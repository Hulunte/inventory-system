; Inno Setup script for Inventory System
; Requires Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
;
; Build: iscc installer\inventory-system.iss
;
; REQUIRED: installer/postgresql-installer.exe must exist.
; Build will FAIL without it.

#define MyAppName "Inventory System"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "Agricola Vita Santa Fe"
#define MyAppExeName "inventory-system.exe"
#define MyAppIcon "..\app\static\img\branding\agricola-vita-santa-fe.ico"
#define MyInstalledIcon "{app}\static\img\branding\agricola-vita-santa-fe.ico"
#define MyDBName "inventory_db"
#define MyDBUser "inventory_user"
#define MyRoot ".."
#define MyBuiltExe MyRoot + "\dist\" + MyAppExeName

#expr FileExists("postgresql-installer.exe") ? 1 : !Error("Falta installer/postgresql-installer.exe")
#expr FileExists(MyBuiltExe) ? 1 : !Error("Falta dist/inventory-system.exe; reconstruya el ejecutable antes del instalador")
#expr GetVersionNumbersString(MyBuiltExe) == MyAppVersion + ".0" ? 1 : !Error("La version de dist/inventory-system.exe no coincide con MyAppVersion")

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductVersion={#MyAppVersion}.0
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableDirPage=no
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=InventorySystemSetup
SetupIconFile={#MyAppIcon}
UninstallDisplayIcon={#MyInstalledIcon}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
CloseApplicationsFilter=inventory-system.exe
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: checkedonce

[Files]
Source: "{#MyBuiltExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyRoot}\app\static\img\branding\*"; DestDir: "{app}\static\img\branding"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#MyRoot}\.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "setup-postgres.bat"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "setup-postgres.bat"; Flags: dontcopy
Source: "run-migrations.bat"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "{#MyRoot}\migrations\*"; DestDir: "{app}\migrations"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "postgresql-installer.exe"; Flags: dontcopy

[Dirs]
Name: "{app}\logs"; Permissions: users-modify
Name: "{app}\backups"; Permissions: users-modify

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{#MyInstalledIcon}"; IconIndex: 0; Check: InstallationIsReady
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{#MyInstalledIcon}"; IconIndex: 0; Check: InstallationIsReady

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName} ahora"; Flags: nowait postinstall skipifsilent; Check: InstallationIsReady

[UninstallDelete]
Type: filesandordirs; Name: "{app}\installer"
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
var
  PGInstalled: Boolean;
  PGBinPath: String;
  AppDatabasePassword: String;
  DBCreated: Boolean;
  EnvAlreadyExists: Boolean;
  IsUpgrade: Boolean;
  PGSetupFailed: Boolean;
  InstallationReady: Boolean;
  PGAdminPasswordPage: TInputQueryWizardPage;
  AppDatabasePasswordPage: TInputQueryWizardPage;
  WasPostgreSQLAlreadyInstalled: Boolean;
  CapturedAppDatabasePassword: String;

function InstallationIsReady: Boolean;
begin
  Result := InstallationReady;
end;

function GenerateRandomPassword: String;
var
  i: Integer;
  c: Char;
  chars: String;
begin
  { Keep this password safe for cmd.exe and the PostgreSQL unattended installer. }
  chars := 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  Result := '';
  for i := 1 to 24 do
  begin
    c := chars[Random(Length(chars)) + 1];
    Result := Result + c;
  end;
end;

function GenerateSecretKey: String;
var
  i: Integer;
  c: Char;
  chars: String;
begin
  chars := 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  Result := '';
  for i := 1 to 64 do
  begin
    c := chars[Random(Length(chars)) + 1];
    Result := Result + c;
  end;
end;

function FindPostgreSQLBin: String;
var
  regKey, subKey: String;
  installPath: String;
  i: Integer;
  installations: TArrayOfString;
begin
  Result := '';
  regKey := 'SOFTWARE\PostgreSQL\Installations';
  if RegGetSubkeyNames(HKLM64, regKey, installations) then
  begin
    for i := 0 to GetArrayLength(installations) - 1 do
    begin
      subKey := regKey + '\' + installations[i];
      if RegQueryStringValue(HKLM64, subKey, 'Base Directory', installPath) and
         FileExists(AddBackslash(installPath) + 'bin\pg_isready.exe') then
      begin
        Result := AddBackslash(installPath) + 'bin';
        Exit;
      end;
    end;
  end;

  if FileExists('C:\Program Files\PostgreSQL\18\bin\pg_isready.exe') then
    Result := 'C:\Program Files\PostgreSQL\18\bin'
  else if FileExists('C:\Program Files\PostgreSQL\17\bin\pg_isready.exe') then
    Result := 'C:\Program Files\PostgreSQL\17\bin'
  else if FileExists('C:\Program Files\PostgreSQL\16\bin\pg_isready.exe') then
    Result := 'C:\Program Files\PostgreSQL\16\bin'
  else if FileExists('C:\Program Files\PostgreSQL\15\bin\pg_isready.exe') then
    Result := 'C:\Program Files\PostgreSQL\15\bin'
  else if FileExists('C:\Program Files\PostgreSQL\14\bin\pg_isready.exe') then
    Result := 'C:\Program Files\PostgreSQL\14\bin';
end;

function IsPort5432Listening: Boolean;
var
  ResultCode: Integer;
begin
  Exec('cmd.exe',
    '/d /s /c "netstat -ano -p tcp | findstr /r /c:":5432 .*LISTENING" >nul"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := ResultCode = 0;
end;

function IsPostgreSQLRunning: Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if PGBinPath = '' then Exit;

  Exec(PGBinPath + '\pg_isready.exe', '-h localhost -p 5432', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := (ResultCode = 0);
end;

function FindPostgreSQLService: String;
var
  RegKey, SubKey, InstallPath, ServiceId, ImagePath: String;
  i: Integer;
  Installations, Services: TArrayOfString;
begin
  Result := '';
  RegKey := 'SOFTWARE\PostgreSQL\Installations';
  if RegGetSubkeyNames(HKLM64, RegKey, Installations) then
  begin
    for i := 0 to GetArrayLength(Installations) - 1 do
    begin
      SubKey := RegKey + '\' + Installations[i];
      if RegQueryStringValue(HKLM64, SubKey, 'Base Directory', InstallPath) and
         (CompareText(AddBackslash(InstallPath) + 'bin', PGBinPath) = 0) and
         RegQueryStringValue(HKLM64, SubKey, 'Service ID', ServiceId) then
      begin
        Result := ServiceId;
        Exit;
      end;
    end;
  end;

  RegKey := 'SYSTEM\CurrentControlSet\Services';
  if RegGetSubkeyNames(HKLM64, RegKey, Services) then
  begin
    for i := 0 to GetArrayLength(Services) - 1 do
    begin
      SubKey := RegKey + '\' + Services[i];
      if RegQueryStringValue(HKLM64, SubKey, 'ImagePath', ImagePath) and
         ((Pos(Lowercase(PGBinPath + '\pg_ctl.exe'), Lowercase(ImagePath)) > 0) or
          (Pos(Lowercase(PGBinPath + '\postgres.exe'), Lowercase(ImagePath)) > 0)) then
      begin
        Result := Services[i];
        Exit;
      end;
    end;
  end;
end;

procedure LogMessage(const Msg: String; LogFile: String);
var
  Lines: TStringList;
begin
  Lines := TStringList.Create;
  try
    if FileExists(LogFile) then
      Lines.LoadFromFile(LogFile);
    Lines.Add(Msg);
    Lines.SaveToFile(LogFile);
  finally
    Lines.Free;
  end;
end;

function ReadEnvValue(const FilePath, Key: String): String;
var
  Lines: TStringList;
  i: Integer;
  Line, K, V: String;
  P: Integer;
begin
  Result := '';
  if not FileExists(FilePath) then Exit;

  Lines := TStringList.Create;
  try
    Lines.LoadFromFile(FilePath);
    for i := 0 to Lines.Count - 1 do
    begin
      Line := Trim(Lines[i]);
      if (Line = '') or (Line[1] = '#') then Continue;
      P := Pos('=', Line);
      if P > 0 then
      begin
        K := Trim(Copy(Line, 1, P - 1));
        V := Trim(Copy(Line, P + 1, Length(Line)));
        if K = Key then
        begin
          Result := V;
          Exit;
        end;
      end;
    end;
  finally
    Lines.Free;
  end;
end;

function ReplaceEnvValue(const FilePath, Key, Value: String): Boolean;
var
  Lines: TStringList;
  i, P: Integer;
  CurrentKey: String;
  Replaced: Boolean;
begin
  Result := False;
  Lines := TStringList.Create;
  try
    if FileExists(FilePath) then
      Lines.LoadFromFile(FilePath);
    Replaced := False;
    for i := 0 to Lines.Count - 1 do
    begin
      P := Pos('=', Lines[i]);
      if P > 0 then
      begin
        CurrentKey := Trim(Copy(Lines[i], 1, P - 1));
        if CurrentKey = Key then
        begin
          Lines[i] := Key + '=' + Value;
          Replaced := True;
          Break;
        end;
      end;
    end;
    if not Replaced then
      Lines.Add(Key + '=' + Value);
    Lines.SaveToFile(FilePath);
    Result := True;
  finally
    Lines.Free;
  end;
end;

function IsValidExistingEnv(const FilePath: String): Boolean;
var
  DBUrl, SecretKey: String;
begin
  DBUrl := ReadEnvValue(FilePath, 'DATABASE_URL');
  SecretKey := ReadEnvValue(FilePath, 'SECRET_KEY');
  Result := (Pos('postgresql+psycopg://', DBUrl) = 1) and
    (Pos('@', DBUrl) > 0) and (Length(SecretKey) >= 32);
end;

function PasswordFromInstallerDBUrl(const DBUrl: String): String;
var
  Prefix: String;
  StartPos, EndPos: Integer;
begin
  Result := '';
  Prefix := 'postgresql+psycopg://{#MyDBUser}:';
  if Pos(Prefix, DBUrl) <> 1 then Exit;
  StartPos := Length(Prefix) + 1;
  EndPos := Pos('@', DBUrl);
  if EndPos > StartPos then
    Result := Copy(DBUrl, StartPos, EndPos - StartPos);
end;

function InitializeSetup: Boolean;
begin
  PGInstalled := False;
  PGBinPath := '';
  AppDatabasePassword := '';
  DBCreated := False;
  EnvAlreadyExists := False;
  IsUpgrade := False;
  PGSetupFailed := False;
  InstallationReady := False;
  WasPostgreSQLAlreadyInstalled := False;
  CapturedAppDatabasePassword := '';
  Result := True;
end;

procedure InitializeWizard;
begin
  PGAdminPasswordPage := CreateInputQueryPage(
    wpSelectDir,
    'Conexion con PostgreSQL existente',
    'Credenciales administrativas',
    'Si PostgreSQL ya esta instalado, escriba la contrasena del usuario postgres. ' +
    'No se almacena ni se escribe en los logs. En una instalacion nueva puede dejarla vacia.');
  PGAdminPasswordPage.Add('Contrasena de postgres:', True);

  AppDatabasePasswordPage := CreateInputQueryPage(
    PGAdminPasswordPage.ID,
    'Usuario de base de datos de la aplicacion',
    'Credenciales de inventory_user',
    'Escriba la contrasena REAL del usuario inventory_user. Si existe un .env ' +
    'correcto puede dejarla vacia para reutilizar exactamente su DATABASE_URL.');
  AppDatabasePasswordPage.Add('Contrasena de inventory_user:', True);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  SelectedEnvPath: String;
begin
  Result := True;
  if Assigned(AppDatabasePasswordPage) and
     (CurPageID = AppDatabasePasswordPage.ID) then
  begin
    SelectedEnvPath := AddBackslash(WizardDirValue) + '.env';
    CapturedAppDatabasePassword := AppDatabasePasswordPage.Values[0];
    if (CapturedAppDatabasePassword = '') and
       (not IsValidExistingEnv(SelectedEnvPath)) then
    begin
      MsgBox(
        'Debe escribir la contraseña existente del usuario inventory_user.' + #13#10 +
        'El instalador no continuara sin validar esta credencial.',
        mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  SetupBatch: String;
  OutputFile: String;
  DBUrl: String;
  EnvPath: String;
  SecretKey: String;
  TzName: String;
  PgInstaller: String;
  PgOutput: String;
  PgServiceName: String;
  PgWait: Integer;
  InstallLog: String;
  PostgresSuperuserPassword: String;
  AppPasswordFile: String;
  PostgresPasswordFile: String;
  SetupOutput: AnsiString;
  AppPasswordWasProvided: Boolean;
begin
  if CurStep = ssInstall then
  begin
    EnvPath := ExpandConstant('{app}\.env');
    EnvAlreadyExists := FileExists(EnvPath);
    IsUpgrade := EnvAlreadyExists and IsValidExistingEnv(EnvPath);
    ForceDirectories(ExpandConstant('{app}\installer'));
    InstallLog := ExpandConstant('{app}\installer\install_log.txt');

    LogMessage('=== Installation started ===', InstallLog);

    PGBinPath := FindPostgreSQLBin;
    WasPostgreSQLAlreadyInstalled := PGBinPath <> '';

    if PGBinPath <> '' then
    begin
      PGInstalled := True;
      LogMessage('PostgreSQL found at: ' + PGBinPath, InstallLog);

      if not IsPostgreSQLRunning then
      begin
        LogMessage('PostgreSQL found but not running. Attempting to start...', InstallLog);
        PgServiceName := FindPostgreSQLService;
        if PgServiceName <> '' then
        begin
          Exec('cmd.exe', '/c net start "' + PgServiceName + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
          PgWait := 0;
          while (PgWait < 60) and (not IsPostgreSQLRunning) do
          begin
            Sleep(2000);
            PgWait := PgWait + 2;
          end;
          if not IsPostgreSQLRunning then
          begin
            LogMessage('ERROR: PostgreSQL service could not be started', InstallLog);
            MsgBox(
              'PostgreSQL esta instalado pero el servicio no pudo iniciarse.' + #13#10 +
              'Reinicie el computer y ejecute este instalador de nuevo.' + #13#10 + #13#10 +
              'Log: ' + InstallLog, mbError, MB_OK);
            Abort;
          end;
        end
        else
        begin
          LogMessage('ERROR: No PostgreSQL service found', InstallLog);
          MsgBox(
            'PostgreSQL esta instalado pero no se encontro el servicio de Windows.' + #13#10 +
            'Reinicie el computer y ejecute este instalador de nuevo.' + #13#10 + #13#10 +
            'Log: ' + InstallLog, mbError, MB_OK);
          Abort;
        end;
      end;

      if not IsPostgreSQLRunning then
      begin
        LogMessage('ERROR: PostgreSQL is not responding on port 5432', InstallLog);
        MsgBox(
          'PostgreSQL no responde en el puerto 5432.' + #13#10 +
          'Verifique que el servicio este corriendo y reinicie el instalador.' + #13#10 + #13#10 +
          'Log: ' + InstallLog, mbError, MB_OK);
        Abort;
      end;

      LogMessage('PostgreSQL is running and accepting connections', InstallLog);
    end
    else
    begin
      if IsPort5432Listening then
      begin
        LogMessage('ERROR: Port 5432 is occupied but no PostgreSQL installation was detected', InstallLog);
        MsgBox(
          'El puerto 5432 esta ocupado por otro proceso y no se detecto una ' +
          'instalacion reutilizable de PostgreSQL.' + #13#10 +
          'Libere el puerto o corrija la instalacion parcial antes de reintentar.' + #13#10 + #13#10 +
          'Log: ' + InstallLog, mbError, MB_OK);
        Abort;
      end;

      ExtractTemporaryFile('postgresql-installer.exe');
      PgInstaller := ExpandConstant('{tmp}\postgresql-installer.exe');

      if not FileExists(PgInstaller) then
      begin
        LogMessage('ERROR: postgresql-installer.exe not found', InstallLog);
        MsgBox(
          'PostgreSQL no fue encontrado y el instalador offline no esta disponible.' + #13#10 + #13#10 +
          'Coloque postgresql-installer.exe en la carpeta del instalador' + #13#10 +
          'y ejecute de nuevo.', mbError, MB_OK);
        Abort;
      end;

      AppDatabasePassword := GenerateRandomPassword;
      PostgresSuperuserPassword := AppDatabasePassword;
      PgOutput := ExpandConstant('{app}\installer\pg_install_output.txt');
      LogMessage('Installing PostgreSQL from: ' + PgInstaller, InstallLog);

      { EDB installers require unattendedmodeui for a silent install. Direct
        execution avoids cmd.exe quoting problems with paths containing spaces. }
      Exec(PgInstaller,
        '--mode unattended --unattendedmodeui none --superpassword "' + AppDatabasePassword +
        '" --serverport 5432 --servicepassword "' + AppDatabasePassword +
        '" --debugtrace "' + PgOutput + '"',
        '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

      LogMessage('PostgreSQL installer exit code: ' + IntToStr(ResultCode), InstallLog);

      if ResultCode <> 0 then
      begin
        LogMessage('ERROR: PostgreSQL installer failed with code ' + IntToStr(ResultCode), InstallLog);
        MsgBox(
          'La instalacion de PostgreSQL fallo (codigo: ' + IntToStr(ResultCode) + ').' + #13#10 +
          'Revise el log para mas detalles: ' + PgOutput + #13#10 + #13#10 +
          'Log: ' + InstallLog, mbError, MB_OK);
        Abort;
      end;

      LogMessage('PostgreSQL installer completed. Waiting for service...', InstallLog);

      PgWait := 0;
      PGBinPath := '';
      while (PgWait < 120) do
      begin
        PGBinPath := FindPostgreSQLBin;
        if (PGBinPath <> '') and IsPostgreSQLRunning then
        begin
          PGInstalled := True;
          LogMessage('PostgreSQL service detected and running at: ' + PGBinPath, InstallLog);
          Break;
        end;
        Sleep(2000);
        PgWait := PgWait + 2;
        if (PgWait mod 10 = 0) then
          LogMessage('Waiting for PostgreSQL service... (' + IntToStr(PgWait) + 's)', InstallLog);
      end;

      if not PGInstalled then
      begin
        LogMessage('ERROR: PostgreSQL service not detected after 120 seconds', InstallLog);
        MsgBox(
          'PostgreSQL se instalo pero el servicio no pudo detectarse.' + #13#10 +
          'Es posible que se requiera reiniciar el computer.' + #13#10 + #13#10 +
          'Reinicie y ejecute este instalador de nuevo.' + #13#10 + #13#10 +
          'Log: ' + InstallLog, mbError, MB_OK);
        Abort;
      end;

      if not IsPostgreSQLRunning then
      begin
        LogMessage('ERROR: PostgreSQL installed but not responding', InstallLog);
        MsgBox(
          'PostgreSQL se instalo pero no responde en el puerto 5432.' + #13#10 +
          'Reinicie el computer y ejecute este instalador de nuevo.' + #13#10 + #13#10 +
          'Log: ' + InstallLog, mbError, MB_OK);
        Abort;
      end;
    end;

    AppPasswordWasProvided := CapturedAppDatabasePassword <> '';
    if WasPostgreSQLAlreadyInstalled and AppPasswordWasProvided then
      AppDatabasePassword := CapturedAppDatabasePassword
    else if IsUpgrade then
      AppDatabasePassword := PasswordFromInstallerDBUrl(ReadEnvValue(EnvPath, 'DATABASE_URL'))
    else if WasPostgreSQLAlreadyInstalled then
    begin
      LogMessage('ERROR: Application database password was not provided', InstallLog);
      MsgBox(
        'Debe proporcionar la contrasena existente de inventory_user.' + #13#10 +
        'No se modifico el usuario ni la base de datos.' + #13#10 + #13#10 +
        'Log: ' + InstallLog, mbError, MB_OK);
      Abort;
    end
    else if AppDatabasePassword = '' then
      AppDatabasePassword := GenerateRandomPassword;

    if AppDatabasePassword = '' then
    begin
      LogMessage('ERROR: Existing DATABASE_URL is not compatible with automatic validation', InstallLog);
      MsgBox(
        'El DATABASE_URL existente no pudo validarse automaticamente.' + #13#10 +
        'No se modifico el archivo .env ni la base de datos.' + #13#10 + #13#10 +
        'Log: ' + InstallLog, mbError, MB_OK);
      Abort;
    end;

    if PostgresSuperuserPassword = '' then
      PostgresSuperuserPassword := PGAdminPasswordPage.Values[0];

    if (not IsUpgrade) and (PostgresSuperuserPassword = '') then
    begin
      LogMessage('ERROR: PostgreSQL administrator password was not provided', InstallLog);
      MsgBox(
        'Se requiere la contrasena administrativa de PostgreSQL para verificar ' +
        'la conexion y preparar la base de datos.' + #13#10 + #13#10 +
        'Log: ' + InstallLog, mbError, MB_OK);
      Abort;
    end;

    ExtractTemporaryFile('setup-postgres.bat');
    SetupBatch := ExpandConstant('{tmp}\setup-postgres.bat');
    OutputFile := ExpandConstant('{app}\installer\pg_output.txt');
    LogMessage('Running database setup...', InstallLog);

    PgServiceName := FindPostgreSQLService;
    if PgServiceName = '' then
    begin
      LogMessage('ERROR: No Windows service matches the detected PostgreSQL installation', InstallLog);
      MsgBox(
        'Se encontro PostgreSQL, pero no su servicio de Windows.' + #13#10 +
        'Revise una instalacion parcial antes de reintentar.' + #13#10 + #13#10 +
        'Log: ' + InstallLog, mbError, MB_OK);
      Abort;
    end;

    AppPasswordFile := ExpandConstant('{tmp}\inventory-app-db.credential');
    PostgresPasswordFile := ExpandConstant('{tmp}\inventory-postgres.credential');
    if not SaveStringToFile(AppPasswordFile, AppDatabasePassword, False) then
      Abort;
    if not SaveStringToFile(PostgresPasswordFile, PostgresSuperuserPassword, False) then
    begin
      DeleteFile(AppPasswordFile);
      Abort;
    end;
    Exec('cmd.exe',
      '/d /s /c ""' + SetupBatch + '" "' + PGBinPath + '" {#MyDBName} {#MyDBUser} "' + AppPasswordFile + '" "' + PostgresPasswordFile + '" "' + PgServiceName + '" > "' + OutputFile + '" 2>&1"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    DeleteFile(AppPasswordFile);
    DeleteFile(PostgresPasswordFile);

    LogMessage('Database setup exit code: ' + IntToStr(ResultCode), InstallLog);

    if ResultCode = 0 then
    begin
      DBCreated := True;
      LogMessage('Database and user authenticated successfully', InstallLog);
    end
    else
    begin
      LogMessage('ERROR: Database setup or authenticated validation failed', InstallLog);
      SetupOutput := '';
      LoadStringFromFile(OutputFile, SetupOutput);
      if Pos('ERROR_CODE=INVALID_POSTGRES_PASSWORD', String(SetupOutput)) > 0 then
        MsgBox(
          'La contraseña del usuario postgres no es válida.' + #13#10 + #13#10 +
          'Revise el log: ' + OutputFile, mbError, MB_OK)
      else if Pos('ERROR_CODE=APP_CREDENTIALS_MISMATCH', String(SetupOutput)) > 0 then
        MsgBox(
          'La contraseña del usuario de aplicación no coincide con la configuración existente.' + #13#10 + #13#10 +
          'No se modifico inventory_user ni la base de datos.' + #13#10 +
          'Revise el log: ' + OutputFile, mbError, MB_OK)
      else
        MsgBox(
          'No se pudo configurar o validar la base de datos.' + #13#10 +
          'Revise el log: ' + OutputFile + #13#10 + #13#10 +
          'Log: ' + InstallLog, mbError, MB_OK);
      Abort;
    end;

    if not IsUpgrade then
    begin
      SecretKey := GenerateSecretKey;
      TzName := 'America/Chihuahua';
      DBUrl := 'postgresql+psycopg://{#MyDBUser}:' + AppDatabasePassword + '@localhost:5432/{#MyDBName}';

      if EnvAlreadyExists then
        CopyFile(EnvPath, EnvPath + '.invalid.bak', False);

      with TStringList.Create do
      try
        Add('# Inventory System Configuration');
        Add('# Generated by installer');
        Add('');
        Add('SECRET_KEY=' + SecretKey);
        Add('DATABASE_URL=' + DBUrl);
        Add('HARVEST_TIMEZONE=' + TzName);
        Add('APP_HOST=127.0.0.1');
        Add('APP_PORT=5000');
        Add('SESSION_COOKIE_SECURE=false');
        SaveToFile(EnvPath);
      finally
        Free;
      end;

      LogMessage('.env created with DATABASE_URL and SECRET_KEY', InstallLog);

      MsgBox(
        'Instalacion completada exitosamente.' + #13#10 + #13#10 +
        'Al iniciar la aplicacion, se abrira el asistente de configuracion' + #13#10 +
        'donde podra definir la contrasena del administrador.',
        mbInformation, MB_OK);
    end
    else if IsUpgrade then
    begin
      if AppPasswordWasProvided then
      begin
        DBUrl := 'postgresql+psycopg://{#MyDBUser}:' + AppDatabasePassword +
          '@localhost:5432/{#MyDBName}';
        if not ReplaceEnvValue(EnvPath, 'DATABASE_URL', DBUrl) then
        begin
          LogMessage('ERROR: Validated DATABASE_URL could not be saved', InstallLog);
          Abort;
        end;
        LogMessage('Upgrade: updated only the validated DATABASE_URL', InstallLog);
      end;
      LogMessage('Upgrade: preserving existing .env', InstallLog);

      MsgBox(
        'Actualizacion completada.' + #13#10 + #13#10 +
        'Su configuracion, respaldos y base de datos han sido preservados.',
        mbInformation, MB_OK);
    end;

    LogMessage('=== Installation completed ===', InstallLog);
    InstallationReady := True;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  KeepData: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    if FileExists(ExpandConstant('{app}\.env')) then
    begin
      KeepData := MsgBox(
        'Desea conservar la configuracion, respaldos y base de datos?' + #13#10 + #13#10 +
        '  Si: Conserva todo (recomendado)' + #13#10 +
        '  No: Elimina configuracion y respaldos' + #13#10 + #13#10 +
        'La base de datos NO se eliminara automaticamente.',
        mbConfirmation, MB_YESNO);

      if KeepData = IDNO then
      begin
        if MsgBox(
          'Eliminar configuracion y respaldos? Esta accion no se puede deshacer.',
          mbConfirmation, MB_YESNO) = IDYES then
        begin
          DeleteFile(ExpandConstant('{app}\.env'));
          DelTree(ExpandConstant('{app}\backups'), True, True, True);
          DelTree(ExpandConstant('{app}\logs'), True, True, True);
        end;
      end;
    end;
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if Assigned(PGAdminPasswordPage) and (PageID = PGAdminPasswordPage.ID) then
    Result := (FindPostgreSQLBin = '') or
      IsValidExistingEnv(AddBackslash(WizardDirValue) + '.env');
  if Assigned(AppDatabasePasswordPage) and
     (PageID = AppDatabasePasswordPage.ID) then
    Result := FindPostgreSQLBin = '';
end;
