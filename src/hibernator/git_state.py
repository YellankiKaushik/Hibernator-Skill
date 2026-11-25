from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import time
from bisect import bisect_left
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ScanFailure, UnsupportedRoot
from .paths import local_mounts, path_key, real_directory, stamp
from .util import is_reparse_point


INDEX_ROW = re.compile(
    rb"H (100644|100755|120000) ([0-9a-f]{40}) 0\t([^\0]+)\0"
    rb"  ctime: \d+:\d+\n  mtime: (\d+):(\d+)\n  dev: \d+\tino: \d+\n"
    rb"  uid: \d+\tgid: \d+\n  size: (\d+)\tflags: (?:0|20000000)\n"
)


@dataclass(frozen=True)
class GitState:
    root: Path
    tracked: frozenset[str]
    snapshot: str
    tracked_snapshot: str
    index_metadata: dict[str, tuple[int, int, int]] = field(default_factory=dict)
    staged_paths: int = 0
    tracked_index: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracked_index", tuple(sorted({path_key(path) for path in self.tracked})))

    def protects(self, relative: str) -> bool:
        key = path_key(relative)
        if self.has_file(relative):
            return True
        prefix = key + "/"
        i = bisect_left(self.tracked_index, prefix)
        return i < len(self.tracked_index) and self.tracked_index[i].startswith(prefix)

    def has_file(self, relative: str) -> bool:
        key = path_key(relative)
        i = bisect_left(self.tracked_index, key)
        return i < len(self.tracked_index) and self.tracked_index[i] == key


@dataclass
class GitReader:
    root: Path
    calls: int = 0
    seconds: float = 0.0
    admin: dict[Path, tuple[int, ...] | None] = field(default_factory=dict)
    executable: str = field(init=False)

    def __post_init__(self) -> None:
        git = shutil.which("git")
        if not git:
            raise ScanFailure("Git is required to inspect the selected project.")
        executable = Path(git).resolve()
        if executable.is_relative_to(self.root) or executable.suffix.lower() in {".bat", ".cmd"}:
            raise ScanFailure("Git must be a trusted executable outside the selected project.")
        self.executable = str(executable)

    def run(self, *args: str) -> bytes:
        env = {key: value for key, value in os.environ.items()
               if not key.upper().startswith(("GIT_", "LD_", "DYLD_"))}
        env.update(GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1", GIT_ALLOW_PROTOCOL="",
                   LC_ALL="C")
        start = time.monotonic()
        self.calls += 1
        try:
            result = subprocess.run(
                [self.executable, "--no-pager", "-c", "core.fsmonitor=false", "-c",
                 "core.untrackedCache=false", "-c", "submodule.recurse=false",
                 "-c", "core.hooksPath=", "-c", "core.quotePath=true", "-C", str(self.root), *args],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                env=env, cwd=str(Path(self.executable).parent), shell=False, timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            raise ScanFailure("Git could not interpret local repository metadata.") from exc
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ScanFailure("Git metadata inspection could not finish.") from exc
        finally:
            self.seconds += time.monotonic() - start
        if len(result.stdout) > 128 << 20:
            raise ScanFailure("Git metadata output exceeded its local inspection limit.")
        return result.stdout

    def prepare(self) -> None:
        metadata = self.root / ".git"
        try:
            device = real_directory(self.root).st_dev
            if real_directory(metadata).st_dev != device or any(mount.is_relative_to(metadata) for mount in local_mounts()):
                raise ScanFailure("Git metadata crosses a filesystem boundary.")
            self._check_admin(device)
            names = self.run("config", "--file", str(metadata / "config"),
                             "--no-includes", "--name-only", "--null", "--list")
        except (OSError, UnsupportedRoot) as exc:
            raise UnsupportedRoot("Select an ordinary Git root with a local .git directory.") from exc
        keys = names.lower().split(b"\0")
        if any(key.startswith((b"include.", b"includeif.", b"filter.", b"extensions.", b"submodule."))
               or key in {b"core.worktree", b"core.sparsecheckout", b"core.sparsecheckoutcone",
                          b"index.sparse", b"core.splitindex", b"core.attributesfile", b"core.excludesfile"}
               for key in keys):
            raise ScanFailure("Git configuration contains unsupported includes, filters, or layout options.")
        if not self.unchanged():
            raise ScanFailure("Git metadata changed during configuration inspection.")
        root = self.run("rev-parse", "--show-toplevel").removesuffix(b"\n").removesuffix(b"\r")
        try:
            if Path(os.fsdecode(root)).resolve(strict=True) != self.root:
                raise UnsupportedRoot("Select the exact Git working-tree root.")
        except OSError as exc:
            raise UnsupportedRoot("Git did not identify the selected working-tree root.") from exc

    def _check_admin(self, device: int) -> None:
        meta = self.root / ".git"
        with os.scandir(meta) as entries:
            for number, entry in enumerate(entries):
                if number >= 4096 or entry.name.startswith("sharedindex."):
                    raise ScanFailure("Git metadata exceeds supported repository layouts.")
        # Only Git metadata is visited here. The working-tree inventory does not walk .git.
        pending = [meta / entry for entry in ("objects", "refs", "info")]
        seen = 0
        while pending:
            directory = pending.pop()
            try:
                info = directory.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISDIR(info.st_mode) or is_reparse_point(info) or info.st_dev != device:
                raise ScanFailure("A Git administrative path crosses an unsupported boundary.")
            if directory.name != "objects" and not directory.is_relative_to(meta / "objects"):
                self.admin[directory] = stamp(info)
            with os.scandir(directory) as entries:
                for entry in entries:
                    seen += 1
                    if seen > 250_000:
                        raise ScanFailure("Git administrative inspection exceeded its entry budget.")
                    path = Path(entry.path)
                    record = path.lstat() if os.name == "nt" else entry.stat(follow_symlinks=False)
                    if record.st_dev not in {0, device} or is_reparse_point(record):
                        raise ScanFailure("A Git administrative entry crosses an unsupported boundary.")
                    if path.suffix == ".promisor":
                        raise ScanFailure("Partial clone objects are not supported.")
                    if stat.S_ISDIR(record.st_mode):
                        pending.append(path)
                    elif not stat.S_ISREG(record.st_mode) or record.st_nlink > 1:
                        raise ScanFailure("Git administrative content is linked or unsupported.")
                    elif not directory.is_relative_to(meta / "objects"):
                        if len(self.admin) >= 4096:
                            raise ScanFailure("Git references exceed the observation budget.")
                        self.admin[path] = stamp(record)
        for forbidden in ("commondir", "worktrees", "info/sparse-checkout", "objects/info/alternates",
                          "objects/info/http-alternates", "index.lock", "shallow.lock"):
            candidate = meta / forbidden
            try:
                candidate.lstat()
            except FileNotFoundError:
                self.admin[candidate] = None
                continue
            raise ScanFailure("Git administrative layout or a concurrent Git operation is unsupported.")
        for name in (".git", ".git/config", ".git/index", ".git/HEAD", ".git/packed-refs",
                     ".git/config.worktree", ".git/shallow"):
            path = self.root / name
            try:
                info = path.lstat()
            except FileNotFoundError:
                if name in {".git", ".git/config", ".git/HEAD"}:
                    raise ScanFailure("Required Git metadata is missing.")
                self.admin[path] = None
                continue
            if info.st_dev != device or is_reparse_point(info) or (
                name != ".git" and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)
            ):
                raise ScanFailure("A Git administrative file is linked or unsupported.")
            if info.st_size > (64 << 20 if name == ".git/index" else 16 << 20):
                raise ScanFailure("Git metadata exceeds its local inspection limit.")
            self.admin[path] = stamp(info)

    def unchanged(self) -> bool:
        for path, expected in sorted(self.admin.items(), key=lambda entry: len(entry[0].parts)):
            try:
                current = stamp(path.lstat())
            except FileNotFoundError:
                current = None
            if current != expected:
                return False
        return True

    def retirement_state(self) -> GitState:
        self.prepare()
        index = self.run("ls-files", "--stage", "--debug", "-v", "-z")
        indexed = {}
        index_metadata = {}
        offset = 0
        while offset < len(index):
            match = INDEX_ROW.match(index, offset)
            if not match:
                raise ScanFailure("Git index has unsupported, sparse, assumed, unmerged or submodule entries.")
            mode, object_id, raw_path, seconds, nanos, size = match.groups()
            path = raw_path.decode("utf-8", "surrogateescape")
            key = path_key(path)
            if key in index_metadata:
                raise ScanFailure("Git index contains ambiguous path aliases.")
            index_metadata[key] = (int(mode, 8), int(seconds) * 1_000_000_000 + int(nanos), int(size))
            indexed[path] = (mode, object_id)
            offset = match.end()
        head = self.run("rev-parse", "--verify", "--quiet", "HEAD")
        if not re.fullmatch(rb"[a-f0-9]{40}\n", head):
            raise ScanFailure("The Git HEAD object format is unsupported.")
        committed = self.run("ls-tree", "-r", "-z", "--full-tree", head.strip().decode("ascii"))
        head_entries = {}
        for row in committed.split(b"\0"):
            if not row:
                continue
            metadata, _, path = row.partition(b"\t")
            fields = metadata.split()
            if not path or len(fields) != 3 or fields[0] not in {b"100644", b"100755", b"120000"}:
                raise ScanFailure("The selected Git history has an unsupported submodule boundary.")
            head_entries[path.decode("utf-8", "surrogateescape")] = (fields[0], fields[2])
        all_paths = indexed.keys() | head_entries.keys()
        staged_paths = sum(indexed.get(path) != head_entries.get(path) for path in all_paths)
        index_content = b"".join(mode + b" " + oid + b"\t" + path.encode("utf-8", "surrogateescape") + b"\0"
                                 for path, (mode, oid) in indexed.items())
        fingerprint = hashlib.sha256(b"\0".join((head.strip(), index_content, committed))).hexdigest()
        return GitState(self.root, frozenset(all_paths), fingerprint, fingerprint, index_metadata, staged_paths)


def read_git_state(project: Path) -> GitState:
    reader = GitReader(project)
    reader.prepare()
    tracked_raw = reader.run("ls-files", "-z", "--cached")
    tracked = frozenset(os_path.decode("utf-8", "surrogateescape") for os_path in tracked_raw.split(b"\0") if os_path)
    from .rules import protected_secret
    if any(protected_secret(Path(path).name) for path in tracked):
        raise ScanFailure("A tracked secret-like file prevents legacy Git status inspection; use retire.")
    index = reader.run("ls-files", "--stage", "-v", "-z")
    if any(
        not row.startswith(b"H ") or row.startswith(b"H 160000 ")
        for row in index.split(b"\0") if row
    ):
        raise ScanFailure("Legacy preview requires an ordinary, non-sparse Git index.")
    index = b"".join(row[2:] + b"\0" for row in index.split(b"\0") if row)
    status = reader.run("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=all")
    unstaged = reader.run("diff", "--raw", "--no-ext-diff", "--no-textconv", "--ignore-submodules=all")
    staged = reader.run("diff", "--cached", "--raw", "--no-ext-diff", "--no-textconv", "--ignore-submodules=all")
    try:
        head = reader.run("rev-parse", "--verify", "HEAD")
    except ScanFailure:
        head = b"UNBORN"
    if head != b"UNBORN":
        committed = reader.run("ls-tree", "-r", "-z", "--full-tree", head.strip().decode("ascii"))
        head_records = [(row.partition(b"\t")[0], row.partition(b"\t")[2])
                        for row in committed.split(b"\0") if row]
        if any(header.startswith(b"160000 ") for header, _ in head_records):
            raise ScanFailure("Legacy preview cannot inspect a Git submodule layout.")
        tracked |= frozenset(path.decode("utf-8", "surrogateescape") for _, path in head_records)
    snapshot = hashlib.sha256(b"\0".join((head.strip(), tracked_raw, status))).hexdigest()
    tracked_snapshot = hashlib.sha256(b"\0".join((head.strip(), index, unstaged, staged))).hexdigest()
    if not reader.unchanged():
        raise ScanFailure("Git metadata changed during inspection.")
    return GitState(project, tracked, snapshot, tracked_snapshot)
