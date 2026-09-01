import pytest
from werkzeug.security import generate_password_hash

from app.models.worker import Worker
from app.extensions import db


class TestSessionEndpoint:
    def test_session_unauthenticated(self, client):
        response = client.get("/api/admin/session")
        assert response.status_code == 200
        data = response.get_json()
        assert data["authenticated"] is False
        assert "csrf_token" in data
        assert len(data["csrf_token"]) > 0

    def test_session_authenticated(self, admin_client):
        response = admin_client.get("/api/admin/session")
        assert response.status_code == 200
        data = response.get_json()
        assert data["authenticated"] is True
        assert "csrf_token" in data


class TestAdminLogin:
    def test_login_correct(self, client, app):
        app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("secret123")

        session_response = client.get("/api/admin/session")
        csrf_token = session_response.get_json()["csrf_token"]

        response = client.post(
            "/api/admin/login",
            json={"password": "secret123"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["message"] == "Login successful"

        session_check = client.get("/api/admin/session")
        assert session_check.get_json()["authenticated"] is True

    def test_login_incorrect_password(self, client, app):
        app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("secret123")

        session_response = client.get("/api/admin/session")
        csrf_token = session_response.get_json()["csrf_token"]

        response = client.post(
            "/api/admin/login",
            json={"password": "wrong-password"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Invalid password"

    def test_login_password_hash_not_configured(self, client, app):
        app.config["ADMIN_PASSWORD_HASH"] = None

        session_response = client.get("/api/admin/session")
        csrf_token = session_response.get_json()["csrf_token"]

        response = client.post(
            "/api/admin/login",
            json={"password": "anything"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 401

    def test_login_empty_password(self, client, app):
        app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("secret123")

        session_response = client.get("/api/admin/session")
        csrf_token = session_response.get_json()["csrf_token"]

        response = client.post(
            "/api/admin/login",
            json={"password": ""},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 400

    def test_login_no_json_body(self, client, app):
        app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("secret123")

        session_response = client.get("/api/admin/session")
        csrf_token = session_response.get_json()["csrf_token"]

        response = client.post(
            "/api/admin/login",
            headers={"X-CSRF-Token": csrf_token},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_login_no_csrf_token(self, client, app):
        app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("secret123")

        response = client.post(
            "/api/admin/login",
            json={"password": "secret123"},
        )
        assert response.status_code == 403

    def test_login_wrong_csrf_token(self, client, app):
        app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("secret123")

        response = client.post(
            "/api/admin/login",
            json={"password": "secret123"},
            headers={"X-CSRF-Token": "wrong-token"},
        )
        assert response.status_code == 403


class TestAdminLogout:
    def test_logout_authenticated(self, admin_client):
        response = admin_client.post(
            "/api/admin/logout",
            headers={"X-CSRF-Token": admin_client.get("/api/admin/session").get_json()["csrf_token"]},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["message"] == "Logged out"

        session_check = admin_client.get("/api/admin/session")
        assert session_check.get_json()["authenticated"] is False

    def test_logout_unauthenticated(self, client):
        session_response = client.get("/api/admin/session")
        csrf_token = session_response.get_json()["csrf_token"]

        response = client.post(
            "/api/admin/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 401

    def test_logout_no_csrf(self, admin_client):
        response = admin_client.post("/api/admin/logout")
        assert response.status_code == 403

    def test_logout_wrong_csrf(self, admin_client):
        response = admin_client.post(
            "/api/admin/logout",
            headers={"X-CSRF-Token": "wrong-token-value"},
        )
        assert response.status_code == 403

    def test_logout_idempotent(self, client, app):
        app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("secret123")

        session_response = client.get("/api/admin/session")
        csrf_token = session_response.get_json()["csrf_token"]

        client.post(
            "/api/admin/login",
            json={"password": "secret123"},
            headers={"X-CSRF-Token": csrf_token},
        )

        new_csrf = client.get("/api/admin/session").get_json()["csrf_token"]
        client.post("/api/admin/logout", headers={"X-CSRF-Token": new_csrf})

        new_csrf2 = client.get("/api/admin/session").get_json()["csrf_token"]
        response = client.post(
            "/api/admin/logout",
            headers={"X-CSRF-Token": new_csrf2},
        )
        assert response.status_code == 401


class TestAdminPageAccess:
    def test_admin_page_without_login_redirects(self, client):
        response = client.get("/admin")
        assert response.status_code == 302
        assert "/admin/login" in response.headers["Location"]

    def test_admin_login_page_renders(self, client):
        response = client.get("/admin/login")
        assert response.status_code == 200

    def test_admin_page_with_login(self, admin_client):
        response = admin_client.get("/admin")
        assert response.status_code == 200


class TestAdminAPIProtection:
    def test_list_workers_no_auth(self, client):
        response = client.get("/api/admin/workers")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_get_worker_no_auth(self, client, db_session):
        worker = Worker(barcode="AUTH001", name="Auth Test")
        db_session.add(worker)
        db_session.commit()

        response = client.get(f"/api/admin/workers/{worker.id}")
        assert response.status_code == 401

    def test_create_worker_no_auth(self, client):
        response = client.post(
            "/api/admin/workers",
            json={"name": "Test", "barcode": "AUTH002"},
        )
        assert response.status_code == 401

    def test_deactivate_worker_no_auth(self, client, db_session):
        worker = Worker(barcode="AUTH003", name="Deactivate Test")
        db_session.add(worker)
        db_session.commit()

        response = client.patch(f"/api/admin/workers/{worker.id}/deactivate")
        assert response.status_code == 401

    def test_activate_worker_no_auth(self, client, db_session):
        worker = Worker(barcode="AUTH004", name="Activate Test", active=False)
        db_session.add(worker)
        db_session.commit()

        response = client.patch(f"/api/admin/workers/{worker.id}/activate")
        assert response.status_code == 401

    def test_harvest_entries_no_auth(self, client):
        response = client.get("/api/admin/harvest-entries")
        assert response.status_code == 401

    def test_void_entry_no_auth(self, client, db_session):
        from app.models.harvest_entry import HarvestEntry
        from decimal import Decimal
        from datetime import datetime, timezone

        worker = Worker(barcode="AUTH005", name="Void Test")
        db_session.add(worker)
        db_session.flush()

        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("5.000"), created_at=datetime.now(timezone.utc))
        db_session.add(entry)
        db_session.commit()

        response = client.patch(
            f"/api/admin/harvest-entries/{entry.id}/void",
            json={"reason": "test"},
        )
        assert response.status_code == 401


class TestAdminWorkerActionsAuthenticated:
    def test_create_worker(self, admin_client):
        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.post(
            "/api/admin/workers",
            json={"name": "New Worker", "barcode": "AUTH006"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "New Worker"

    def test_deactivate_worker(self, admin_client, db_session):
        worker = Worker(barcode="AUTH007", name="Deactivate Me")
        db_session.add(worker)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            f"/api/admin/workers/{worker.id}/deactivate",
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200
        assert response.get_json()["active"] is False

    def test_activate_worker(self, admin_client, db_session):
        worker = Worker(barcode="AUTH008", name="Activate Me", active=False)
        db_session.add(worker)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            f"/api/admin/workers/{worker.id}/activate",
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200
        assert response.get_json()["active"] is True

    def test_create_worker_no_csrf(self, admin_client):
        response = admin_client.post(
            "/api/admin/workers",
            json={"name": "No CSRF", "barcode": "AUTH009"},
        )
        assert response.status_code == 403

    def test_deactivate_worker_no_csrf(self, admin_client, db_session):
        worker = Worker(barcode="AUTH010", name="No CSRF Deact")
        db_session.add(worker)
        db_session.commit()

        response = admin_client.patch(f"/api/admin/workers/{worker.id}/deactivate")
        assert response.status_code == 403

    def test_activate_worker_no_csrf(self, admin_client, db_session):
        worker = Worker(barcode="AUTH011", name="No CSRF Act", active=False)
        db_session.add(worker)
        db_session.commit()

        response = admin_client.patch(f"/api/admin/workers/{worker.id}/activate")
        assert response.status_code == 403
