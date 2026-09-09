from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXE_PATH = ROOT / "dist" / "inventory-system.exe"


def normalize_newlines(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def test_packaged_reception_resources_match_sources_byte_for_byte():
    if not EXE_PATH.is_file():
        pytest.skip("inventory-system.exe has not been built")

    from PyInstaller.archive.readers import CArchiveReader

    archive = CArchiveReader(str(EXE_PATH))
    resources = (
        (ROOT / "app" / "static" / "js" / "reception.js", r"app\static\js\reception.js"),
        (ROOT / "app" / "static" / "css" / "reception.css", r"app\static\css\reception.css"),
        (ROOT / "app" / "templates" / "reception.html", r"app\templates\reception.html"),
    )

    for source_path, archive_name in resources:
        packaged = archive.extract(archive_name)
        assert normalize_newlines(packaged) == normalize_newlines(
            source_path.read_bytes()
        )

    packaged_js = archive.extract(r"app\static\js\reception.js")
    assert b"function findScrollableAncestor(element)" in packaged_js
    assert b"async function scrollToWeightControl(element)" in packaged_js
    assert b"element.focus({ preventScroll: true })" in packaged_js
    assert b"async function showRecentMovementAfterRegistration()" in packaged_js
    assert b"recentMovementsSection.scrollIntoView" in packaged_js
    packaged_sacks = archive.extract(r"app\static\js\sacks.js")
    assert normalize_newlines(packaged_sacks) == normalize_newlines(
        (ROOT / "app" / "static" / "js" / "sacks.js").read_bytes()
    )
    assert b"/api/harvest/sack-entries" in packaged_sacks


def test_packaged_phase2_ticket_resources_match_sources():
    if not EXE_PATH.is_file():
        pytest.skip("inventory-system.exe has not been built")

    from PyInstaller.archive.readers import CArchiveReader

    archive = CArchiveReader(str(EXE_PATH))
    resources = (
        (ROOT / "app" / "static" / "js" / "tickets.js", r"app\static\js\tickets.js"),
        (ROOT / "app" / "static" / "css" / "tickets.css", r"app\static\css\tickets.css"),
        (ROOT / "app" / "templates" / "tickets.html", r"app\templates\tickets.html"),
    )
    for source_path, archive_name in resources:
        packaged = archive.extract(archive_name)
        assert normalize_newlines(packaged) == normalize_newlines(source_path.read_bytes())

    packaged_js = archive.extract(r"app\static\js\tickets.js")
    assert b"async function processQuickScan()" in packaged_js
    assert b"quickPrintedTickets" in packaged_js
