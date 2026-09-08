from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ISS_PATH = ROOT / "installer" / "inventory-system.iss"
ICON_PATH = ROOT / "app" / "static" / "img" / "branding" / "agricola-vita-santa-fe.ico"


def _script():
    return ISS_PATH.read_text(encoding="utf-8")


def test_brand_icon_exists_and_is_not_empty():
    assert ICON_PATH.is_file()
    assert ICON_PATH.stat().st_size > 0


def test_installer_copies_branding_icon_to_stable_app_path():
    script = _script()
    assert 'DestDir: "{app}\\static\\img\\branding"' in script
    assert '#define MyInstalledIcon "{app}\\static\\img\\branding\\agricola-vita-santa-fe.ico"' in script


def test_start_menu_shortcut_uses_installed_icon_and_index_zero():
    line = next(
        line for line in _script().splitlines()
        if line.startswith('Name: "{group}\\{#MyAppName}"')
    )
    assert 'IconFilename: "{#MyInstalledIcon}"' in line
    assert "IconIndex: 0" in line
    assert "MyAppIcon" not in line


def test_desktop_shortcut_uses_installed_icon_and_index_zero():
    line = next(
        line for line in _script().splitlines()
        if line.startswith('Name: "{autodesktop}\\{#MyAppName}"')
    )
    assert 'IconFilename: "{#MyInstalledIcon}"' in line
    assert "IconIndex: 0" in line
    assert "MyAppIcon" not in line


def test_executable_remains_windowed_without_corporate_icon():
    spec = (ROOT / "build.spec").read_text(encoding="utf-8")
    exe_section = spec.split("exe = EXE(", 1)[1]
    assert "console=False" in exe_section
    assert "icon=" not in exe_section
