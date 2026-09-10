from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ISS = (ROOT / "installer" / "inventory-system.iss").read_text(encoding="utf-8")
BAT = (ROOT / "installer" / "setup-postgres.bat").read_text(encoding="utf-8")


def test_distribution_version_is_consistent_and_installer_checks_built_exe():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    spec = (ROOT / "build.spec").read_text(encoding="utf-8")
    version_info = (ROOT / "version_info.txt").read_text(encoding="utf-8")

    assert 'version = "1.0.1"' in pyproject
    assert '#define MyAppVersion "1.0.1"' in ISS
    assert "AppVerName={#MyAppName} {#MyAppVersion}" in ISS
    assert "UninstallDisplayName={#MyAppName} {#MyAppVersion}" in ISS
    assert "VersionInfoVersion={#MyAppVersion}.0" in ISS
    assert "GetVersionNumbersString(MyBuiltExe)" in ISS
    assert 'MyAppVersion + ".0"' in ISS
    assert 'version=\'version_info.txt\'' in spec
    assert "filevers=(1, 0, 1, 0)" in version_info
    assert "prodvers=(1, 0, 1, 0)" in version_info


def test_postgres_service_detection_supports_registry_and_versions_14_to_18():
    assert "SOFTWARE\\PostgreSQL\\Installations" in ISS
    assert "Service ID" in ISS
    assert "SYSTEM\\CurrentControlSet\\Services" in ISS
    for version in range(14, 19):
        assert f"PostgreSQL\\{version}\\bin\\pg_isready.exe" in ISS


def test_passwords_are_passed_to_batch_through_temporary_files():
    command = next(line for line in ISS.splitlines() if "SetupBatch +" in line)
    assert "AppPasswordFile" in command
    assert "PostgresPasswordFile" in command
    assert "AppDatabasePassword" not in command
    assert "PostgresSuperuserPassword" not in command
    assert 'set /p "APP_DB_PASSWORD="' in BAT
    assert 'set /p "POSTGRES_SUPERUSER_PASSWORD="' in BAT


def test_temporary_credentials_are_deleted_and_never_logged():
    assert "DeleteFile(AppPasswordFile)" in ISS
    assert "DeleteFile(PostgresPasswordFile)" in ISS
    assert "LogMessage(AppDatabasePassword" not in ISS
    assert "LogMessage(PostgresSuperuserPassword" not in ISS


def test_invalid_postgres_password_has_specific_safe_error():
    assert "ERROR_CODE=INVALID_POSTGRES_PASSWORD" in BAT
    assert "La contraseña del usuario postgres no es válida." in ISS


def test_valid_env_is_reused_without_rewriting_it():
    assert "else if IsUpgrade then" in ISS
    assert "PasswordFromInstallerDBUrl" in ISS
    assert "Upgrade: preserving existing .env" in ISS
    assert "if AppPasswordWasProvided then" in ISS


def test_existing_user_with_wrong_password_has_specific_error():
    assert BAT.count("ERROR_CODE=APP_CREDENTIALS_MISMATCH") == 2
    assert (
        "La contraseña del usuario de aplicación no coincide con la configuración existente."
        in ISS
    )
    assert "ALTER USER" not in BAT


def test_existing_user_can_use_explicitly_provided_password():
    assert "AppDatabasePasswordPage.Values[0]" in ISS
    assert "AppPasswordWasProvided" in ISS
    assert "ReplaceEnvValue(EnvPath, 'DATABASE_URL', DBUrl)" in ISS


def test_new_install_generates_app_password_only_after_postgres_is_absent():
    assert "WasPostgreSQLAlreadyInstalled := PGBinPath <> ''" in ISS
    assert "else if WasPostgreSQLAlreadyInstalled then" in ISS
    assert "AppDatabasePassword := GenerateRandomPassword" in ISS


def test_required_app_password_is_captured_before_install_step():
    assert "function NextButtonClick(CurPageID: Integer): Boolean" in ISS
    assert (
        "CapturedAppDatabasePassword := AppDatabasePasswordPage.Values[0]" in ISS
    )
    assert "Result := False" in ISS
    assert "AppDatabasePassword := CapturedAppDatabasePassword" in ISS


def test_captured_password_reaches_batch_only_through_temporary_file():
    assert "SaveStringToFile(AppPasswordFile, AppDatabasePassword, False)" in ISS
    command = next(line for line in ISS.splitlines() if "SetupBatch +" in line)
    assert "AppPasswordFile" in command
    assert "CapturedAppDatabasePassword" not in command
    assert 'set /p "APP_DB_PASSWORD="<"%APP_PASSWORD_FILE%"' in BAT


def test_pyinstaller_includes_dynamic_alembic_logging_dependency():
    spec = (ROOT / "build.spec").read_text(encoding="utf-8")
    assert "'logging.config'" in spec
    assert "('migrations', 'migrations')" in spec


def test_installer_packages_current_exe_and_migration_tree():
    assert 'Source: "{#MyBuiltExe}"; DestDir: "{app}"' in ISS
    assert 'Source: "{#MyRoot}\\migrations\\*"; DestDir: "{app}\\migrations"' in ISS


def test_batch_uses_exact_service_and_handles_paths_with_spaces():
    assert 'sc query "%PG_SERVICE%"' in BAT
    assert '"%PG_ISREADY%"' in BAT
    assert '"%PSQL%"' in BAT
    assert "SERVICE_NAME:" not in BAT
