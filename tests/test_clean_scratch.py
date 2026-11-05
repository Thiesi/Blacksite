"""scripts/clean_scratch.py removes only ignored scratch."""
import importlib.util
from pathlib import Path

from tests.conftest import REPO_ROOT

spec = importlib.util.spec_from_file_location('clean_scratch', REPO_ROOT / 'scripts' / 'clean_scratch.py')
clean_scratch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clean_scratch)


def test_clean_removes_scratch_and_keeps_everything_else(tmp_path: Path) -> None:
    for rel in ('.test-tmp/a/b.txt', '.pytest_cache/v/x', 'src/pkg/__pycache__/m.pyc',
                'src/pkg.egg-info/PKG-INFO', 'src/pkg/m.py', '.venv/__pycache__/keep.pyc', 'docs/evidence.md'):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('x')
    (tmp_path / '.test-tmp' / 'a' / 'b.txt').chmod(0o444)
    assert clean_scratch.clean(tmp_path) == 0
    left = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob('*') if p.is_file())
    assert left == ['.venv/__pycache__/keep.pyc', 'docs/evidence.md', 'src/pkg/m.py']
