from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXE_PATH = ROOT / "dist" / "inventory-system.exe"


def normalize_newlines(data):
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def test_packaged_admin_and_void_resources_match_sources():
    if not EXE_PATH.is_file():
        pytest.skip("inventory-system.exe has not been built")
    from PyInstaller.archive.readers import CArchiveReader

    archive = CArchiveReader(str(EXE_PATH))
    resources = (
        (ROOT / "app/templates/admin.html", r"app\templates\admin.html"),
        (ROOT / "app/templates/voids.html", r"app\templates\voids.html"),
        (ROOT / "app/static/js/admin.js", r"app\static\js\admin.js"),
        (ROOT / "app/static/js/voids.js", r"app\static\js\voids.js"),
    )
    for source, archive_name in resources:
        assert normalize_newlines(archive.extract(archive_name)) == normalize_newlines(
            source.read_bytes()
        )

    packaged_admin = archive.extract(r"app\templates\admin.html")
    packaged_voids = archive.extract(r"app\templates\voids.html")
    packaged_js = archive.extract(r"app\static\js\voids.js")
    assert b'id="void-modal"' not in packaged_admin
    assert b'id="active-entries-content"' in packaged_voids
    assert b"Confirmar anulaci" in packaged_js
    assert b"X-CSRF-Token" in packaged_js
