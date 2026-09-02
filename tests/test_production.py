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
    """Tests que verifican el módulo production.py sin levantar servidor."""

    def test_production_has_main_function(self):
        """production.py debe tener una función main()."""
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
        """Configuración completa y válida no debe fallar."""
        from production import validate_production_config
        validate_production_config(environ=dict(VALID_ENV))

    def test_empty_environ_fails(self):
        """Environ vacío debe fallar por DATABASE_URL."""
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
        """DATABASE_URL vacía debe fallar."""
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
        """DATABASE_URL con formato inválido debe fallar."""
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
        """SECRET_KEY vacía debe fallar."""
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
        """ADMIN_PASSWORD_HASH vacía debe fallar."""
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
        """ADMIN_PASSWORD_HASH con formato scrypt válido debe pasar."""
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
        """ADMIN_PASSWORD_HASH con salt vacío debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, ADMIN_PASSWORD_HASH="pbkdf2:sha256:600000$$def")
        with pytest.raises(SystemExit, match="invalid format"):
            validate_production_config(environ=env)

    def test_admin_hash_empty_digest_rejected(self):
        """ADMIN_PASSWORD_HASH con digest vacío debe fallar."""
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
        """HARVEST_TIMEZONE vacía debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, HARVEST_TIMEZONE="")
        with pytest.raises(SystemExit, match="HARVEST_TIMEZONE"):
            validate_production_config(environ=env)

    def test_invalid_timezone(self):
        """HARVEST_TIMEZONE con valor inválido debe fallar."""
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
        """APP_HOST vacío debe fallar."""
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
        """APP_HOST con valor válido no debe fallar."""
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
        """SESSION_COOKIE_SECURE con valor inválido debe fallar."""
        from production import validate_production_config
        env = dict(VALID_ENV, SESSION_COOKIE_SECURE="yes")
        with pytest.raises(SystemExit, match="SESSION_COOKIE_SECURE"):
            validate_production_config(environ=env)

    def test_session_secure_numeric_rejected(self):
        """SESSION_COOKIE_SECURE con número debe fallar."""
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

    # --- Ausencia de filtración de secretos ---

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
        """El mensaje de error de DATABASE_URL no debe incluir host ni db inválidos."""
        from production import validate_production_config
        env = dict(VALID_ENV, DATABASE_URL="not-a-valid-scheme://evil.example.com/sensitive_db")
        with pytest.raises(SystemExit) as exc_info:
            validate_production_config(environ=env)
        error_msg = str(exc_info.value)
        assert "evil.example.com" not in error_msg
        assert "sensitive_db" not in error_msg


class TestProductionValidation:
    """Tests de validación de parámetros en main() (sin levantar servidor)."""

    @mock.patch("waitress.serve")
    def test_port_non_numeric_fails(self, mock_serve):
        """APP_PORT no numérico debería causar SystemExit."""
        import production
        env = dict(VALID_ENV, APP_PORT="abc")
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="APP_PORT"):
                production.main()

    @mock.patch("waitress.serve")
    def test_port_zero_fails(self, mock_serve):
        """APP_PORT=0 debería causar SystemExit."""
        import production
        env = dict(VALID_ENV, APP_PORT="0")
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                production.main()

    @mock.patch("waitress.serve")
    def test_port_negative_fails(self, mock_serve):
        """APP_PORT negativo debería causar SystemExit."""
        import production
        env = dict(VALID_ENV, APP_PORT="-1")
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                production.main()

    @mock.patch("waitress.serve")
    def test_port_65536_fails(self, mock_serve):
        """APP_PORT=65536 debería causar SystemExit."""
        import production
        env = dict(VALID_ENV, APP_PORT="65536")
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                production.main()

    @mock.patch("waitress.serve")
    def test_port_65535_passes(self, mock_serve):
        """APP_PORT=65535 debería ser válido."""
        import production
        env = dict(VALID_ENV, APP_PORT="65535")
        with mock.patch.dict(os.environ, env, clear=True):
            production.main()
            mock_serve.assert_called_once()

    @mock.patch("waitress.serve")
    def test_port_custom_valid_passes(self, mock_serve):
        """APP_PORT personalizado válido debería pasar."""
        import production
        env = dict(VALID_ENV, APP_PORT="8080")
        with mock.patch.dict(os.environ, env, clear=True):
            production.main()
            mock_serve.assert_called_once()

    @mock.patch("waitress.serve")
    @mock.patch("dotenv.load_dotenv")
    def test_validation_before_port_check(self, mock_dotenv, mock_serve):
        """Config obligatoria inválida debe fallar antes de validar APP_PORT."""
        import production
        env = dict(VALID_ENV, APP_PORT="abc")
        del env["DATABASE_URL"]
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="DATABASE_URL"):
                production.main()

    @mock.patch("waitress.serve")
    @mock.patch("dotenv.load_dotenv")
    def test_invalid_config_stops_before_create_app(self, mock_dotenv, mock_serve):
        """Config inválida no debe llamar a create_app ni a waitress.serve."""
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
        """create_app() produce una instancia Flask válida."""
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
    """Verifica que TestConfig declara una zona horaria explícita y determinista."""

    def test_test_config_has_explicit_harvest_timezone(self):
        """TestConfig.HARVEST_TIMEZONE debe ser ZoneInfo("America/Chihuahua")."""
        from config import TestConfig

        tz = TestConfig.HARVEST_TIMEZONE
        assert isinstance(tz, ZoneInfo)
        assert str(tz) == "America/Chihuahua"
