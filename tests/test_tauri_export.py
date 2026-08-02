import json

from arabicpy.tauri_export import export_tauri_project


def test_exports_tauri_react_project_for_all_platforms(tmp_path):
    source = '''اسم التطبيق هو الباء
لون الشاشة اسود
في شريط السفلي ضع:
    الرئيسية
    البحث
انشئ زر اسمه اضغط هنا
'''
    export_tauri_project(source, tmp_path)
    package = json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))
    config = json.loads((tmp_path / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    workflow = (tmp_path / ".github" / "workflows" / "build-all.yml").read_text(encoding="utf-8")
    windows_workflow = (tmp_path / ".github" / "workflows" / "build-windows.yml").read_text(encoding="utf-8")
    app = (tmp_path / "src" / "App.tsx").read_text(encoding="utf-8")
    assert package["devDependencies"]["@tauri-apps/cli"] == "^2"
    assert config["productName"] == "الباء"
    assert 'dir="rtl"' in app
    assert all(target in workflow for target in ("windows-latest", "ubuntu-24.04", "macos-latest"))
    assert "name: albaa-web" in workflow
    assert "path: dist/**" in workflow
    assert "runs-on: windows-latest" in windows_workflow
    assert "name: albaa-windows-app" in windows_workflow
