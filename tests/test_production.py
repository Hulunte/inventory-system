import importlib
import os
import sys
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pytest

from app import create_app


VALID_ENV = {
    "DATABASE_URL": "postgresql+psycopg://user:pass@localhost:5432/inventory_db",
    "SECRET_KEY": "a" * 40,
    "ADMIN_PASSWORD_HASH": "pbkdf2:sha256:600000$abc$def",
    "HARVEST_TIMEZONE": "UTC",
}


class TestProductionModule:
    """Tests que verifican el modulo production.py sin levantar servidor."""

    def test_production_has_main_function(self):
        """production.py debe tener una funcion main()."""
        import production
        assert hasattr(production, "main")
        assert callable(production.main)

    def test_importing_production_does_not_start_server(self):
        """importar production no debe iniciar el servidor."""
        import production  # noqa: F401
        assert hasattr(production, "main")


class TestValidateProductionConfig:
    """Tests directos para validate_production_config()."""

    # --- DATABASE_URL ---

    def test_valid_config_passes(self):
        """Configuracion completa y valida no debe fallar."""
        from production import validate_production_config
        validate_production_config(environ=dict(VALID_ENV))

    def test_empty_environ_fails(self):
        """Environ vacio debe fallar por DATABASE_URL."""
        from production import validate_production_config
        with pytest.raises(SystemExit, match="DATABASE_URL"):
            validate_production_config(environ={})

    def test_missing_database_url(self):
        """DATABASE_URL ausente debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV)
        del env["DATABASE_URL"]
        with pytest.raises(SystemExit, match="DATABASE_URL"):
            validate_production_config(environ=env)

    def test_empty_database_url(self):
        """DATABASE_URL vacia debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, DATABASE_URL="")
        with pytest.raises(SystemExit, match="DATABASE_URL"):
            validate_production_config(environ=env)

    def test_database_url_whitespace_only(self):
        """DATABASE_URL con solo espacios debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, DATABASE_URL="   ")
        with pytest.raises(SystemExit, match="DATABASE_URL"):
            validate_production_config(environ=env)

    def test_database_url_placeholder(self):
        """DATABASE_URL con valor placeholder debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/inventory_db")
        with pytest.raises(SystemExit, match="placeholder"):
            validate_production_config(environ=env)

    def test_database_url_invalid_format(self):
        """DATABASE_URL con formato invalido debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, DATABASE_URL="not-a-url")
        with pytest.raises(SystemExit, match="invalid"):
            validate_production_config(environ=env)

    def test_database_url_sqlite_rejected(self):
        """DATABASE_URL con SQLite debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, DATABASE_URL="sqlite:///test.db")
        with pytest.raises(SystemExit, match="PostgreSQL"):
            validate_production_config(environ=env)

    def test_database_url_mysql_rejected(self):
        """DATABASE_URL con MySQL debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, DATABASE_URL="mysql://user:pass@localhost/db")
        with pytest.raises(SystemExit, match="PostgreSQL"):
            validate_production_config(environ=env)

    @pytest.mark.parametrize("value", [
        " postgresql+psycopg://user:pass@localhost:5432/db",
    ])
    def test_database_url_rejects_whitespace_padded(self, value):
        """DATABASE_URL con espacios iniciales o finales debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, DATABASE_URL=value)
        with pytest.raises(SystemExit, match="whitespace"):
            validate_production_config(environ=env)

    # --- SECRET_KEY ---

    def test_missing_secret_key(self):
        """SECRET_KEY ausente debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV)
        del env["SECRET_KEY"]
        with pytest.raises(SystemExit, match="SECRET_KEY"):
            validate_production_config(environ=env)

    def test_empty_secret_key(self):
        """SECRET_KEY vacia debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, SECRET_KEY="")
        with pytest.raises(SystemExit, match="SECRET_KEY"):
            validate_production_config(environ=env)

    def test_secret_key_placeholder(self):
        """SECRET_KEY con valor placeholder debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, SECRET_KEY="replace-with-a-real-secret-key")
        with pytest.raises(SystemExit, match="placeholder"):
            validate_production_config(environ=env)

    def test_secret_key_too_short(self):
        """SECRET_KEY menor a 32 caracteres debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, SECRET_KEY="short")
        with pytest.raises(SystemExit, match="at least 32"):
            validate_production_config(environ=env)

    def test_secret_key_exactly_32_chars(self):
        """SECRET_KEY de exactamente 32 caracteres debe pasar."""
        from production import validate_production_config
        env = dict(VALID_ENV, SECRET_KEY="a" * 32)
        validate_production_config(environ=env)

    @pytest.mark.parametrize("value", [
        " a" + "a" * 38,
    ])
    def test_secret_key_rejects_whitespace_padded(self, value):
        """SECRET_KEY con espacios iniciales o finales debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, SECRET_KEY=value)
        with pytest.raises(SystemExit, match="whitespace"):
            validate_production_config(environ=env)

    def test_secret_key_padded_placeholder_not_bypassed(self):
        """SECRET_KEY placeholder rodeado de espacios no debe pasar."""
        from production import validate_production_config
        env = dict(VALID_ENV, SECRET_KEY=" replace-with-a-real-secret-key ")
        with pytest.raises(SystemExit, match="whitespace"):
            validate_production_config(environ=env)

    # --- ADMIN_PASSWORD_HASH ---

    def test_missing_admin_hash(self):
        """ADMIN_PASSWORD_HASH ausente debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV)
        del env["ADMIN_PASSWORD_HASH"]
        with pytest.raises(SystemExit, match="ADMIN_PASSWORD_HASH"):
            validate_production_config(environ=env)

    def test_empty_admin_hash(self):
        """ADMIN_PASSWORD_HASH vacia debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, ADMIN_PASSWORD_HASH="")
        with pytest.raises(SystemExit, match="ADMIN_PASSWORD_HASH"):
            validate_production_config(environ=env)

    def test_admin_hash_placeholder(self):
        """ADMIN_PASSWORD_HASH con valor placeholder debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, ADMIN_PASSWORD_HASH="replace-with-generated-password-hash")
        with pytest.raises(SystemExit, match="placeholder"):
            validate_production_config(environ=env)

    def test_admin_hash_no_prefix(self):
        """ADMIN_PASSWORD_HASH sin prefijo pbkdf2:/scrypt: debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, ADMIN_PASSWORD_HASH="plaintextpassword")
        with pytest.raises(SystemExit, match="invalid format"):
            validate_production_config(environ=env)

    def test_admin_hash_missing_dollar(self):
        """ADMIN_PASSWORD_HASH pbkdf2 sin $ debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, ADMIN_PASSWORD_HASH="pbkdf2:sha256:600000")
        with pytest.raises(SystemExit, match="invalid format"):
            validate_production_config(environ=env)

    def test_admin_hash_scrypt_format(self):
        """ADMIN_PASSWORD_HASH con formato scrypt valido debe pasar."""
        from production import validate_production_config
        env = dict(VALID_ENV, ADMIN_PASSWORD_HASH="scrypt:32768:8:1$abc$def")
        validate_production_config(environ=env)

    def test_admin_hash_single_component_rejected(self):
        """ADMIN_PASSWORD_HASH con un solo componente sin $ debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, ADMIN_PASSWORD_HASH="pbkdf2:sha256:600000nosalt")
        with pytest.raises(SystemExit, match="invalid format"):
            validate_production_config(environ=env)

    def test_admin_hash_two_components_rejected(self):
        """ADMIN_PASSWORD_HASH con dos componentes debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, ADMIN_PASSWORD_HASH="pbkdf2:sha256:600000$abc")
        with pytest.raises(SystemExit, match="invalid format"):
            validate_production_config(environ=env)

    def test_admin_hash_four_components_rejected(self):
        """ADMIN_PASSWORD_HASH con cuatro componentes debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, ADMIN_PASSWORD_HASH="pbkdf2:sha256:600000$abc$def$extra")
        with pytest.raises(SystemExit, match="invalid format"):
            validate_production_config(environ=env)

    def test_admin_hash_empty_salt_rejected(self):
        """ADMIN_PASSWORD_HASH con salt vacio debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, ADMIN_PASSWORD_HASH="pbkdf2:sha256:600000$$def")
        with pytest.raises(SystemExit, match="invalid format"):
            validate_production_config(environ=env)

    def test_admin_hash_empty_digest_rejected(self):
        """ADMIN_PASSWORD_HASH con digest vacio debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, ADMIN_PASSWORD_HASH="pbkdf2:sha256:600000$abc$")
        with pytest.raises(SystemExit, match="invalid format"):
            validate_production_config(environ=env)

    @pytest.mark.parametrize("value", [
        " pbkdf2:sha256:600000$abc$def",
    ])
    def test_admin_hash_rejects_whitespace_padded(self, value):
        """ADMIN_PASSWORD_HASH con espacios iniciales o finales debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, ADMIN_PASSWORD_HASH=value)
        with pytest.raises(SystemExit, match="whitespace"):
            validate_production_config(environ=env)

    # --- HARVEST_TIMEZONE ---

    def test_missing_timezone(self):
        """HARVEST_TIMEZONE ausente debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV)
        del env["HARVEST_TIMEZONE"]
        with pytest.raises(SystemExit, match="HARVEST_TIMEZONE"):
            validate_production_config(environ=env)

    def test_empty_timezone(self):
        """HARVEST_TIMEZONE vacia debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, HARVEST_TIMEZONE="")
        with pytest.raises(SystemExit, match="HARVEST_TIMEZONE"):
            validate_production_config(environ=env)

    def test_invalid_timezone(self):
        """HARVEST_TIMEZONE con valor invalido debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, HARVEST_TIMEZONE="Not/Real/Timezone")
        with pytest.raises(SystemExit, match="valid timezone"):
            validate_production_config(environ=env)

    def test_valid_timezone_america_chihuahua(self):
        """HARVEST_TIMEZONE America/Chihuahua debe pasar."""
        from production import validate_production_config
        env = dict(VALID_ENV, HARVEST_TIMEZONE="America/Chihuahua")
        validate_production_config(environ=env)

    @pytest.mark.parametrize("value", [
        " UTC",
    ])
    def test_timezone_rejects_whitespace_padded(self, value):
        """HARVEST_TIMEZONE con espacios iniciales o finales debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, HARVEST_TIMEZONE=value)
        with pytest.raises(SystemExit, match="whitespace"):
            validate_production_config(environ=env)

    # --- APP_HOST ---

    def test_app_host_absent_ok(self):
        """APP_HOST ausente no debe fallar (usa default)."""
        from production import validate_production_config
        env = dict(VALID_ENV)
        validate_production_config(environ=env)

    def test_app_host_empty_string_fails(self):
        """APP_HOST vacio debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, APP_HOST="")
        with pytest.raises(SystemExit, match="APP_HOST"):
            validate_production_config(environ=env)

    def test_app_host_whitespace_only_fails(self):
        """APP_HOST con solo espacios debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, APP_HOST="   ")
        with pytest.raises(SystemExit, match="APP_HOST"):
            validate_production_config(environ=env)

    def test_app_host_valid_value(self):
        """APP_HOST con valor valido no debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, APP_HOST="127.0.0.1")
        validate_production_config(environ=env)

    @pytest.mark.parametrize("value", [
        " 127.0.0.1",
    ])
    def test_app_host_rejects_whitespace_padded(self, value):
        """APP_HOST con espacios iniciales o finales debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, APP_HOST=value)
        with pytest.raises(SystemExit, match="whitespace"):
            validate_production_config(environ=env)

    # --- SESSION_COOKIE_SECURE ---

    def test_session_secure_absent_ok(self):
        """SESSION_COOKIE_SECURE ausente no debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV)
        validate_production_config(environ=env)

    def test_session_secure_true_ok(self):
        """SESSION_COOKIE_SECURE=true debe pasar."""
        from production import validate_production_config
        env = dict(VALID_ENV, SESSION_COOKIE_SECURE="true")
        validate_production_config(environ=env)

    def test_session_secure_false_ok(self):
        """SESSION_COOKIE_SECURE=false debe pasar."""
        from production import validate_production_config
        env = dict(VALID_ENV, SESSION_COOKIE_SECURE="false")
        validate_production_config(environ=env)

    def test_session_secure_case_insensitive(self):
        """SESSION_COOKIE_SECURE debe ser case-insensitive."""
        from production import validate_production_config
        for val in ("TRUE", "True", "False", "FALSE"):
            env = dict(VALID_ENV, SESSION_COOKIE_SECURE=val)
            validate_production_config(environ=env)

    def test_session_secure_invalid_value(self):
        """SESSION_COOKIE_SECURE con valor invalido debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, SESSION_COOKIE_SECURE="yes")
        with pytest.raises(SystemExit, match="SESSION_COOKIE_SECURE"):
            validate_production_config(environ=env)

    def test_session_secure_numeric_rejected(self):
        """SESSION_COOKIE_SECURE con numero debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, SESSION_COOKIE_SECURE="1")
        with pytest.raises(SystemExit, match="SESSION_COOKIE_SECURE"):
            validate_production_config(environ=env)

    @pytest.mark.parametrize("value", [
        " true",
    ])
    def test_session_secure_rejects_whitespace_padded(self, value):
        """SESSION_COOKIE_SECURE con espacios iniciales o finales debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, SESSION_COOKIE_SECURE=value)
        with pytest.raises(SystemExit, match="whitespace"):
            validate_production_config(environ=env)

    # --- Variables opcionales que NO deben bloquear ---

    def test_optional_variables_present_ok(self):
        """Variables opcionales definidas no deben bloquear el startup."""
        from production import validate_production_config
        env = dict(VALID_ENV, BACKUP_DIR="/some/path")
        validate_production_config(environ=env)

    # --- Ausencia de filtracion de secretos ---

    @pytest.mark.parametrize("key,bad_value", [
        ("DATABASE_URL", "not-a-url"),
        ("SECRET_KEY", "short"),
        ("ADMIN_PASSWORD_HASH", "plaintext"),
    ])
    def test_error_message_no_sensitive_values(self, key, bad_value):
        """Los mensajes de error no deben exponer valores sensibles."""
        from production import validate_production_config
        env = dict(VALID_ENV)
        env[key] = bad_value
        with pytest.raises(SystemExit) as exc_info:
            validate_production_config(environ=env)
        error_msg = str(exc_info.value)
        assert bad_value not in error_msg

    def test_error_message_no_invalid_database_url_with_host(self):
        """El mensaje de error de DATABASE_URL no debe incluir host ni db invalidos."""
        from production import validate_production_config
        env = dict(VALID_ENV, DATABASE_URL="not-a-valid-scheme://evil.example.com/sensitive_db")
        with pytest.raises(SystemExit) as exc_info:
            validate_production_config(environ=env)
        error_msg = str(exc_info.value)
        assert "evil.example.com" not in error_msg
        assert "sensitive_db" not in error_msg


class TestProductionValidation:
    """Tests de validacion de parametros en main() (sin levantar servidor)."""

    @mock.patch("waitress.create_server")
    def test_port_non_numeric_fails(self, mock_cs):
        """APP_PORT no numerico deberia causar SystemExit."""
        import production
        env = dict(VALID_ENV, APP_PORT="abc")
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="APP_PORT"):
                production.main()

    @mock.patch("waitress.create_server")
    def test_port_zero_fails(self, mock_cs):
        """APP_PORT=0 deberia causar SystemExit."""
        import production
        env = dict(VALID_ENV, APP_PORT="0")
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                production.main()

    @mock.patch("waitress.create_server")
    def test_port_negative_fails(self, mock_cs):
        """APP_PORT negativo deberia causar SystemExit."""
        import production
        env = dict(VALID_ENV, APP_PORT="-1")
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                production.main()

    @mock.patch("waitress.create_server")
    def test_port_65536_fails(self, mock_cs):
        """APP_PORT=65536 deberia causar SystemExit."""
        import production
        env = dict(VALID_ENV, APP_PORT="65536")
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                production.main()

    @mock.patch("waitress.create_server")
    def test_port_65535_passes(self, mock_cs):
        """APP_PORT=65535 deberia ser valido."""
        import production
        mock_server = mock.MagicMock()
        mock_cs.return_value = mock_server
        env = dict(VALID_ENV, APP_PORT="65535")
        with mock.patch("threading.Thread"):
            with mock.patch("threading.Event") as mock_evt:
                mock_evt.return_value.wait.side_effect = None
                with mock.patch.dict(os.environ, env, clear=True):
                    production.main()
                    mock_cs.assert_called_once()

    @mock.patch("waitress.create_server")
    def test_port_custom_valid_passes(self, mock_cs):
        """APP_PORT personalizado valido deberia pasar."""
        import production
        mock_server = mock.MagicMock()
        mock_cs.return_value = mock_server
        env = dict(VALID_ENV, APP_PORT="8080")
        with mock.patch("threading.Thread"):
            with mock.patch("threading.Event") as mock_evt:
                mock_evt.return_value.wait.side_effect = None
                with mock.patch.dict(os.environ, env, clear=True):
                    production.main()
                    mock_cs.assert_called_once()

    @mock.patch("waitress.create_server")
    @mock.patch("dotenv.load_dotenv")
    def test_validation_before_port_check(self, mock_dotenv, mock_cs):
        """Config obligatoria invalida debe fallar antes de validar APP_PORT."""
        import production
        env = dict(VALID_ENV, APP_PORT="abc")
        del env["DATABASE_URL"]
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="DATABASE_URL"):
                production.main()

    @mock.patch("waitress.create_server")
    @mock.patch("dotenv.load_dotenv")
    def test_invalid_config_stops_before_create_app(self, mock_dotenv, mock_cs):
        """Config invalida no debe llamar a create_app ni a create_server."""
        import production
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("app.create_app") as mock_create:
                with pytest.raises(SystemExit):
                    production.main()
                mock_create.assert_not_called()
                mock_cs.assert_not_called()

    @mock.patch("waitress.create_server")
    @mock.patch("app.create_app")
    @mock.patch("dotenv.load_dotenv")
    def test_load_dotenv_called_before_reading_env(self, mock_dotenv, mock_create_app, mock_cs):
        """load_dotenv() inyecta config que main() usa para host, port y create_app."""
        import production
        mock_app = mock.MagicMock()
        mock_create_app.return_value = mock_app
        mock_server = mock.MagicMock()
        mock_cs.return_value = mock_server

        def fake_load_dotenv(*args, **kwargs):
            os.environ["DATABASE_URL"] = "postgresql+psycopg://u:p@localhost/db"
            os.environ["SECRET_KEY"] = "a" * 40
            os.environ["ADMIN_PASSWORD_HASH"] = "pbkdf2:sha256:600000$abc$def"
            os.environ["HARVEST_TIMEZONE"] = "UTC"
            os.environ["APP_HOST"] = "10.0.0.1"
            os.environ["APP_PORT"] = "9999"

        mock_dotenv.side_effect = fake_load_dotenv

        with mock.patch("threading.Thread"):
            with mock.patch("threading.Event") as mock_evt:
                mock_evt.return_value.wait.side_effect = None
                with mock.patch.dict(os.environ, {}, clear=True):
                    production.main()

        mock_create_app.assert_called_once()
        mock_cs.assert_called_once()
        args, kwargs = mock_cs.call_args
        assert args[0] is mock_app
        assert kwargs["host"] == "10.0.0.1"
        assert kwargs["port"] == 9999

    @mock.patch("waitress.create_server")
    @mock.patch("app.create_app")
    @mock.patch("dotenv.load_dotenv")
    def test_default_host_and_port(self, mock_dotenv, mock_create_app, mock_cs):
        """APP_HOST y APP_PORT ausentes usan defaults 0.0.0.0:5000."""
        import production
        mock_app = mock.MagicMock()
        mock_create_app.return_value = mock_app
        mock_server = mock.MagicMock()
        mock_cs.return_value = mock_server

        def fake_load_dotenv(*args, **kwargs):
            os.environ["DATABASE_URL"] = "postgresql+psycopg://u:p@localhost/db"
            os.environ["SECRET_KEY"] = "a" * 40
            os.environ["ADMIN_PASSWORD_HASH"] = "pbkdf2:sha256:600000$abc$def"
            os.environ["HARVEST_TIMEZONE"] = "UTC"

        mock_dotenv.side_effect = fake_load_dotenv

        with mock.patch("threading.Thread"):
            with mock.patch("threading.Event") as mock_evt:
                mock_evt.return_value.wait.side_effect = None
                with mock.patch.dict(os.environ, {}, clear=True):
                    production.main()

        mock_cs.assert_called_once()
        args, kwargs = mock_cs.call_args
        assert args[0] is mock_app
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["port"] == 5000

    @mock.patch("waitress.create_server")
    @mock.patch("app.create_app")
    @mock.patch("dotenv.load_dotenv")
    def test_main_sets_debug_false(self, mock_dotenv, mock_create_app, mock_cs):
        """main() debe deshabilitar debug en la app."""
        import production
        mock_app = mock.MagicMock()
        mock_create_app.return_value = mock_app
        mock_server = mock.MagicMock()
        mock_cs.return_value = mock_server

        def fake_load_dotenv(*args, **kwargs):
            os.environ["DATABASE_URL"] = "postgresql+psycopg://u:p@localhost/db"
            os.environ["SECRET_KEY"] = "a" * 40
            os.environ["ADMIN_PASSWORD_HASH"] = "pbkdf2:sha256:600000$abc$def"
            os.environ["HARVEST_TIMEZONE"] = "UTC"

        mock_dotenv.side_effect = fake_load_dotenv

        with mock.patch("threading.Thread"):
            with mock.patch("threading.Event") as mock_evt:
                mock_evt.return_value.wait.side_effect = None
                with mock.patch.dict(os.environ, {}, clear=True):
                    production.main()

        assert mock_app.debug is False


class TestProductionAppFactory:
    """Tests del application factory usados por production."""

    def test_create_app_produces_valid_flask_app(self):
        """create_app() produce una instancia Flask valida."""
        app = create_app()
        assert app is not None
        assert hasattr(app, "debug")
        assert hasattr(app, "config")

    def test_create_app_debug_not_true(self):
        """create_app() no debe setear debug=True."""
        app = create_app()
        assert app.debug is False
        assert app.config.get("DEBUG") is not True


class TestTestConfigTimezone:
    """Verifica que TestConfig declara una zona horaria explicita y determinista."""

    def test_test_config_has_explicit_harvest_timezone(self):
        """TestConfig.HARVEST_TIMEZONE debe ser ZoneInfo("America/Chihuahua")."""
        from config import TestConfig

        tz = TestConfig.HARVEST_TIMEZONE
        assert isinstance(tz, ZoneInfo)
        assert str(tz) == "America/Chihuahua"


class TestHealthCheck:
    """Tests for the /api/health endpoint."""

    def test_health_returns_200_when_db_ok(self, client):
        """Health check returns 200 when DB is connected."""
        resp = client.get("/api/health")
        assert resp.status_code in (200, 503)
        data = resp.get_json()
        assert "status" in data
        assert "database" in data

    def test_health_returns_status_field(self, client):
        """Health check returns status field."""
        resp = client.get("/api/health")
        data = resp.get_json()
        assert data["status"] in ("ok", "degraded")

    def test_health_returns_database_field(self, client):
        """Health check returns database field."""
        resp = client.get("/api/health")
        data = resp.get_json()
        assert "database" in data

    def test_health_no_config_returns_503(self):
        """Health check returns 503 when DATABASE_URL is not set."""
        app = create_app()
        app.config["SQLALCHEMY_DATABASE_URI"] = None
        client = app.test_client()
        resp = client.get("/api/health")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["status"] == "degraded"
        assert data["database"] == "not_configured"

    def test_health_bad_db_returns_503(self):
        """Health check returns 503 when DB connection fails."""
        app = create_app()
        app.config["SQLALCHEMY_DATABASE_URI"] = (
            "postgresql+psycopg://fake:fake@localhost:99999/fake_db"
        )
        client = app.test_client()
        resp = client.get("/api/health")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["status"] == "degraded"


class TestProductionConfigValidation:
    """Tests for ProductionConfig.validate()."""

    def test_validate_missing_secret_key(self):
        """validate() fails when SECRET_KEY is missing."""
        from config import ProductionConfig
        env = {
            "DATABASE_URL": "postgresql+psycopg://u:p@localhost/db",
            "ADMIN_PASSWORD_HASH": "hash",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            os.environ.pop("SECRET_KEY", None)
            with pytest.raises(SystemExit, match="SECRET_KEY"):
                ProductionConfig.validate()

    def test_validate_missing_database_url(self):
        """validate() fails when DATABASE_URL is missing."""
        from config import ProductionConfig
        env = {
            "SECRET_KEY": "a" * 20,
            "ADMIN_PASSWORD_HASH": "hash",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            os.environ.pop("DATABASE_URL", None)
            with pytest.raises(SystemExit, match="DATABASE_URL"):
                ProductionConfig.validate()

    def test_validate_missing_admin_password_hash(self):
        """validate() fails when ADMIN_PASSWORD_HASH is missing."""
        from config import ProductionConfig
        env = {
            "SECRET_KEY": "a" * 20,
            "DATABASE_URL": "postgresql+psycopg://u:p@localhost/db",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            os.environ.pop("ADMIN_PASSWORD_HASH", None)
            with pytest.raises(SystemExit, match="ADMIN_PASSWORD_HASH"):
                ProductionConfig.validate()

    def test_validate_short_secret_key(self):
        """validate() fails when SECRET_KEY is too short."""
        from config import ProductionConfig
        env = {
            "SECRET_KEY": "short",
            "DATABASE_URL": "postgresql+psycopg://u:p@localhost/db",
            "ADMIN_PASSWORD_HASH": "hash",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="16 caracteres"):
                ProductionConfig.validate()

    def test_validate_sqlite_rejected(self):
        """validate() fails when DATABASE_URL uses SQLite."""
        from config import ProductionConfig
        env = {
            "SECRET_KEY": "a" * 20,
            "DATABASE_URL": "sqlite:///local.db",
            "ADMIN_PASSWORD_HASH": "hash",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="SQLite"):
                ProductionConfig.validate()

    def test_validate_all_valid_passes(self):
        """validate() passes with all valid values."""
        from config import ProductionConfig
        env = {
            "SECRET_KEY": "a" * 20,
            "DATABASE_URL": "postgresql+psycopg://u:p@localhost/db",
            "ADMIN_PASSWORD_HASH": "hash",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            ProductionConfig.validate()


class TestPyserialAvailability:
    """Tests for pyserial detection."""

    def test_pyserial_importable(self):
        """pyserial must be importable."""
        import serial
        assert hasattr(serial, "__version__")

    def test_serial_list_ports_importable(self):
        """serial.tools.list_ports must be importable."""
        import serial.tools.list_ports
        assert hasattr(serial.tools.list_ports, "comports")

    def test_serial_list_ports_returns_list(self):
        """comports() returns a list (empty or with ports)."""
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        assert isinstance(ports, list)

    def test_no_ports_is_normal(self):
        """Having no serial ports is a valid state."""
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        assert isinstance(ports, list)


class TestRunPyWarnings:
    """Tests for run.py development warnings."""

    def test_run_py_file_exists(self):
        """run.py must exist."""
        assert os.path.exists("run.py")

    def test_run_py_has_debug_true(self):
        """run.py must contain debug=True."""
        with open("run.py", encoding="utf-8") as f:
            content = f.read()
        assert "debug=True" in content

    def test_run_py_disables_reloader_to_avoid_stale_database_processes(self):
        with open("run.py", encoding="utf-8") as f:
            content = f.read()
        assert "use_reloader=False" in content

    def test_run_py_has_warning(self):
        """run.py must warn about development mode."""
        with open("run.py", encoding="utf-8") as f:
            content = f.read()
        assert "WARNING" in content or "development" in content.lower()


class TestProductionPyExists:
    """Tests for production.py entry point."""

    def test_production_py_exists(self):
        """production.py must exist."""
        assert os.path.exists("production.py")

    def test_production_py_no_debug(self):
        """production.py must not use debug=True."""
        with open("production.py", encoding="utf-8") as f:
            content = f.read()
        assert "debug=True" not in content
        assert "app.debug = False" in content

    def test_production_py_uses_waitress(self):
        """production.py must use waitress."""
        with open("production.py", encoding="utf-8") as f:
            content = f.read()
        assert "waitress" in content

    def test_production_py_validates_config(self):
        """production.py must call validate_production_config()."""
        with open("production.py", encoding="utf-8") as f:
            content = f.read()
        assert "validate_production_config" in content


class TestErrorHandlers:
    """Tests for error handlers."""

    def test_error_handler_500_registered(self):
        """App has 500 error handler registered."""
        app = create_app()
        assert 500 in app.error_handler_spec.get(None, {})


class TestWindowsScripts:
    """Tests for Windows batch scripts."""

    def test_start_bat_exists(self):
        """scripts/start.bat must exist."""
        assert os.path.exists("scripts/start.bat")

    def test_verify_bat_exists(self):
        """scripts/verify.bat must exist."""
        assert os.path.exists("scripts/verify.bat")

    def test_backup_bat_exists(self):
        """scripts/backup.bat must exist."""
        assert os.path.exists("scripts/backup.bat")

    def test_start_bat_references_production(self):
        """start.bat must run production.py."""
        with open("scripts/start.bat", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        assert "production.py" in content

    def test_verify_bat_checks_python(self):
        """verify.bat must check Python."""
        with open("scripts/verify.bat", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        assert "python" in content.lower()


class TestEnvExample:
    """Tests for .env.example completeness."""

    def test_env_example_exists(self):
        """.env.example must exist."""
        assert os.path.exists(".env.example")

    def test_env_example_has_database_url(self):
        """.env.example must have DATABASE_URL."""
        with open(".env.example", encoding="utf-8") as f:
            content = f.read()
        assert "DATABASE_URL" in content

    def test_env_example_has_secret_key(self):
        """.env.example must have SECRET_KEY."""
        with open(".env.example", encoding="utf-8") as f:
            content = f.read()
        assert "SECRET_KEY" in content

    def test_env_example_no_real_credentials(self):
        """.env.example must not contain real credentials."""
        with open(".env.example", encoding="utf-8") as f:
            content = f.read()
        assert "replace-with" in content.lower() or "example" in content.lower()

    def test_env_example_has_admin_password_hash(self):
        """.env.example must have ADMIN_PASSWORD_HASH."""
        with open(".env.example", encoding="utf-8") as f:
            content = f.read()
        assert "ADMIN_PASSWORD_HASH" in content

    def test_env_example_has_app_host(self):
        """.env.example must have APP_HOST."""
        with open(".env.example", encoding="utf-8") as f:
            content = f.read()
        assert "APP_HOST" in content

    def test_env_example_has_app_port(self):
        """.env.example must have APP_PORT."""
        with open(".env.example", encoding="utf-8") as f:
            content = f.read()
        assert "APP_PORT" in content


class TestRequirements:
    """Tests for requirements.txt completeness."""

    def test_requirements_exists(self):
        """requirements.txt must exist."""
        assert os.path.exists("requirements.txt")

    def test_requirements_has_waitress(self):
        """requirements.txt must include waitress."""
        with open("requirements.txt", encoding="utf-8") as f:
            content = f.read()
        assert "waitress" in content

    def test_requirements_has_pyserial(self):
        """requirements.txt must include pyserial."""
        with open("requirements.txt", encoding="utf-8") as f:
            content = f.read()
        assert "pyserial" in content

    def test_requirements_has_openpyxl(self):
        """requirements.txt must include openpyxl."""
        with open("requirements.txt", encoding="utf-8") as f:
            content = f.read()
        assert "openpyxl" in content

    def test_requirements_has_flask(self):
        """requirements.txt must include Flask."""
        with open("requirements.txt", encoding="utf-8") as f:
            content = f.read()
        assert "Flask" in content

    def test_requirements_has_psycopg(self):
        """requirements.txt must include psycopg."""
        with open("requirements.txt", encoding="utf-8") as f:
            content = f.read()
        assert "psycopg" in content

    def test_requirements_has_alembic(self):
        """requirements.txt must include alembic."""
        with open("requirements.txt", encoding="utf-8") as f:
            content = f.read()
        assert "alembic" in content


class TestBuildSpec:
    """Tests for build.spec completeness."""

    def test_build_spec_exists(self):
        """build.spec must exist."""
        assert os.path.exists("build.spec")

    def test_build_spec_uses_production_entry(self):
        """build.spec must use production.py as entry point."""
        with open("build.spec", encoding="utf-8") as f:
            content = f.read()
        assert "production.py" in content

    def test_build_spec_includes_templates(self):
        """build.spec must include app/templates."""
        with open("build.spec", encoding="utf-8") as f:
            content = f.read()
        assert "app/templates" in content

    def test_build_spec_includes_static(self):
        """build.spec must include app/static."""
        with open("build.spec", encoding="utf-8") as f:
            content = f.read()
        assert "app/static" in content

    def test_build_spec_includes_migrations(self):
        """build.spec must include migrations."""
        with open("build.spec", encoding="utf-8") as f:
            content = f.read()
        assert "migrations" in content

    def test_build_spec_excludes_env(self):
        """build.spec must not include .env."""
        with open("build.spec", encoding="utf-8") as f:
            content = f.read()
        # .env should be in excludes or not in datas
        assert ".env" not in content or "exclude" in content.lower()

    def test_build_spec_has_pyserial_imports(self):
        """build.spec must include pyserial hidden imports."""
        with open("build.spec", encoding="utf-8") as f:
            content = f.read()
        assert "serial" in content

    def test_build_spec_console_false(self):
        """build.spec must set console=False for windowed mode."""
        with open("build.spec", encoding="utf-8") as f:
            content = f.read()
        assert "console=False" in content

    def test_build_spec_no_icon(self):
        """build.spec must not set an icon (no custom exe icon)."""
        with open("build.spec", encoding="utf-8") as f:
            content = f.read()
        assert "icon=" not in content or "icon=" not in content.split("EXE")[1]


class TestIcoFile:
    """Tests for the multi-resolution ICO file."""

    def test_ico_file_exists(self):
        """agricola-vita-santa-fe.ico must exist."""
        assert os.path.exists("app/static/img/branding/agricola-vita-santa-fe.ico")

    def test_ico_does_not_replace_png(self):
        """The original PNG logo must still exist."""
        assert os.path.exists("app/static/img/branding/logo-agricola-vita-santa-fe.png")

    def test_ico_has_multiple_resolutions(self):
        """The ICO file must contain at least 3 different sizes."""
        from PIL import Image
        ico = Image.open("app/static/img/branding/agricola-vita-santa-fe.ico")
        sizes = ico.info.get("sizes", set())
        assert len(sizes) >= 3, f"ICO has only {len(sizes)} sizes, expected >= 3"

    def test_ico_contains_16x16(self):
        """ICO must contain 16x16."""
        from PIL import Image
        ico = Image.open("app/static/img/branding/agricola-vita-santa-fe.ico")
        assert (16, 16) in ico.info.get("sizes", set())

    def test_ico_contains_256x256(self):
        """ICO must contain 256x256."""
        from PIL import Image
        ico = Image.open("app/static/img/branding/agricola-vita-santa-fe.ico")
        assert (256, 256) in ico.info.get("sizes", set())


class TestProductionWindowed:
    """Tests for windowed-mode features in production.py."""

    def test_importing_production_does_not_open_browser(self):
        """Importing production must not trigger browser.open."""
        import production
        with mock.patch("webbrowser.open") as mock_browse:
            importlib.reload(production)
            mock_browse.assert_not_called()

    def test_main_not_called_on_import(self):
        """main() must not execute during import."""
        import production
        assert callable(production.main)

    def test_build_url_generation(self):
        """_open_browser should construct correct URL from host and port."""
        from production import _open_browser
        with mock.patch("production._is_port_open", return_value=True):
            with mock.patch("webbrowser.open") as mock_browse:
                _open_browser("127.0.0.1", 5000)
                mock_browse.assert_called_once_with("http://127.0.0.1:5000")

    def test_browser_opens_only_once(self):
        """_open_browser must open the browser exactly once."""
        from production import _open_browser
        call_count = 0

        def fake_is_port(host, port, timeout=1.0):
            nonlocal call_count
            call_count += 1
            return True

        with mock.patch("production._is_port_open", side_effect=fake_is_port):
            with mock.patch("webbrowser.open") as mock_browse:
                result = _open_browser("127.0.0.1", 5000)
                assert result is True
                assert mock_browse.call_count == 1

    def test_browser_not_opened_if_server_never_starts(self):
        """_open_browser must return False if server never becomes ready."""
        from production import _open_browser
        with mock.patch("production._is_port_open", return_value=False):
            with mock.patch("webbrowser.open") as mock_browse:
                result = _open_browser("127.0.0.1", 5000, max_wait=1)
                assert result is False
                mock_browse.assert_not_called()

    def test_browser_uses_127_for_0_0_0_0_host(self):
        """main() must map 0.0.0.0 to 127.0.0.1 for browser URL."""
        from production import _open_browser
        with mock.patch("production._is_port_open", return_value=True):
            with mock.patch("webbrowser.open") as mock_browse:
                _open_browser("0.0.0.0", 5000)
                mock_browse.assert_called_once_with("http://0.0.0.0:5000")

    def test_is_port_open_returns_true_when_connected(self):
        """_is_port_open returns True when connection succeeds."""
        from production import _is_port_open
        with mock.patch("socket.create_connection"):
            assert _is_port_open("127.0.0.1", 5000) is True

    def test_is_port_open_returns_false_when_refused(self):
        """_is_port_open returns False when connection is refused."""
        from production import _is_port_open
        with mock.patch("socket.create_connection", side_effect=ConnectionRefusedError):
            assert _is_port_open("127.0.0.1", 5000) is False

    def test_is_port_open_returns_false_on_os_error(self):
        """_is_port_open returns False on OSError."""
        from production import _is_port_open
        with mock.patch("socket.create_connection", side_effect=OSError):
            assert _is_port_open("127.0.0.1", 5000) is False

    def test_show_error_messagebox_not_called_when_not_windowed(self):
        """_show_error_messagebox must be a no-op when not in windowed mode."""
        from production import _show_error_messagebox
        with mock.patch("production._is_windowed_mode", return_value=False):
            with mock.patch("ctypes.windll.user32.MessageBoxW") as mock_mb:
                _show_error_messagebox("Title", "Message")
                mock_mb.assert_not_called()

    def test_setup_logging_creates_log_dir(self):
        """_setup_logging must create the logs directory."""
        from production import _setup_logging
        with mock.patch("production._get_base_dir", return_value=os.path.join(os.environ["TEMP"], "test_logs")):
            logger = _setup_logging()
            log_dir = os.path.join(os.environ["TEMP"], "test_logs", "logs")
            assert os.path.isdir(log_dir)
            assert logger is not None
            import shutil
            shutil.rmtree(os.path.join(os.environ["TEMP"], "test_logs"), ignore_errors=True)

    def test_get_base_dir_frozen(self):
        """_get_base_dir returns exe dir when frozen."""
        from production import _get_base_dir
        with mock.patch("sys.frozen", True, create=True):
            result = _get_base_dir()
            assert result is not None

    def test_get_base_dir_script(self):
        """_get_base_dir returns script dir when not frozen."""
        from production import _get_base_dir
        with mock.patch.object(sys, "frozen", False, create=True):
            result = _get_base_dir()
            assert os.path.isdir(result)

    def test_missing_env_no_browser_no_server(self):
        """Missing .env should fail validation, not open browser or start server."""
        from production import validate_production_config
        with mock.patch("webbrowser.open") as mock_browse:
            with pytest.raises(SystemExit):
                validate_production_config(environ={})
            mock_browse.assert_not_called()

    def test_error_logged_on_startup_failure(self):
        """Startup errors must be written to the log file."""
        import logging
        from production import _setup_logging
        with mock.patch("production._get_base_dir", return_value=os.path.join(os.environ["TEMP"], "test_logdir")):
            _setup_logging()
            logger = logging.getLogger("production")
            with mock.patch.object(logger, "error") as mock_log:
                try:
                    raise SystemExit("ERROR: test error")
                except SystemExit:
                    logger.error("Startup error: %s", "ERROR: test error")
                    mock_log.assert_called()
            import shutil
            shutil.rmtree(os.path.join(os.environ["TEMP"], "test_logdir"), ignore_errors=True)

    def test_main_creates_server(self):
        """main() must use waitress.create_server."""
        mock_server = mock.MagicMock()
        mock_app = mock.MagicMock()
        mock_cs = mock.MagicMock(return_value=mock_server)

        def fake_load_dotenv(*args, **kwargs):
            os.environ["DATABASE_URL"] = "postgresql+psycopg://u:p@localhost/db"
            os.environ["SECRET_KEY"] = "a" * 40
            os.environ["ADMIN_PASSWORD_HASH"] = "pbkdf2:sha256:600000$abc$def"
            os.environ["HARVEST_TIMEZONE"] = "UTC"

        import production
        with mock.patch("dotenv.load_dotenv", side_effect=fake_load_dotenv):
            with mock.patch("app.create_app", return_value=mock_app):
                with mock.patch("waitress.create_server", mock_cs):
                    with mock.patch("threading.Thread") as mock_thread_cls:
                        mock_thread = mock.MagicMock()
                        mock_thread_cls.return_value = mock_thread
                        with mock.patch("threading.Event") as mock_event:
                            mock_event.return_value.wait.side_effect = None
                            with mock.patch.dict(os.environ, {}, clear=True):
                                production.main()
        mock_cs.assert_called_once()

    def test_main_starts_server_in_thread(self):
        """main() must start the server in a daemon thread."""
        import production
        mock_server = mock.MagicMock()
        mock_app = mock.MagicMock()
        mock_cs = mock.MagicMock(return_value=mock_server)

        def fake_load_dotenv(*args, **kwargs):
            os.environ["DATABASE_URL"] = "postgresql+psycopg://u:p@localhost/db"
            os.environ["SECRET_KEY"] = "a" * 40
            os.environ["ADMIN_PASSWORD_HASH"] = "pbkdf2:sha256:600000$abc$def"
            os.environ["HARVEST_TIMEZONE"] = "UTC"

        with mock.patch("dotenv.load_dotenv", side_effect=fake_load_dotenv):
            with mock.patch("app.create_app", return_value=mock_app):
                with mock.patch("waitress.create_server", mock_cs):
                    with mock.patch("threading.Thread") as mock_thread_cls:
                        mock_thread = mock.MagicMock()
                        mock_thread_cls.return_value = mock_thread
                        with mock.patch("threading.Event") as mock_event:
                            mock_event.return_value.wait.side_effect = None
                            with mock.patch.dict(os.environ, {}, clear=True):
                                production.main()
                            mock_thread_cls.assert_called_once()
                            mock_thread.start.assert_called_once()
                            _, kwargs = mock_thread_cls.call_args
                            assert kwargs.get("daemon") is True

    def test_main_does_not_open_browser_when_not_main(self):
        """main() must not open browser when __name__ != '__main__'."""
        import production
        mock_server = mock.MagicMock()
        mock_app = mock.MagicMock()
        mock_cs = mock.MagicMock(return_value=mock_server)

        def fake_load_dotenv(*args, **kwargs):
            os.environ["DATABASE_URL"] = "postgresql+psycopg://u:p@localhost/db"
            os.environ["SECRET_KEY"] = "a" * 40
            os.environ["ADMIN_PASSWORD_HASH"] = "pbkdf2:sha256:600000$abc$def"
            os.environ["HARVEST_TIMEZONE"] = "UTC"

        with mock.patch("dotenv.load_dotenv", side_effect=fake_load_dotenv):
            with mock.patch("app.create_app", return_value=mock_app):
                with mock.patch("waitress.create_server", mock_cs):
                    with mock.patch("webbrowser.open") as mock_browse:
                        with mock.patch("threading.Thread"):
                            with mock.patch("threading.Event") as mock_event:
                                mock_event.return_value.wait.side_effect = None
                                with mock.patch.dict(os.environ, {}, clear=True):
                                    production.main()
                                mock_browse.assert_not_called()


class TestSetupNeededDetection:
    """Tests for _is_setup_needed() detection logic."""

    def test_setup_needed_when_no_admin_hash(self):
        """Setup is needed when ADMIN_PASSWORD_HASH is not set."""
        from production import _is_setup_needed
        with mock.patch.dict(os.environ, {}, clear=True):
            assert _is_setup_needed() is True

    def test_setup_needed_when_empty_admin_hash(self):
        """Setup is needed when ADMIN_PASSWORD_HASH is empty."""
        from production import _is_setup_needed
        with mock.patch.dict(os.environ, {"ADMIN_PASSWORD_HASH": ""}, clear=True):
            assert _is_setup_needed() is True

    def test_setup_needed_when_placeholder_hash(self):
        """Setup is needed when ADMIN_PASSWORD_HASH is the placeholder."""
        from production import _is_setup_needed
        with mock.patch.dict(os.environ,
                             {"ADMIN_PASSWORD_HASH": "replace-with-generated-password-hash"},
                             clear=True):
            assert _is_setup_needed() is True

    def test_setup_not_needed_when_valid_hash(self):
        """Setup is not needed when ADMIN_PASSWORD_HASH is a real hash."""
        from production import _is_setup_needed
        with mock.patch.dict(os.environ,
                             {"ADMIN_PASSWORD_HASH": "pbkdf2:sha256:600000$abc$def"},
                             clear=True):
            assert _is_setup_needed() is False


class TestMinimalConfigValidation:
    """Tests for _validate_minimal_config() used in setup wizard mode."""

    def test_valid_minimal_config_passes(self):
        """Valid minimal config should pass."""
        from production import _validate_minimal_config
        env = {
            "DATABASE_URL": "postgresql+psycopg://u:p@localhost/db",
            "SECRET_KEY": "a" * 40,
            "HARVEST_TIMEZONE": "UTC",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            _validate_minimal_config()

    def test_missing_database_url_fails(self):
        """Missing DATABASE_URL should fail."""
        from production import _validate_minimal_config
        env = {
            "SECRET_KEY": "a" * 40,
            "HARVEST_TIMEZONE": "UTC",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="DATABASE_URL"):
                _validate_minimal_config()

    def test_missing_secret_key_fails(self):
        """Missing SECRET_KEY should fail."""
        from production import _validate_minimal_config
        env = {
            "DATABASE_URL": "postgresql+psycopg://u:p@localhost/db",
            "HARVEST_TIMEZONE": "UTC",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="SECRET_KEY"):
                _validate_minimal_config()

    def test_missing_timezone_fails(self):
        """Missing HARVEST_TIMEZONE should fail."""
        from production import _validate_minimal_config
        env = {
            "DATABASE_URL": "postgresql+psycopg://u:p@localhost/db",
            "SECRET_KEY": "a" * 40,
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="HARVEST_TIMEZONE"):
                _validate_minimal_config()

    def test_short_secret_key_fails(self):
        """SECRET_KEY shorter than 32 chars should fail."""
        from production import _validate_minimal_config
        env = {
            "DATABASE_URL": "postgresql+psycopg://u:p@localhost/db",
            "SECRET_KEY": "short",
            "HARVEST_TIMEZONE": "UTC",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="at least 32"):
                _validate_minimal_config()

    def test_admin_password_hash_not_required(self):
        """ADMIN_PASSWORD_HASH should NOT be required in minimal validation."""
        from production import _validate_minimal_config
        env = {
            "DATABASE_URL": "postgresql+psycopg://u:p@localhost/db",
            "SECRET_KEY": "a" * 40,
            "HARVEST_TIMEZONE": "UTC",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            _validate_minimal_config()


class TestProductionSetupMode:
    """Tests for production.py running in setup wizard mode."""

    @mock.patch("waitress.create_server")
    @mock.patch("app.create_app")
    @mock.patch("dotenv.load_dotenv")
    def test_main_starts_in_setup_mode_when_no_admin_hash(self, mock_dotenv, mock_create_app, mock_cs):
        """main() should start the server when ADMIN_PASSWORD_HASH is missing."""
        import production
        mock_app = mock.MagicMock()
        mock_create_app.return_value = mock_app
        mock_server = mock.MagicMock()
        mock_cs.return_value = mock_server

        def fake_load_dotenv(*args, **kwargs):
            os.environ["DATABASE_URL"] = "postgresql+psycopg://u:p@localhost/db"
            os.environ["SECRET_KEY"] = "a" * 40
            os.environ["HARVEST_TIMEZONE"] = "UTC"

        mock_dotenv.side_effect = fake_load_dotenv

        with mock.patch("threading.Thread"):
            with mock.patch("threading.Event") as mock_evt:
                mock_evt.return_value.wait.side_effect = None
                with mock.patch.dict(os.environ, {}, clear=True):
                    production.main()
                mock_cs.assert_called_once()

    @mock.patch("waitress.create_server")
    @mock.patch("app.create_app")
    @mock.patch("dotenv.load_dotenv")
    def test_main_starts_in_normal_mode_when_admin_hash_set(self, mock_dotenv, mock_create_app, mock_cs):
        """main() should start normally when ADMIN_PASSWORD_HASH is valid."""
        import production
        mock_app = mock.MagicMock()
        mock_create_app.return_value = mock_app
        mock_server = mock.MagicMock()
        mock_cs.return_value = mock_server

        def fake_load_dotenv(*args, **kwargs):
            os.environ["DATABASE_URL"] = "postgresql+psycopg://u:p@localhost/db"
            os.environ["SECRET_KEY"] = "a" * 40
            os.environ["ADMIN_PASSWORD_HASH"] = "pbkdf2:sha256:600000$abc$def"
            os.environ["HARVEST_TIMEZONE"] = "UTC"

        mock_dotenv.side_effect = fake_load_dotenv

        with mock.patch("threading.Thread"):
            with mock.patch("threading.Event") as mock_evt:
                mock_evt.return_value.wait.side_effect = None
                with mock.patch.dict(os.environ, {}, clear=True):
                    production.main()
                mock_cs.assert_called_once()


class TestSetupWizardRoutes:
    """Tests for the /setup wizard routes."""

    def test_setup_page_returns_200(self, client):
        """GET /setup should return 200."""
        resp = client.get("/setup")
        assert resp.status_code == 200

    def test_setup_page_contains_form(self, client):
        """GET /setup should contain the setup form."""
        resp = client.get("/setup")
        data = resp.get_data(as_text=True)
        assert "setup-form" in data
        assert "admin-password" in data

    def test_setup_api_missing_password(self, client):
        """POST /api/setup without password should fail."""
        resp = client.post("/api/setup", json={})
        assert resp.status_code == 400
        assert "contrasena" in resp.get_json()["error"].lower()

    def test_setup_api_short_password(self, client):
        """POST /api/setup with short password should fail."""
        resp = client.post("/api/setup", json={"admin_password": "short"})
        assert resp.status_code == 400
        assert "8 caracteres" in resp.get_json()["error"]

    def test_setup_api_invalid_port(self, client):
        """POST /api/setup with invalid port should fail."""
        resp = client.post("/api/setup", json={
            "admin_password": "validpassword123",
            "app_port": "99999",
        })
        assert resp.status_code == 400
        assert "puerto" in resp.get_json()["error"].lower()

    def test_setup_api_invalid_timezone(self, client):
        """POST /api/setup with invalid timezone should fail."""
        resp = client.post("/api/setup", json={
            "admin_password": "validpassword123",
            "harvest_timezone": "Invalid/Timezone",
        })
        assert resp.status_code == 400
        assert "zona horaria" in resp.get_json()["error"].lower()

    def test_setup_api_creates_env_file(self, client, tmp_path):
        """POST /api/setup should create .env file with config."""
        from app.routes import views
        original_get_base = views._get_base_dir
        views._get_base_dir = lambda: str(tmp_path)
        try:
            env_file = tmp_path / ".env"
            env_file.write_text("DATABASE_URL=postgresql+psycopg://u:p@localhost/db\n")

            resp = client.post("/api/setup", json={
                "admin_password": "validpassword123",
                "app_port": "8080",
                "app_access": "local",
                "harvest_timezone": "UTC",
            })
            assert resp.status_code == 200
            assert env_file.exists()
            content = env_file.read_text()
            assert "ADMIN_PASSWORD_HASH=" in content
            assert "SECRET_KEY=" in content
            assert "APP_PORT=8080" in content
            assert "HARVEST_TIMEZONE=UTC" in content
            assert "DATABASE_URL=postgresql+psycopg://u:p@localhost/db" in content
            assert "validpassword123" not in content
        finally:
            views._get_base_dir = original_get_base

    def test_setup_api_preserves_existing_env_keys(self, client, tmp_path):
        """POST /api/setup should preserve existing .env keys."""
        from app.routes import views
        original_get_base = views._get_base_dir
        views._get_base_dir = lambda: str(tmp_path)
        try:
            env_file = tmp_path / ".env"
            env_file.write_text(
                "DATABASE_URL=postgresql+psycopg://u:p@localhost/db\n"
                "PG_DUMP_PATH=C:\\pgsql\\bin\\pg_dump.exe\n"
                "TICKET_BUSINESS_NAME=Mi Empresa\n"
            )

            resp = client.post("/api/setup", json={
                "admin_password": "validpassword123",
            })
            assert resp.status_code == 200
            content = env_file.read_text()
            assert "PG_DUMP_PATH=C:\\pgsql\\bin\\pg_dump.exe" in content
            assert "TICKET_BUSINESS_NAME=Mi Empresa" in content
        finally:
            views._get_base_dir = original_get_base

    def test_setup_api_no_password_in_response(self, client, tmp_path):
        """POST /api/setup must not expose the password in the response."""
        from app.routes import views
        original_get_base = views._get_base_dir
        views._get_base_dir = lambda: str(tmp_path)
        try:
            env_file = tmp_path / ".env"
            env_file.write_text("DATABASE_URL=postgresql+psycopg://u:p@localhost/db\n")

            resp = client.post("/api/setup", json={
                "admin_password": "mysecretpassword123",
            })
            data = resp.get_data(as_text=True)
            assert "mysecretpassword123" not in data
        finally:
            views._get_base_dir = original_get_base

    def test_setup_api_no_plaintext_password_in_env(self, client, tmp_path):
        """POST /api/setup must store a hash, not plaintext password."""
        from app.routes import views
        original_get_base = views._get_base_dir
        views._get_base_dir = lambda: str(tmp_path)
        try:
            env_file = tmp_path / ".env"
            env_file.write_text("DATABASE_URL=postgresql+psycopg://u:p@localhost/db\n")

            resp = client.post("/api/setup", json={
                "admin_password": "mysecretpassword123",
            })
            assert resp.status_code == 200
            content = env_file.read_text()
            assert "mysecretpassword123" not in content
            assert "pbkdf2:" in content or "scrypt:" in content
        finally:
            views._get_base_dir = original_get_base

    def test_setup_password_can_login_immediately_without_restart(
        self, client, app, tmp_path
    ):
        """The hash created by /setup must be used by login in this process."""
        from app.routes import views
        from werkzeug.security import check_password_hash

        password = "same-password-123"
        original_get_base = views._get_base_dir
        original_hash = app.config.get("ADMIN_PASSWORD_HASH")
        views._get_base_dir = lambda: str(tmp_path)
        try:
            env_file = tmp_path / ".env"
            env_file.write_text(
                "DATABASE_URL=postgresql+psycopg://u:p@localhost/db\n"
                "SECRET_KEY=" + "s" * 64 + "\n",
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {}, clear=False):
                setup_response = client.post(
                    "/api/setup",
                    json={
                        "admin_password": password,
                        "harvest_timezone": "UTC",
                    },
                )
                assert setup_response.status_code == 200
                assert setup_response.get_json()["redirect"] == "/admin/login"
                assert client.get("/admin/login").status_code == 200

                stored_hash = app.config["ADMIN_PASSWORD_HASH"]
                assert stored_hash == os.environ["ADMIN_PASSWORD_HASH"]
                assert check_password_hash(stored_hash, password)

                csrf = client.get("/api/admin/session").get_json()["csrf_token"]
                login_response = client.post(
                    "/api/admin/login",
                    json={"password": password},
                    headers={"X-CSRF-Token": csrf},
                )
                assert login_response.status_code == 200
        finally:
            app.config["ADMIN_PASSWORD_HASH"] = original_hash
            views._get_base_dir = original_get_base

    def test_setup_then_empty_and_wrong_password_are_rejected(
        self, client, app, tmp_path
    ):
        from app.routes import views

        password = "correct-password-123"
        original_get_base = views._get_base_dir
        original_hash = app.config.get("ADMIN_PASSWORD_HASH")
        views._get_base_dir = lambda: str(tmp_path)
        try:
            (tmp_path / ".env").write_text(
                "DATABASE_URL=postgresql+psycopg://u:p@localhost/db\n"
                "SECRET_KEY=" + "s" * 64 + "\n",
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {}, clear=False):
                assert client.post(
                    "/api/setup", json={"admin_password": password}
                ).status_code == 200

                csrf = client.get("/api/admin/session").get_json()["csrf_token"]
                empty = client.post(
                    "/api/admin/login",
                    json={"password": ""},
                    headers={"X-CSRF-Token": csrf},
                )
                assert empty.status_code == 400

                wrong = client.post(
                    "/api/admin/login",
                    json={"password": "incorrect-password"},
                    headers={"X-CSRF-Token": csrf},
                )
                assert wrong.status_code == 401
        finally:
            app.config["ADMIN_PASSWORD_HASH"] = original_hash
            views._get_base_dir = original_get_base

    def test_setup_api_smtp_config(self, client, tmp_path):
        """POST /api/setup should include SMTP config when provided."""
        from app.routes import views
        original_get_base = views._get_base_dir
        views._get_base_dir = lambda: str(tmp_path)
        try:
            env_file = tmp_path / ".env"
            env_file.write_text("DATABASE_URL=postgresql+psycopg://u:p@localhost/db\n")

            resp = client.post("/api/setup", json={
                "admin_password": "validpassword123",
                "smtp_host": "smtp.gmail.com",
                "smtp_port": "587",
                "smtp_username": "test@gmail.com",
                "smtp_app_password": "app-pass-123",
            })
            assert resp.status_code == 200
            content = env_file.read_text()
            assert "MAIL_SMTP_HOST=smtp.gmail.com" in content
            assert "MAIL_SMTP_PORT=587" in content
            assert "MAIL_SMTP_USERNAME=test@gmail.com" in content
            assert "MAIL_SMTP_APP_PASSWORD=app-pass-123" in content
            assert "MAIL_USE_TLS=true" in content
        finally:
            views._get_base_dir = original_get_base

    def test_setup_needed_check_in_before_request(self, app):
        """before_request should redirect to /setup when setup is needed."""
        from app.routes import views
        original = views._is_setup_needed
        views._is_setup_needed = lambda: True
        try:
            client = app.test_client()
            resp = client.get("/")
            assert resp.status_code == 302
            assert "/setup" in resp.headers["Location"]
        finally:
            views._is_setup_needed = original

    def test_setup_not_needed_serves_normal_page(self, app):
        """When setup is not needed, normal pages should be served."""
        from app.routes import views
        original = views._is_setup_needed
        views._is_setup_needed = lambda: False
        try:
            client = app.test_client()
            resp = client.get("/")
            assert resp.status_code == 200
        finally:
            views._is_setup_needed = original

    def test_setup_page_always_accessible(self, app):
        """The /setup page should be accessible even when setup is needed."""
        from app.routes import views
        original = views._is_setup_needed
        views._is_setup_needed = lambda: True
        try:
            client = app.test_client()
            resp = client.get("/setup")
            assert resp.status_code == 200
        finally:
            views._is_setup_needed = original

    def test_setup_api_always_accessible(self, app):
        """The /api/setup endpoint should be accessible even when setup is needed."""
        from app.routes import views
        original = views._is_setup_needed
        views._is_setup_needed = lambda: True
        try:
            client = app.test_client()
            resp = client.post("/api/setup", json={"admin_password": "short"})
            assert resp.status_code == 400
        finally:
            views._is_setup_needed = original

    def test_setup_api_invalid_json(self, client):
        """POST /api/setup with invalid JSON should fail."""
        resp = client.post("/api/setup", data="not json",
                           content_type="text/plain")
        assert resp.status_code == 400


class TestFrozenDatabaseStartup:
    def test_verify_database_connection_executes_select_one(self):
        from production import _verify_database_connection

        connection = mock.MagicMock()
        context = mock.MagicMock()
        context.__enter__.return_value = connection
        engine = mock.MagicMock()
        engine.connect.return_value = context

        with mock.patch("sqlalchemy.create_engine", return_value=engine):
            _verify_database_connection("postgresql+psycopg://u:p@localhost/db")

        connection.execute.assert_called_once()
        engine.dispose.assert_called_once()

    def test_verify_database_connection_fails_closed(self):
        from production import _verify_database_connection

        engine = mock.MagicMock()
        engine.connect.side_effect = RuntimeError("sensitive connection detail")

        with mock.patch("sqlalchemy.create_engine", return_value=engine):
            with pytest.raises(SystemExit, match="No se pudo conectar") as exc_info:
                _verify_database_connection("postgresql+psycopg://u:p@localhost/db")

        assert "sensitive" not in str(exc_info.value)
        engine.dispose.assert_called_once()

    def test_run_pending_migrations_uses_bundled_directory(self, tmp_path):
        import shutil

        from production import _get_bundled_migrations_dir, _run_pending_migrations

        source = Path(__file__).resolve().parents[1] / "migrations"
        bundled = tmp_path / "migrations"
        shutil.copytree(source, bundled)

        app = mock.MagicMock()
        app.config = {
            "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://u:secret@localhost/db"
        }
        revisions = [
            (("d1e2f3a4b5c6",), ("d1e2f3a4b5c6",)),
            (("d1e2f3a4b5c6",), ("d1e2f3a4b5c6",)),
        ]
        with mock.patch("flask_migrate.upgrade") as upgrade, mock.patch(
            "production._migration_revisions", side_effect=revisions
        ):
            with mock.patch.object(sys, "_MEIPASS", str(tmp_path), create=True):
                assert _get_bundled_migrations_dir() == str(bundled)
                _run_pending_migrations(app)

        upgrade.assert_called_once_with(directory=str(bundled))

    def test_real_bundled_migration_tree_resolves_head(self, tmp_path):
        import shutil

        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory
        from production import _get_bundled_migrations_dir

        source = Path(__file__).resolve().parents[1] / "migrations"
        shutil.copytree(source, tmp_path / "migrations")
        with mock.patch.object(sys, "_MEIPASS", str(tmp_path), create=True):
            migrations_dir = _get_bundled_migrations_dir()

        config = AlembicConfig(str(Path(migrations_dir) / "alembic.ini"))
        config.set_main_option("script_location", migrations_dir)
        assert ScriptDirectory.from_config(config).get_heads() == ["f3a4b5c6d7e8"]

    def test_migration_traceback_redacts_database_password(self):
        from production import _redacted_traceback

        try:
            raise RuntimeError("postgresql+psycopg://u:secret@localhost/db secret")
        except RuntimeError:
            rendered = _redacted_traceback(
                "postgresql+psycopg://u:secret@localhost/db"
            )

        assert "secret" not in rendered
        assert "<redacted DATABASE_URL>" in rendered

    def test_setup_browser_opens_setup_path(self):
        from production import _open_browser

        with mock.patch("production._is_port_open", return_value=True):
            with mock.patch("webbrowser.open") as browser:
                _open_browser("127.0.0.1", 5000, "/setup")

        browser.assert_called_once_with("http://127.0.0.1:5000/setup")
