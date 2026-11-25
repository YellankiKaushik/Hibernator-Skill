"""Path validation shared by project readers and local report writers."""

from __future__ import annotations

import os
import re
import stat
import sys
import unicodedata
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath

from .errors import UnsupportedRoot
from .util import is_reparse_point


def local_path(value: str | os.PathLike[str]) -> Path:
    raw = os.fspath(value)
    win = PureWindowsPath(raw)
    if (
        not raw or "\0" in raw or raw.startswith(("//", "\\"))
        or win.drive and (os.name != "nt" or not win.is_absolute())
        or os.name == "nt" and any(
            PureWindowsPath(part).is_reserved() or ":" in part or part.endswith((".", " "))
            for part in win.parts if part != win.anchor and part not in {".", ".."}
        )
        or ".." in Path(raw).parts
    ):
        raise UnsupportedRoot("Use an unambiguous local path without traversal or device aliases.")
    return Path(raw).absolute()


def real_directory(path: Path) -> os.stat_result:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or is_reparse_point(info):
        raise UnsupportedRoot("A directory boundary is a link, reparse point, or non-directory.")
    return info


def directory_chain(path: Path) -> os.stat_result:
    for ancestor in reversed(path.parents):
        real_directory(ancestor)
    return real_directory(path)


def mounted_filesystems() -> dict[Path, bytes]:
    """Recognize Linux mount entries and their filesystem types."""
    if not sys.platform.startswith("linux"):
        return {}
    with open("/proc/self/mountinfo", "rb") as stream:
        data = stream.read((4 << 20) + 1)
    if len(data) > 4 << 20:
        raise OSError("The local mount table exceeds the inspection limit.")
    result = {}
    for line in data.splitlines():
        fields = line.split()
        if len(fields) < 10 or fields[-4] != b"-":
            raise OSError("The local mount table could not be interpreted.")
        name = re.sub(rb"\\([0-7]{3})", lambda match: bytes([int(match[1], 8)]), fields[4])
        result[Path(os.fsdecode(name))] = fields[-3]
    return result


def local_mounts() -> set[Path]:
    return set(mounted_filesystems())


def external_filesystem(kind: bytes) -> bool:
    return kind.startswith((b"nfs", b"cifs", b"smb", b"9p", b"sshfs", b"fuse.", b"afs", b"ceph"))


def external_directory(directory: Path, root: Path | None) -> Path:
    """Validate an existing ancestor before creating a legacy output directory."""
    directory = local_path(directory)
    if root is not None and directory.is_relative_to(root):
        raise UnsupportedRoot("Local output must be outside the project.")
    current = directory
    missing = []
    while True:
        try:
            directory_chain(current)
            break
        except FileNotFoundError:
            missing.append(current)
            current = current.parent
    if directory.resolve(strict=False) != directory:
        raise UnsupportedRoot("Local output uses a path alias.")
    for path in reversed(missing):
        if root is not None and path.is_relative_to(root):
            raise UnsupportedRoot("Local output must be outside the project.")
        directory_chain(path.parent)
        path.mkdir(mode=0o700, exist_ok=True)
        real_directory(path)
    directory_chain(directory)
    return directory


def canonical_root(value: str | os.PathLike[str]) -> Path:
    supplied = local_path(value)
    try:
        directory_chain(supplied)
        root = supplied.resolve(strict=True)
        if supplied != root:
            raise UnsupportedRoot("Select the canonical project directory without aliases.")
        if root.parent == root or root == Path.home().resolve():
            raise UnsupportedRoot("Select a Git project, rather than the filesystem or home root.")
        mounts = mounted_filesystems()
        if root in mounts:
            raise UnsupportedRoot("A mounted directory cannot be verified as the project root.")
        if any(external_filesystem(mounts.get(parent, b"")) for parent in root.parents):
            raise UnsupportedRoot("The project crosses an unsupported network or virtual filesystem.")
        if os.name == "nt" and not windows_local_drive(root):
            raise UnsupportedRoot("The project must be on a local drive.")
    except OSError as exc:
        raise UnsupportedRoot("The project directory cannot be inspected.") from exc
    return root


def windows_local_drive(path: Path) -> bool:
    import ctypes

    return ctypes.windll.kernel32.GetDriveTypeW(path.anchor) in (2, 3, 6)


def validate_windows_private_directory(path: Path) -> None:
    """Reject absent DACLs and grants to common broad Windows principals."""
    import ctypes
    from ctypes import wintypes

    api = ctypes.WinDLL("advapi32", use_last_error=True)
    security = api.GetFileSecurityW
    security.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
                         wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
    security.restype = wintypes.BOOL
    convert = api.ConvertSecurityDescriptorToStringSecurityDescriptorW
    convert.argtypes = (ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                        ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(wintypes.DWORD))
    convert.restype = wintypes.BOOL
    free = ctypes.windll.kernel32.LocalFree
    free.argtypes = (ctypes.c_void_p,)
    free.restype = ctypes.c_void_p
    size = wintypes.DWORD()
    dacl = 4
    security(str(path), dacl, None, 0, ctypes.byref(size))
    if not size.value or size.value > 64 << 10:
        raise OSError("The report directory ACL could not be verified.")
    descriptor = ctypes.create_string_buffer(size.value)
    result = wintypes.LPWSTR()
    if not security(str(path), dacl, descriptor, size.value, ctypes.byref(size)) or not convert(
        descriptor, 1, dacl, ctypes.byref(result), None,
    ):
        raise OSError("The report directory ACL could not be verified.")
    try:
        sddl = result.value
    finally:
        free(result)
    broad = {"WD", "AU", "BU", "AN", "IU", "NU", "PU", "AC", "S-1-1-0", "S-1-5-11", "S-1-5-32-545"}
    if not sddl or "NO_ACCESS_CONTROL" in sddl:
        raise UnsupportedRoot("The report directory needs a private Windows ACL.")
    entries = re.findall(r"\(([^()]*)\)", sddl)
    if len(entries) != sddl.count("("):
        raise UnsupportedRoot("The report directory ACL uses an unsupported access rule.")
    for entry in entries:
        fields = entry.split(";")
        kind, principal = fields[0], fields[-1]
        if kind in {"A", "OA", "XA", "ZA"} and principal in broad:
            raise UnsupportedRoot("The report directory grants access to a broad Windows principal.")


@contextmanager
def pin_windows_directory(path: Path):
    """Hold a directory handle without FILE_SHARE_DELETE during report publication."""
    if os.name != "nt":
        yield
        return
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    handle = create(str(path), 0x80, 0x3, None, 3, 0x02200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        real_directory(path)
        yield
    finally:
        close(handle)


def path_key(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


def relative_path(value: str) -> bool:
    if not isinstance(value, str) or re.search(r'[\\:*?\[\]<>|"]', value):
        return False
    return all(
        part not in {"", ".", ".."} and not part.endswith((".", " "))
        and not PureWindowsPath(part).is_reserved()
        and not any(unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in part)
        for part in value.split("/")
    )


def stamp(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def observed_entry(expected: os.stat_result, current: os.stat_result) -> bool:
    """Windows DirEntry.stat can omit the device and inode."""
    a, b = stamp(expected), stamp(current)
    return all(not left or left == right for left, right in zip(a[:2], b[:2])) and (
        a[2] == b[2] and (not a[3] or a[3] == b[3]) and a[4:] == b[4:]
    )


def same_open_file(expected: os.stat_result, current: os.stat_result) -> bool:
    if os.name == "nt":
        # CPython can derive ctime and execute bits differently for Windows handles.
        left, right = stamp(expected), stamp(current)
        return left[:2] == right[:2] and stat.S_IFMT(left[2]) == stat.S_IFMT(right[2]) and left[3:6] == right[3:6]
    return observed_entry(expected, current)


def open_observed(path: Path, expected: os.stat_result):
    """Open a regular single-link file and confirm identity before exposing its bytes."""
    directory_chain(path.parent)
    current = path.lstat()
    if (not stat.S_ISREG(current.st_mode) or is_reparse_point(current) or current.st_nlink != 1
            or not observed_entry(expected, current)):
        raise OSError("File boundary changed or could not be verified.")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    handle = os.fdopen(os.open(path, flags), "rb")
    if not same_open_file(current, os.fstat(handle.fileno())):
        handle.close()
        raise OSError("File changed before reading.")
    return handle
