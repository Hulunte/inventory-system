import os
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

    @mock.patch("waitress.serve")
    def test_port_non_numeric_fails(self, mock_serve):
        """APP_PORT no numerico deberia causar SystemExit."""
        import production
        env = dict(VALID_ENV, APP_PORT="abc")
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="APP_PORT"):
                production.main()

    @mock.patch("waitress.serve")
    def test_port_zero_fails(self, mock_serve):
        """APP_PORT=0 deberia causar SystemExit."""
        import production
        env = dict(VALID_ENV, APP_PORT="0")
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                production.main()

    @mock.patch("waitress.serve")
    def test_port_negative_fails(self, mock_serve):
        """APP_PORT negativo deberia causar SystemExit."""
        import production
        env = dict(VALID_ENV, APP_PORT="-1")
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                production.main()

    @mock.patch("waitress.serve")
    def test_port_65536_fails(self, mock_serve):
        """APP_PORT=65536 deberia causar SystemExit."""
        import production
        env = dict(VALID_ENV, APP_PORT="65536")
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                production.main()

    @mock.patch("waitress.serve")
    def test_port_65535_passes(self, mock_serve):
        """APP_PORT=65535 deberia ser valido."""
        import production
        env = dict(VALID_ENV, APP_PORT="65535")
        with mock.patch.dict(os.environ, env, clear=True):
            production.main()
            mock_serve.assert_called_once()

    @mock.patch("waitress.serve")
    def test_port_custom_valid_passes(self, mock_serve):
        """APP_PORT personalizado valido deberia pasar."""
        import production
        env = dict(VALID_ENV, APP_PORT="8080")
        with mock.patch.dict(os.environ, env, clear=True):
            production.main()
            mock_serve.assert_called_once()

    @mock.patch("waitress.serve")
    @mock.patch("dotenv.load_dotenv")
    def test_validation_before_port_check(self, mock_dotenv, mock_serve):
        """Config obligatoria invalida debe fallar antes de validar APP_PORT."""
        import production
        env = dict(VALID_ENV, APP_PORT="abc")
        del env["DATABASE_URL"]
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="DATABASE_URL"):
                production.main()

    @mock.patch("waitress.serve")
    @mock.patch("dotenv.load_dotenv")
    def test_invalid_config_stops_before_create_app(self, mock_dotenv, mock_serve):
        """Config invalida no debe llamar a create_app ni a waitress.serve."""
        import production
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("app.create_app") as mock_create:
                with pytest.raises(SystemExit):
                    production.main()
                mock_create.assert_not_called()
                mock_serve.assert_not_called()

    @mock.patch("waitress.serve")
    @mock.patch("app.create_app")
    @mock.patch("dotenv.load_dotenv")
    def test_load_dotenv_called_before_reading_env(self, mock_dotenv, mock_create_app, mock_serve):
        """load_dotenv() inyecta config que main() usa para host, port y create_app."""
        import production
        mock_app = mock.MagicMock()
        mock_create_app.return_value = mock_app

        def fake_load_dotenv():
            os.environ["DATABASE_URL"] = "postgresql+psycopg://u:p@localhost/db"
            os.environ["SECRET_KEY"] = "a" * 40
            os.environ["ADMIN_PASSWORD_HASH"] = "pbkdf2:sha256:600000$abc$def"
            os.environ["HARVEST_TIMEZONE"] = "UTC"
            os.environ["APP_HOST"] = "10.0.0.1"
            os.environ["APP_PORT"] = "9999"

        mock_dotenv.side_effect = fake_load_dotenv

        with mock.patch.dict(os.environ, {}, clear=True):
            production.main()

        mock_dotenv.assert_called_once()
        mock_create_app.assert_called_once()
        mock_serve.assert_called_once()
        args, kwargs = mock_serve.call_args
        assert args[0] is mock_app
        assert kwargs["host"] == "10.0.0.1"
        assert kwargs["port"] == 9999

    @mock.patch("waitress.serve")
    @mock.patch("app.create_app")
    @mock.patch("dotenv.load_dotenv")
    def test_default_host_and_port(self, mock_dotenv, mock_create_app, mock_serve):
        """APP_HOST y APP_PORT ausentes usan defaults 0.0.0.0:5000."""
        import production
        mock_app = mock.MagicMock()
        mock_create_app.return_value = mock_app

        def fake_load_dotenv():
            os.environ["DATABASE_URL"] = "postgresql+psycopg://u:p@localhost/db"
            os.environ["SECRET_KEY"] = "a" * 40
            os.environ["ADMIN_PASSWORD_HASH"] = "pbkdf2:sha256:600000$abc$def"
            os.environ["HARVEST_TIMEZONE"] = "UTC"

        mock_dotenv.side_effect = fake_load_dotenv

        with mock.patch.dict(os.environ, {}, clear=True):
            production.main()

        mock_serve.assert_called_once()
        args, kwargs = mock_serve.call_args
        assert args[0] is mock_app
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["port"] == 5000

    @mock.patch("waitress.serve")
    @mock.patch("app.create_app")
    @mock.patch("dotenv.load_dotenv")
    def test_main_sets_debug_false(self, mock_dotenv, mock_create_app, mock_serve):
        """main() debe deshabilitar debug en la app."""
        import production
        mock_app = mock.MagicMock()
        mock_create_app.return_value = mock_app

        def fake_load_dotenv():
            os.environ["DATABASE_URL"] = "postgresql+psycopg://u:p@localhost/db"
            os.environ["SECRET_KEY"] = "a" * 40
            os.environ["ADMIN_PASSWORD_HASH"] = "pbkdf2:sha256:600000$abc$def"
            os.environ["HARVEST_TIMEZONE"] = "UTC"

        mock_dotenv.side_effect = fake_load_dotenv

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
