# S01 — Repository skeleton, package layout, CI, test harness conventions

**Status:** planned
**Primary model:** Sonnet · **Reviewer:** none
**Depends on:** — · **Milestone:** M0
**Issue:** (filled in when filed)

## Goal

Turn the documentation-only repository into an installable Python
package with a test runner, a CI workflow, and the module skeleton every
later slice fills in. After this slice, `pip install -e .` works,
`pytest` runs one trivial passing test, and `python -m blacksite.door`
prints a one-line "not implemented" and exits 0.

## Spec references

- `docs/design/02-architecture.md` §2 (components), §14 (packaging).
- `AGENTS.md` §1, §4, §5, §9 (layout, coding and testing rules).
- `docs/plan/00-roadmap.md` §7 (definition of done).

## Scope

- `pyproject.toml`: package `blacksite`, `requires-python >= 3.12`, no
  runtime dependencies, `pytest` as the only test dependency, setuptools
  `src/` layout, package data include for `src/blacksite/content/**`,
  console entry points `blacksite-server`, `blacksite-door`,
  `blacksite-admin`, `blacksite-bot` mapping to `blacksite.<sub>.__main__:main`.
- Module skeleton with docstrings and a `main()` that prints "blacksite
  <module>: not implemented (see docs/plan/slices/)" and exits 0:
  `src/blacksite/__init__.py` (`__version__ = "0.0.1"`),
  `server/__init__.py`, `server/__main__.py`, `door/__init__.py`,
  `door/__main__.py`, `admin/__init__.py`, `admin/__main__.py`,
  `bot/__init__.py`, `bot/__main__.py`, `content/__init__.py`
  (empty package with a `README.md` explaining the tree from
  `01-entities.md` §1).
- `src/blacksite/version.py`: `PACKAGE_VERSION`, `PROTOCOL_MAJOR = 1`,
  `CONTENT_SCHEMA = 1`, `WORLD_SCHEMA = 1` as named constants with a
  comment citing `02-architecture.md` §5.1 and §6.2.
- `tests/conftest.py` with a `repo_root` fixture and a `scratch_dir`
  fixture (a `tmp_path` subdirectory; never `/tmp`).
- `tests/test_skeleton.py`: imports every package, asserts the version
  constants exist, runs each `__main__.main()` and asserts exit 0.
- `.github/workflows/ci.yml`: on push and pull request, matrix of
  `ubuntu-latest` and `windows-latest`, Python 3.12, `pip install -e
  .[test]`, `pytest -q`. No NetBSD runner exists; note in the workflow
  that NetBSD is verified by hand.
- `deploy/README.md` placeholder describing what S05 and S31 will put
  there.
- `.gitignore` extended for `.venv/`, `*.egg-info/`, `.pytest_cache/`,
  `build/`, `dist/`, `.test-tmp/`.
- `docs/ops/README.md` placeholder pointing at S28/S31.

## Out of scope

- Any real server, client, or content code (S02, S03, S04).
- The deploy templates themselves (S05).
- Release packaging and tagging (S31).

## Data and content

None. `src/blacksite/content/README.md` documents the intended tree only.

## Protocol and view models

None. `PROTOCOL_MAJOR` is declared so S03 and S04 assert the same
constant.

## Tests

- `tests/test_skeleton.py::test_packages_import` — every `blacksite.*`
  package imports.
- `tests/test_skeleton.py::test_version_constants` — `PACKAGE_VERSION`
  matches `pyproject.toml`, `PROTOCOL_MAJOR == 1`.
- `tests/test_skeleton.py::test_mains_exit_zero` — each `__main__.main()`
  returns 0 and prints one line containing the module name.
- `tests/test_skeleton.py::test_no_runtime_dependencies` — parse
  `pyproject.toml` and assert `dependencies` is empty.

## Acceptance script

1. `python -m venv .venv`, activate, `pip install -e .[test]`.
2. `pytest -q` → 4 passed.
3. `python -m blacksite.door` → one line, exit 0.
4. Push a branch; CI green on both runners.

## Definition of done

- Roadmap §7 holds.
- `AGENTS.md` §9 layout matches what exists (adjust the doc if a path
  had to differ, with the reason in the PR).
- Slice file marked `Status: done (PR #n)`.

## Implementer notes

- NetBBS launches doors with an argv list, never a shell; the console
  entry points are conveniences for humans. The door profile will name
  the venv interpreter and `-m blacksite.door` explicitly
  (`02-architecture.md` §8.1), so `python -m blacksite.door` must always
  work without the console script.
- Windows is a supported development host for tests and the client
  (`AGENTS.md` §5). Keep paths through `pathlib`, no `os.fork`.
- Keep the package data include broad now (`content/**`) so S02 does not
  have to touch packaging.
