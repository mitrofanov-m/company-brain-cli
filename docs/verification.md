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

During initial extraction, `uv sync --locked` could not download the pinned
build dependency. This blocker was resolved during v0.1.0 release preparation:
`uv build --no-sources` built wheel and source distributions with the verified
setuptools 84.1.0. The wheel was installed using `uv pip install --no-index
--no-deps` into a fresh virtual environment inside this checkout. Its installed
`brain` entry point passed version/help checks and all 5 real API/MCP/Docker
integration tests. The 14 standalone tests also passed again. See
[release logs](logs/) and [dependency provenance](dependencies.json).

This repository starts with a fresh git history. Its selected source files,
tests, documentation and lockfile exclude server data, credential files and the
source repository's history.

Publication follow-up: on 2026-11-12 the independent repository was pushed to
[mitrofanov-m/company-brain-cli](https://github.com/mitrofanov-m/company-brain-cli),
with local `main` tracking `origin/main`. The earlier publication blocker has
been resolved. Release assets and instructions are described in
[v0.1.0](releases/v0.1.0.md).


## 0.1.1 candidate — 2026-11-12

17 standalone checks passed, including binary file upload, atomic verified
download, 1 GB + 1 byte rejection and interrupted downloads. `uv lock --check`
ran offline; the stdlib zipapp reports version 0.1.1. No dependency was installed.
See [log](logs/large-upload-candidate.log).

The platform checkout additionally tested this standalone source and zipapp
against its candidate API: exact 1,000,000,000-byte upload, publish, download and
SHA-256 verification, the existing five CLI/API/MCP/sandbox contracts, and a
separate 1 GB UI proxy round trip. These are local candidate compatibility
checks. Production deployment and public CLI release remain pending because
production SSH requires a key outside the authorized workspace. Release this
CLI before the corresponding platform release, then record its tag/commit in
the platform release description.

## 0.1.1 release verification — 2026-11-12

Repeated 17 standalone tests, lock verification and zipapp build/version/help
checks. `uv build --offline --no-sources` built wheel and sdist with the already
verified setuptools 84.1.0 in the checkout-local cache. No dependency or image
was downloaded. Installed the wheel into a fresh checkout-local environment
with uv; its command reports 0.1.1.

Both the zipapp and installed wheel passed all five real API/MCP/Docker
integration checks against the platform 0.2.2 candidate (source 6158478 plus
the release version update). The platform's full tracked suite also passed
513 Python tests, including exact 1 GB transfer checks, and 121 JavaScript
tests. The earlier production access blocker was resolved before rollout.
See `docs/logs/release-0.1.1-*.log`. Public release publication follows these
checks and precedes the platform release.
