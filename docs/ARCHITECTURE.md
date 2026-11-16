# Architecture

Hibernator is a Python 3.10+ standard-library-first CLI. `cli` is the only public command interface. `git_state` reads Git root, tracked paths, HEAD, and status; `discovery` inventories project markers and classifies paths using the versioned rules in `rules`; `plans` serializes canonical candidates and invalidates stale plans; `cleaner` isolates the test-fixture cleanup pathway and refuses production deletion; `reports` writes local reports outside the project; `restore` prints non-mutating package restoration suggestions.

The Agent Skill is an interaction protocol, not a second cleanup engine. It directs agents to the same CLI and forbids model-generated deletion commands or approval impersonation.

No server, account system, telemetry, database, remote API, package-manager invocation, or required LLM is part of this MVP.
