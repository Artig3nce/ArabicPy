import ast

from arabicpy.pyside_template import generate_pyside_project


def _all_python_files(root):
    return sorted(path for path in root.rglob("*.py"))


def test_generates_expected_files(tmp_path):
    project_dir = tmp_path / "DemoApp"
    generate_pyside_project(str(project_dir), "Demo App")

    expected = [
        "main.py",
        "main_window.py",
        "pyproject.toml",
        "README.md",
        ".gitignore",
        "styles/overrides.qss",
        "pages/__init__.py",
        "pages/welcome_page.py",
        "pages/settings_page.py",
        "pages/ai_panel.py",
        "design_system/__init__.py",
        "design_system/tokens.py",
        "design_system/qss.py",
        "design_system/icons.py",
        "design_system/components.py",
    ]
    for relative in expected:
        assert (project_dir / relative).is_file(), f"missing {relative}"


def test_generated_python_files_parse(tmp_path):
    project_dir = tmp_path / "DemoApp"
    generate_pyside_project(str(project_dir), "Demo App")

    for path in _all_python_files(project_dir):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_pyproject_declares_pyside6_only(tmp_path):
    project_dir = tmp_path / "DemoApp"
    generate_pyside_project(str(project_dir), "Demo App")

    content = (project_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert "PySide6" in content
    for heavy_dependency in ("paddleocr", "paddlepaddle", "pypdf", "python-docx"):
        assert heavy_dependency not in content


def test_project_name_with_symbols_produces_safe_folder_name(tmp_path):
    project_dir = tmp_path / "my_app"
    generate_pyside_project(str(project_dir), "My App! v2.0")

    content = (project_dir / "main_window.py").read_text(encoding="utf-8")
    assert "My App! v2.0" in content
