# Verification — 2026-11-12

Tested on macOS arm64, CPython 3.14.7, with the existing uv 0.11.3.
Other supported Python versions have not been exercised in this extraction.

A clean independent clone of commit `80e3da2` passed the 14 standalone tests,
rebuilt the zipapp, and passed all 5 real server/Docker tests using that artifact.
The tested artifact checksum is recorded in [artifact.json](artifact.json).

- 14 standalone HTTP/CLI tests passed: configuration permissions and boundaries,
  login, settings precedence, guest reads, workspace/session isolation, CRUD,
  history, tool discovery/calls, remote execution status, errors and redirects.
- The built zipapp passed `--version` and `--help` with isolated Python and
  without the source checkout on `PYTHONPATH`; direct executable launch passed.
- 5 real server integration tests passed using the zipapp from a separate
  working directory: session/write/read/search/history/close, read-only access,
  workspace isolation, MCP interoperability and server-side Docker execution.
  The success case committed its result; the failing script published no edit.
- 14 legacy CLI/MCP server regression tests passed.
- `uv lock --check --offline` and `uv export --locked --no-emit-project
  --format requirements.txt` passed. There are no runtime dependencies to export.

Passing test logs are in [logs](logs/). Server integration tests are maintained
with the separately deployed server, whose fixtures are deliberately excluded
from this client repository. They ran against Company Brain 0.2.1, source
revision `f37e81d`.

`uv sync --locked` could not complete because downloading the pinned build
dependency failed. Wheel build/install and the generated `brain` console entry
point therefore remain unverified. No dependency was installed. The tested
distribution is the standard-library-only `dist/brain.pyz`; rebuilding it does
not require any registry access. See [dependency provenance](dependencies.json).

This repository starts with a fresh git history. Its selected source files,
tests, documentation and lockfile exclude server data, credential files and the
source repository's history.

Publication follow-up: on 2026-11-12 the independent repository was pushed to
[mitrofanov-m/company-brain-cli](https://github.com/mitrofanov-m/company-brain-cli),
with local `main` tracking `origin/main`. The earlier publication blocker has
been resolved; the package-install verification limitation above remains.
