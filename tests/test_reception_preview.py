import pytest
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.models.harvest_entry import HarvestEntry
from app.extensions import db
from tests.conftest import make_worker, make_worker_with_assignment


TZ = ZoneInfo("America/Chihuahua")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_product(db_session, name="Chile", rate="5.25", active=True):
    from app.models.product import Product
    product = Product(name=name, rate_per_kg=Decimal(rate), active=active)
    db_session.add(product)
    db_session.commit()
    return product


def _make_entry(db_session, worker, assignment, product=None, weight="5.000",
                created_at=None, voided=False, void_reason=None,
                voided_at=None):
    slot_num = worker.slot_number
    entry = HarvestEntry(
        worker_id=worker.id,
        weight_kg=Decimal(weight),
        voided=voided,
        void_reason=void_reason,
        worker_assignment_id=assignment.id,
        worker_slot_number_snapshot=slot_num,
        worker_barcode_snapshot=worker.barcode,
        worker_name_snapshot=assignment.person_name,
    )
    if voided and voided_at is None:
        entry.voided_at = datetime.now(timezone.utc)
    if product is not None:
        entry.product_id = product.id
        entry.product_name_snapshot = product.name
        entry.rate_per_kg_snapshot = Decimal(str(product.rate_per_kg))
        amount = (Decimal(weight) * Decimal(str(product.rate_per_kg))).quantize(
            Decimal("0.01")
        )
        entry.amount_mxn = amount

    if created_at is not None:
        entry.created_at = created_at

    db_session.add(entry)
    db_session.commit()
    return entry


# ---------------------------------------------------------------------------
# 1. Accessible without authentication
# ---------------------------------------------------------------------------

class TestRecentEndpointAccess:
    def test_no_auth_required(self, client, db_session):
        resp = client.get("/api/harvest/recent")
        assert resp.status_code == 200

    def test_returns_movements_key(self, client, db_session):
        resp = client.get("/api/harvest/recent")
        data = resp.get_json()
        assert "movements" in data
        assert isinstance(data["movements"], list)


# ---------------------------------------------------------------------------
# 2. Day calculated in HARVEST_TIMEZONE
# ---------------------------------------------------------------------------

class TestOperationalDayCalculation:
    def test_uses_harvest_timezone(self, client, db_session):
        now_local = datetime.now(TZ)
        entry_time = now_local.replace(hour=12, minute=0, second=0)
        entry_utc = entry_time.astimezone(timezone.utc)

        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)
        _make_entry(db_session, worker, assignment, product=product, created_at=entry_utc)

        resp = client.get("/api/harvest/recent")
        data = resp.get_json()
        assert len(data["movements"]) == 1


# ---------------------------------------------------------------------------
# 3. UTC range boundaries (inclusive start, exclusive end)
# ---------------------------------------------------------------------------

class TestUtcRangeBoundaries:
    def test_start_inclusive(self, client, db_session):
        today_local = datetime.now(TZ).date()
        start_utc = datetime.combine(today_local, time.min, tzinfo=TZ).astimezone(timezone.utc)

        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)
        _make_entry(db_session, worker, assignment, product=product, created_at=start_utc)

        resp = client.get("/api/harvest/recent")
        data = resp.get_json()
        assert len(data["movements"]) == 1

    def test_end_exclusive(self, client, db_session):
        today_local = datetime.now(TZ).date()
        end_utc = datetime.combine(today_local + timedelta(days=1), time.min, tzinfo=TZ).astimezone(timezone.utc)

        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)
        _make_entry(db_session, worker, assignment, product=product, created_at=end_utc)

        resp = client.get("/api/harvest/recent")
        data = resp.get_json()
        assert len(data["movements"]) == 0

    def test_yesterday_excluded(self, client, db_session):
        today_local = datetime.now(TZ).date()
        yesterday = today_local - timedelta(days=1)
        yesterday_midnight = datetime.combine(yesterday, time(23, 59, 59), tzinfo=TZ)
        yesterday_utc = yesterday_midnight.astimezone(timezone.utc)

        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)
        _make_entry(db_session, worker, assignment, product=product, created_at=yesterday_utc)

        resp = client.get("/api/harvest/recent")
        data = resp.get_json()
        assert len(data["movements"]) == 0


# ---------------------------------------------------------------------------
# 4. Includes voided movements
# ---------------------------------------------------------------------------

class TestIncludesVoided:
    def test_voided_included(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)
        _make_entry(db_session, worker, assignment, product=product, voided=True, void_reason="Error")

        resp = client.get("/api/harvest/recent")
        data = resp.get_json()
        assert len(data["movements"]) == 1
        assert data["movements"][0]["voided"] is True


# ---------------------------------------------------------------------------
# 5. Order: created_at DESC, id DESC
# ---------------------------------------------------------------------------

class TestOrdering:
    def test_created_at_desc(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)

        now_utc = datetime.now(timezone.utc)
        e1 = _make_entry(db_session, worker, assignment, product=product, created_at=now_utc - timedelta(seconds=10))
        e2 = _make_entry(db_session, worker, assignment, product=product, created_at=now_utc)

        resp = client.get("/api/harvest/recent")
        data = resp.get_json()
        ids = [m["id"] for m in data["movements"]]
        assert ids == [e2.id, e1.id]

    def test_id_desc_tiebreak(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)

        now_utc = datetime.now(timezone.utc)
        e1 = _make_entry(db_session, worker, assignment, product=product, created_at=now_utc)
        e2 = _make_entry(db_session, worker, assignment, product=product, created_at=now_utc)

        resp = client.get("/api/harvest/recent")
        data = resp.get_json()
        ids = [m["id"] for m in data["movements"]]
        assert ids == [e2.id, e1.id]


# ---------------------------------------------------------------------------
# 6. Limit: default 10
# ---------------------------------------------------------------------------

class TestDefaultLimit:
    def test_default_limit_10(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)

        now_utc = datetime.now(timezone.utc)
        for i in range(15):
            _make_entry(
                db_session, worker, assignment, product=product,
                weight=f"{i + 1}.000",
                created_at=now_utc + timedelta(seconds=i),
            )

        resp = client.get("/api/harvest/recent")
        data = resp.get_json()
        assert len(data["movements"]) == 10


# ---------------------------------------------------------------------------
# 7. Limit: custom valid
# ---------------------------------------------------------------------------

class TestCustomLimit:
    def test_custom_limit(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)

        now_utc = datetime.now(timezone.utc)
        for i in range(5):
            _make_entry(
                db_session, worker, assignment, product=product,
                weight=f"{i + 1}.000",
                created_at=now_utc + timedelta(seconds=i),
            )

        resp = client.get("/api/harvest/recent?limit=5")
        data = resp.get_json()
        assert len(data["movements"]) == 5


# ---------------------------------------------------------------------------
# 8. Limit: max 20
# ---------------------------------------------------------------------------

class TestMaxLimit:
    def test_limit_20_accepted(self, client, db_session):
        resp = client.get("/api/harvest/recent?limit=20")
        assert resp.status_code == 200

    def test_limit_21_rejected(self, client, db_session):
        resp = client.get("/api/harvest/recent?limit=21")
        assert resp.status_code == 400
        assert "limit" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# 9. Invalid limit values
# ---------------------------------------------------------------------------

class TestInvalidLimit:
    @pytest.mark.parametrize("bad_limit", [
        "0", "-1", "abc", "1.5", "10 ", " 5", "1e1",
        "true", "false", "", " ",
    ])
    def test_invalid_limit_returns_400(self, client, bad_limit):
        resp = client.get(f"/api/harvest/recent?limit={bad_limit}")
        assert resp.status_code == 400
        assert "limit" in resp.get_json()["error"]

    def test_bool_limit_rejected(self, client):
        resp = client.get("/api/harvest/recent?limit=true")
        assert resp.status_code == 400

    def test_no_limit_param_defaults_to_10(self, client, db_session):
        resp = client.get("/api/harvest/recent")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 10. Empty response
# ---------------------------------------------------------------------------

class TestEmptyResponse:
    def test_empty_when_no_movements(self, client, db_session):
        resp = client.get("/api/harvest/recent")
        data = resp.get_json()
        assert data["movements"] == []


# ---------------------------------------------------------------------------
# 11. Only public fields
# ---------------------------------------------------------------------------

class TestPublicFields:
    def test_only_allowed_fields(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)
        _make_entry(db_session, worker, assignment, product=product)

        resp = client.get("/api/harvest/recent")
        m = resp.get_json()["movements"][0]

        expected_keys = {
            "id", "time", "worker", "worker_assignment_id",
            "product_name", "weight_kg", "rate_per_kg", "amount_mxn", "voided",
        }
        assert set(m.keys()) == expected_keys
        assert set(m["worker"].keys()) == {"name", "barcode", "slot_number", "slot_label"}

    def test_no_internal_fields(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)
        _make_entry(db_session, worker, assignment, product=product)

        resp = client.get("/api/harvest/recent")
        raw = resp.data.decode()
        for field in ["worker_id", "product_id", "void_reason", "voided_at", "created_at"]:
            assert field not in raw


# ---------------------------------------------------------------------------
# 12. Format of weight, rate, amount
# ---------------------------------------------------------------------------

class TestFormatExact:
    def test_weight_three_decimals(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)
        _make_entry(db_session, worker, assignment, product=product, weight="12.345")

        resp = client.get("/api/harvest/recent")
        m = resp.get_json()["movements"][0]
        assert m["weight_kg"] == "12.345"

    def test_rate_two_decimals(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session, rate="3.00")
        _make_entry(db_session, worker, assignment, product=product)

        resp = client.get("/api/harvest/recent")
        m = resp.get_json()["movements"][0]
        assert m["rate_per_kg"] == "3.00"

    def test_amount_two_decimals(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session, rate="3.00")
        _make_entry(db_session, worker, assignment, product=product, weight="2.000")

        resp = client.get("/api/harvest/recent")
        m = resp.get_json()["movements"][0]
        assert m["amount_mxn"] == "6.00"


# ---------------------------------------------------------------------------
# 13. Local time with day boundary crossing
# ---------------------------------------------------------------------------

class TestLocalTimeFormatting:
    def test_time_is_local_to_harvest_tz(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)

        today_local = datetime.now(TZ).date()
        local_noon = datetime.combine(today_local, time(12, 30, 45), tzinfo=TZ)
        utc_noon = local_noon.astimezone(timezone.utc)

        _make_entry(db_session, worker, assignment, product=product, created_at=utc_noon)

        resp = client.get("/api/harvest/recent")
        m = resp.get_json()["movements"][0]
        assert m["time"] == "12:30:45"


# ---------------------------------------------------------------------------
# 14. Legacy movement returns nulls
# ---------------------------------------------------------------------------

class TestLegacyNulls:
    def test_legacy_product_fields_null(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        _make_entry(db_session, worker, assignment)

        resp = client.get("/api/harvest/recent")
        m = resp.get_json()["movements"][0]
        assert m["product_name"] is None
        assert m["rate_per_kg"] is None
        assert m["amount_mxn"] is None


# ---------------------------------------------------------------------------
# 15. Uses snapshots, not live product data
# ---------------------------------------------------------------------------

class TestSnapshotIndependence:
    def test_shows_snapshot_not_product(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="Original", rate="5.00")
        entry = _make_entry(db_session, worker, assignment, product=product, weight="2.000")

        entry.product_name_snapshot = "Original"
        entry.rate_per_kg_snapshot = Decimal("5.00")
        entry.amount_mxn = Decimal("10.00")
        db_session.commit()

        product.name = "Changed"
        product.rate_per_kg = Decimal("99.00")
        db_session.commit()

        resp = client.get("/api/harvest/recent")
        m = resp.get_json()["movements"][0]
        assert m["product_name"] == "Original"
        assert m["rate_per_kg"] == "5.00"
        assert m["amount_mxn"] == "10.00"

    def test_includes_even_if_product_inactive(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session)
        product = _create_product(db_session)
        _make_entry(db_session, worker, assignment, product=product)

        product.active = False
        db_session.commit()

        resp = client.get("/api/harvest/recent")
        data = resp.get_json()
        assert len(data["movements"]) == 1


# ---------------------------------------------------------------------------
# 16. Uses worker snapshots, not live worker data
# ---------------------------------------------------------------------------

class TestWorkerSnapshotIndependence:
    def test_shows_snapshot_not_worker(self, client, db_session):
        worker, assignment = make_worker_with_assignment(db_session, person_name="Original Name")
        product = _create_product(db_session)
        _make_entry(db_session, worker, assignment, product=product)

        assignment.person_name = "Changed Name"
        db_session.commit()

        resp = client.get("/api/harvest/recent")
        m = resp.get_json()["movements"][0]
        assert m["worker"]["name"] == "Original Name"
        assert m["worker"]["barcode"] == worker.barcode
        assert m["worker"]["slot_number"] == worker.slot_number
        assert m["worker"]["slot_label"] == f"Trabajador {worker.slot_number:03d}"
        assert m["worker_assignment_id"] == assignment.id


# ---------------------------------------------------------------------------
# 17. Cache-Control header
# ---------------------------------------------------------------------------

class TestCacheControl:
    def test_no_store_header(self, client, db_session):
        resp = client.get("/api/harvest/recent")
        assert resp.headers.get("Cache-Control") == "no-store"


# ---------------------------------------------------------------------------
# 18. HTML structure
# ---------------------------------------------------------------------------

class TestHtmlStructure:
    def test_section_exists(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert 'id="recent-movements"' in html
        assert "Movimientos recientes" in html
        assert 'id="movements-content"' in html
        assert 'id="refresh-movements"' in html
        assert 'aria-live="polite"' in html


# ---------------------------------------------------------------------------
# 19. JS evidence (consolidated)
# ---------------------------------------------------------------------------

class TestJsEvidence:
    def test_core_features_present(self, client):
        resp = client.get("/static/js/reception.js")
        js = resp.data.decode()

        assert "loadRecentMovements" in js
        assert "isLoadingMovements" in js
        assert "startMovementsPolling" in js
        assert "stopMovementsPolling" in js
        assert "visibilitychange" in js
        assert "15000" in js
        assert "escapeHtml" in js
        assert "loadRecentMovements()" in js
        assert "/api/harvest/recent" in js
        assert "slot_label" in js

    def test_no_void_controls(self, client):
        resp = client.get("/static/js/reception.js")
        js = resp.data.decode()
        assert "void-entry" not in js
        assert "voidEntry" not in js
        assert "anular" not in js.lower()
        assert "unvoid" not in js.lower()
        assert "restore-entry" not in js
