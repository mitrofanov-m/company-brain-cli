# Changelog

## 0.1.1 — 2026-11-12

- Stream binary file uploads up to 1,000,000,000 bytes using `files write`.
- Add `files download` with streaming, SHA-256 verification and atomic output
  replacement; interrupted or invalid downloads preserve an existing file.
- Keep stdin text writes and existing JSON API scenarios compatible.
- Binary uploads/downloads require the Company Brain 0.2.2 API.

## 0.1.0 — 2026-11-12

First standalone Company Brain CLI release.

- `brain` command, `python3 -m brain_cli` and portable Python zipapp.
- Workspace browsing, binary reads, search, history, sessions, staged file edits,
  commits, tool discovery/calls and server-side script execution.
- Workspace-local credentials with owner-only permissions, HTTPS enforcement
  outside loopback, rejected redirects and workspace/session matching checks.
- Explicit settings precedence: command line, environment, saved configuration.
- Python 3.11+ with no runtime dependencies; uv workflow and checked-in lockfile.
- Wheel and source distributions built with pinned, verified setuptools 84.1.0.
- Standalone HTTP tests and real API/MCP/Docker interoperability verification.
