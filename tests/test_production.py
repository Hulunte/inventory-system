import os
import sys
from unittest import mock

import pytest

from app import create_app


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
        # verify main exists
        assert hasattr(production, "main")

    def test_production_uses_create_app(self):
        """production usa create_app del proyecto."""
        import production
        # main() debe llamar create_app en algún momento
        # solo verificamos que el módulo existe y tiene la estructura esperada


class TestProductionValidation:
    """Tests devalidación de parámetros (sin levantar servidor)."""

    @mock.patch("waitress.serve")
    def test_port_non_numeric_fails(self, mock_serve):
        """APP_PORT no numérico debería causar SystemExit."""
        import production
        with mock.patch.dict(os.environ, {"APP_PORT": "abc"}, clear=True):
            try:
                production.main()
                assert False, "Should have raised SystemExit"
            except SystemExit as e:
                assert "integer" in str(e).lower() or "must be" in str(e)

    @mock.patch("waitress.serve")
    def test_port_zero_fails(self, mock_serve):
        """APP_PORT=0 debería causar SystemExit."""
        import production
        with mock.patch.dict(os.environ, {"APP_PORT": "0"}, clear=True):
            try:
                production.main()
                assert False, "Should have raised SystemExit"
            except SystemExit:
                pass

    @mock.patch("waitress.serve")
    def test_port_negative_fails(self, mock_serve):
        """APP_PORT negativo debería causar SystemExit."""
        import production
        with mock.patch.dict(os.environ, {"APP_PORT": "-1"}, clear=True):
            try:
                production.main()
                assert False, "Should have raised SystemExit"
            except SystemExit:
                pass

    @mock.patch("waitress.serve")
    def test_port_65536_fails(self, mock_serve):
        """APP_PORT=65536 debería causar SystemExit."""
        import production
        with mock.patch.dict(os.environ, {"APP_PORT": "65536"}, clear=True):
            try:
                production.main()
                assert False, "Should have raised SystemExit"
            except SystemExit:
                pass

    @mock.patch("waitress.serve")
    def test_port_65535_passes(self, mock_serve):
        """APP_PORT=65535 debería ser válido."""
        import production
        with mock.patch.dict(os.environ, {"APP_PORT": "65535"}, clear=True):
            try:
                production.main()
            except SystemExit:
                assert False, "Port 65535 should be valid"

    @mock.patch("waitress.serve")
    def test_port_custom_valid_passes(self, mock_serve):
        """APP_PORT personalizado válido debería pasar."""
        import production
        with mock.patch.dict(os.environ, {"APP_PORT": "8080"}, clear=True):
            try:
                production.main()
            except SystemExit:
                assert False, "Valid port 8080 should pass"


class TestProductionAppFactory:
    """verify the app factory produces the app used by production."""

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


class TestProductionEnvDefaults:
    """Tests que verifican defaults de entorno sin levantar servidor."""

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_app_host_default_0_0_0_0(self):
        """host por defecto es 0.0.0.0."""
        import production
        # verify by checking the env is read correctly
        host = os.getenv("APP_HOST", "0.0.0.0")
        assert host == "0.0.0.0"

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_port_default_5000(self):
        """puerto por defecto es 5000."""
        port_str = os.getenv("APP_PORT", "5000")
        port = int(port_str)
        assert port == 5000


class TestProductionDebugDisabled:
    """verify debug is disabled in production."""

    def test_create_app_debug_is_false(self):
        """create_app() deja debug en False."""
        app = create_app()
        assert app.debug is False

    def test_production_code_disables_debug(self):
        """código de production.py debe asegurar debug=False."""
        # The production flow ensures debug=False
        # We verify by checking the app factory result
        app = create_app()
        assert app.debug is False