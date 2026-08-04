from pathlib import Path

DESIGN_SYSTEM_DIR = Path(__file__).resolve().parent.parent / "arabicpy" / "design_system"


def test_design_system_files_have_no_arabicpy_imports():
    """design_system/ is copied verbatim into every generated project, so it
    must never depend on the rest of the arabicpy package -- only stdlib
    and PySide6."""
    for path in sorted(DESIGN_SYSTEM_DIR.glob("*.py")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("import arabicpy") or stripped.startswith("from arabicpy"):
                raise AssertionError(f"{path.name}:{line_number} imports arabicpy: {stripped!r}")
            if stripped.startswith("from ..") or stripped.startswith("import .."):
                raise AssertionError(f"{path.name}:{line_number} reaches outside design_system/: {stripped!r}")
