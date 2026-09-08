import pytest


PAGE_PATHS = ("/history", "/reports")
API_PATHS = (
    "/api/history/daily?date=2099-01-01",
    "/api/history/assignments/999999/entries?date=2099-01-01",
    "/api/reports/harvest?start_date=2099-01-01&end_date=2099-01-02",
    "/api/reports/harvest/export?start_date=2099-01-01&end_date=2099-01-02",
)


@pytest.mark.parametrize("path", PAGE_PATHS)
def test_admin_pages_redirect_anonymous_user(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/login")
    assert "no-store" in response.headers["Cache-Control"]


@pytest.mark.parametrize("path", API_PATHS)
def test_admin_apis_reject_anonymous_user(client, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.get_json()["error"] == "Admin authentication required"
    assert "no-store" in response.headers["Cache-Control"]


@pytest.mark.parametrize("path", PAGE_PATHS)
def test_admin_pages_allow_authenticated_user(admin_client, path):
    assert admin_client.get(path).status_code == 200


def test_admin_history_and_report_apis_allow_authenticated_user(admin_client):
    history = admin_client.get("/api/history/daily?date=2099-01-01")
    report = admin_client.get(
        "/api/reports/harvest?start_date=2099-01-01&end_date=2099-01-02"
    )
    assert history.status_code == 200
    assert report.status_code == 200


def test_report_email_export_keeps_csrf_protection(admin_client):
    response = admin_client.post(
        "/api/reports/harvest/export/email",
        json={
            "email": "admin@example.com",
            "start_date": "2099-01-01",
            "end_date": "2099-01-02",
        },
    )
    assert response.status_code == 403


def test_logout_invalidates_pages_apis_and_session(admin_client):
    csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
    logout = admin_client.post(
        "/api/admin/logout", headers={"X-CSRF-Token": csrf}
    )
    assert logout.status_code == 200
    assert "no-store" in logout.headers["Cache-Control"]
    assert logout.headers["Clear-Site-Data"] == '"cache"'
    assert "session=;" in logout.headers.get("Set-Cookie", "")
    assert admin_client.get("/api/admin/session").get_json()["authenticated"] is False

    for path in PAGE_PATHS:
        response = admin_client.get(path)
        assert response.status_code == 302
        assert "no-store" in response.headers["Cache-Control"]
    for path in API_PATHS:
        response = admin_client.get(path)
        assert response.status_code == 401
        assert "no-store" in response.headers["Cache-Control"]
