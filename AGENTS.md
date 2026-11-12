# Workspace boundary and dependency hygiene

Keep project code, test data, generated artifacts, virtual environments, package
caches and temporary files inside this checkout. Set TMPDIR and package cache
directories accordingly. Do not use global pip or system package managers.

Use `uv` as the primary package manager for environments, dependencies, lockfiles,
builds and package publication. Use `pip` only as a workaround when installing
from `requirements.txt`. Export that file with `uv export` when needed. Set
`UV_CACHE_DIR` inside this checkout, and disable automatic Python downloads
unless the interpreter's version and provenance have been verified first.

Before installing a dependency or container image, verify its exact name against
the official registry or publisher. Pin an exact version released at least two
weeks before the current date, and record its origin, release date and checksum.
Do not use floating tags or version ranges. If these constraints prevent finishing
the task, stop and report the blocker. Docker image/cache/service data may remain
outside the checkout when testing container isolation.

Commit each completed project stage after its checks pass. Do not check usage
limits or pause work because of them. Prefer links to primary sources and logs.
Never commit credentials, local configuration, private fixtures or server data.
