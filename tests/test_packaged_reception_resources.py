from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXE_PATH = ROOT / "dist" / "inventory-system.exe"


def test_packaged_reception_resources_match_sources_byte_for_byte():
    if not EXE_PATH.is_file():
        pytest.skip("inventory-system.exe has not been built")

    from PyInstaller.archive.readers import CArchiveReader

    archive = CArchiveReader(str(EXE_PATH))
    resources = (
        (ROOT / "app" / "static" / "js" / "reception.js", r"app\static\js\reception.js"),
        (ROOT / "app" / "templates" / "reception.html", r"app\templates\reception.html"),
    )

    for source_path, archive_name in resources:
        packaged = archive.extract(archive_name)
        assert packaged == source_path.read_bytes()

    packaged_js = archive.extract(r"app\static\js\reception.js")
    assert b"function findScrollableAncestor(element)" in packaged_js
    assert b"async function scrollToWeightControl(element)" in packaged_js
    assert b"element.focus({ preventScroll: true })" in packaged_js
