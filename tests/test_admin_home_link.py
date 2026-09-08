import pytest


@pytest.mark.parametrize("path", ["/admin/login", "/setup"])
def test_admin_password_pages_have_accessible_home_link(client, path):
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'class="admin-home-link"' in html
    assert 'href="/"' in html
    assert 'aria-label="Volver al inicio"' in html
    assert "Volver al inicio" in html
    assert "⌂" in html


def test_home_link_styles_are_visible_and_mobile_friendly(client):
    css = client.get("/static/css/admin.css").get_data(as_text=True)
    assert ".admin-home-link" in css
    assert "display: inline-flex" in css
    assert "@media (max-width: 600px)" in css
    assert "width: 100%" in css
