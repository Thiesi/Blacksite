# 06 — Third-party door install path: interpreter-module preset and guide section

**NetBBS issue:** https://github.com/Thiesi/NetBBS/issues/471
**Blocks:** nothing. Blacksite S31 documents the manual path either way.
**Recommended model for the NetBBS side:** Sonnet (a preset JSON, a door-guide section, and a Gallery-adjacent hint).

## The gap

The door guide's native-door section explains interpreters by example
(a JVM jar) and the Gallery pre-fills only NetBBS's own bundled doors. A
door distributed as a Python package in its own venv needs a profile
whose executable is that venv's interpreter and whose argv is
`-m <module>` plus environment variables, plus, once request 01 lands,
a service block. Every third-party door author will write the same
preset and the same paragraph.

## Requested change

- Ship `native-python-module.json` in `src/netbbs/doors/presets` with
  `executable_path` as a placeholder interpreter path, `args` of
  `["-m", "<module>"]`, `endpoint: stdio`, `encoding: utf-8`,
  `max_sessions` left for the author to raise, and an `environment` map
  example.
- Add a door-guide section "Installing a packaged Python door" covering:
  a separate venv owned by the service account, `pip install` of a wheel,
  pointing the preset at the venv interpreter, `max_sessions` and
  `multinode_certified` for multiplayer doors, and where persistent data
  goes (install directory, backed up with the node).
- Optional: let a package ship a `netbbs-door.json` manifest that the
  Compatibility screen's import accepts, so the author's preset is one
  file the SysOp imports.

## What Blacksite does meanwhile

`deploy/netbbs-door-profile.json` is exactly such a preset and the SysOp
guide walks through the import.
