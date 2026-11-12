# Company Brain CLI

Standalone Python client for a Company Brain HTTP API. Requires Python 3.11 or
later; no runtime dependencies. The server is deployed separately.

Download the first release from
[GitHub Releases](https://github.com/mitrofanov-m/company-brain-cli/releases/tag/v0.1.0).
Use `python3 brain-0.1.0.pyz --help` for the portable client. For the wheel:

```sh
mkdir -p .tmp
export TMPDIR="$PWD/.tmp"
export UV_CACHE_DIR="$PWD/.tmp/uv-cache"
export UV_PYTHON_DOWNLOADS=never
uv venv --no-managed-python --python python3 .venv
uv pip install --python .venv/bin/python --no-index ./company_brain_cli-0.1.0-py3-none-any.whl
.venv/bin/brain --version
```

`SHA256SUMS` accompanies the release downloads. The wheel has no dependencies.

## Run without installing

From this checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m brain_cli --help
python3 scripts/build.py
python3 dist/brain.pyz --version
```

The zipapp contains only the client package and runs from any directory. Copy
`dist/brain.pyz` to your working directory and use `python3 brain.pyz` in place of
`brain` below. Neither the source checkout nor the zipapp contains the server.

## Install the command

Use `uv` to install into a virtual environment inside your workspace:

```sh
mkdir -p .tmp
export TMPDIR="$PWD/.tmp"
export UV_CACHE_DIR="$PWD/.tmp/uv-cache"
export UV_PYTHON_DOWNLOADS=never
uv sync --locked --no-managed-python --python python3
uv run --locked brain --version
```

The build dependency is pinned in `pyproject.toml`; see
[dependency provenance](docs/dependencies.json). The distribution name is
`company-brain-cli`, the import package is `brain_cli`, and the command is `brain`.
These instructions install this local checkout; no PyPI release is required.

`uv.lock` records the project environment. Build Python distributions with
`uv build`; publishing with `uv publish` is a separate release action requiring
registry credentials and release authorization. Neither command is required to
use the zipapp. To export runtime dependencies in requirements format:

```sh
uv export --locked --no-emit-project --format requirements.txt --output-file requirements.txt
```

Use `pip` only as a workaround for installing such a `requirements.txt`. New
dependencies must be exactly pinned, verified against the official publisher,
and at least two weeks old before installation. Keep caches and temporary files
inside this checkout. See `AGENTS.md` for the full policy.

## Connect

```sh
export BRAIN_API_URL='https://your-brain-server.example'
brain login
brain workspaces
export BRAIN_WORKSPACE_ID='workspace-id'
brain ls
brain cat knowledge/architecture.md
brain search 'release'
brain session start
printf '# Note\n' | brain files write knowledge/note.md --commit
brain history
brain session close
```

`login` prompts without echo and saves the key in `.brain/config.json` under the
current directory, with file mode `0600`. Add `.brain/` to your workspace's
`.gitignore`. Set `BRAIN_TOKEN` instead to supply credentials through the
environment. Guest reads work without a token when the server permits them.

API origins must use HTTPS except for localhost/loopback development servers.
Redirects are rejected to avoid forwarding credentials. Administrator access
can additionally require the server-issued `BRAIN_ADMIN_SESSION` proof.

Settings precedence is command-line option, then environment variable, then
saved config. Global options go **before** the command:

```sh
brain --api-url http://127.0.0.1:8080 --workspace workspace-id ls knowledge
brain --session session-id tools list
brain --session session-id tools search 'create document'
brain --session session-id tools detail files.write
brain --session session-id tools call files.write '{"path":"note.md","content":"Hello"}'
brain session resume session-id
brain session commit
brain history --session-events
brain files write knowledge/note.md local-note.md --commit
brain files delete knowledge/note.md --commit
brain run task.py
brain help
```

`run` sends the script to the server's `brain.execute` tool; execution and
isolation are controlled by the server. It does not execute the script locally.
Script output goes to stdout; execution status goes to stderr. Exit status is
zero on success, one on API/configuration/execution failure, two on usage errors.
File edits require an active session; use `--commit` or `session commit` to
publish staged edits. An explicit workspace must match the selected session.

`BRAIN_CONFIG_DIR` may relocate config only within the current working directory.
The old server checkout's `company_brain.cli` command remains a legacy entry
point; this package can be installed independently alongside the server.

## Verify

```sh
sh scripts/check.sh
```

Tests use only the standard library and a synthetic loopback HTTP fixture. Test
and build output stays in this checkout. Real server interoperability is checked
separately; see [verification](docs/verification.md).

## Binary files up to 1 GB (0.1.1 candidate)

With a server supporting the streaming transfer API, local file arguments are
uploaded as original binary bytes, up to **1,000,000,000 bytes inclusive**:

```sh
brain session start
brain files write materials/deck.pptx ./deck.pptx --commit
brain files download materials/deck.pptx ./downloaded.pptx
```

Uploads stage the file and publish only with `--commit` or `brain session commit`.
The client streams in bounded chunks, verifies SHA-256 on download, and replaces
an output file only after success. Existing stdin text writes keep the original
JSON tool protocol. JSON requests still have their smaller server limits; for
large files use the local file argument. `cat` remains the JSON resource reader.
Binary upload/download commands require the new server endpoints and return an
error against older servers; continue using CLI 0.1.0 with those deployments.
The 0.1.1 candidate has not been published yet.
