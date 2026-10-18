<# 

    setup_db.ps1 - PostgreSQL database setup for Windows (PowerShell)



    Application: docdata_saas

    Database:    docdata_saas

    DB User:     docdata_saas



    ----------------------------------------------------------------------

    USAGE

    ----------------------------------------------------------------------

    # Basic usage (recommended: uses env vars if set, otherwise prompts):

        powershell -ExecutionPolicy Bypass -File .\setup_db.ps1



    # Optional parameters (override environment variables):

        powershell -ExecutionPolicy Bypass -File .\setup_db.ps1 `

            -DbSuperUser "postgres" `

            -DbHost "localhost" `

            -DbPort 5432



    ----------------------------------------------------------------------

    CREDENTIAL SOURCES

    ----------------------------------------------------------------------

    Superuser username:

      1. -DbSuperUser parameter

      2. PG_SUPERUSER environment variable

      3. Defaults to "postgres"



    Superuser password:

      1. PG_SUPERUSER_PASSWORD environment variable

      2. Interactive prompt (password not echoed)



    Host and port:

      -DbHost parameter or PGHOST env var (default: localhost)

      -DbPort parameter or PGPORT env var (default: 5432)



    ----------------------------------------------------------------------

    WHAT THIS SCRIPT DOES (IDEMPOTENT)

    ----------------------------------------------------------------------

    1. Detects psql.exe location by checking common install paths:

         "C:\Program Files\PostgreSQL\17\bin\psql.exe"

         "C:\Program Files\PostgreSQL\16\bin\psql.exe"

         "C:\Program Files\PostgreSQL\15\bin\psql.exe"

         "C:\Program Files\PostgreSQL\14\bin\psql.exe"

       If none exist, it falls back to searching PATH.

       If still not found, it exits with error code 2.



    2. Connects using a PostgreSQL superuser.



    3. Creates role "docdata_saas" with LOGIN (if it does not exist).



    4. Sets password for "docdata_saas":

       - If PG_DBDATA_SAAS_PASSWORD is set, uses that value.

       - Otherwise, if role already exists, leaves password unchanged.

       - If role is new and no env password is set, a secure random password

         is generated and printed once to the console.



    5. Creates database "docdata_saas" owned by "docdata_saas" (if it does not exist).



    6. Grants all privileges on database "docdata_saas" to role "docdata_saas"

       and sets default privileges so future objects are accessible.



    The script is safe to run multiple times.



    ----------------------------------------------------------------------

    EXIT CODES

    ----------------------------------------------------------------------

      0 - Success

      1 - General error (connection, SQL, etc.)

      2 - psql not found

      3 - User cancelled / prompt aborted



#>



param(

    [string]$DbSuperUser,

    [string]$DbHost,

    [int]$DbPort

)



# Enable strict mode

Set-StrictMode -Version Latest

$ErrorActionPreference = "Stop"



function Write-Info {

    param([string]$Message)

    Write-Host "[INFO ] $Message"

}



function Write-Warn {

    param([string]$Message)

    Write-Warning "$Message"

}



function Write-ErrorMsg {

    param([string]$Message)

    Write-Host "[ERROR] $Message" -ForegroundColor Red

}



function Find-Psql {

    # 1. Check common installation paths (preferred)

    $candidatePaths = @(

        "C:\Program Files\PostgreSQL\17\bin\psql.exe",

        "C:\Program Files\PostgreSQL\16\bin\psql.exe",

        "C:\Program Files\PostgreSQL\15\bin\psql.exe",

        "C:\Program Files\PostgreSQL\14\bin\psql.exe"

    )



    foreach ($path in $candidatePaths) {

        if (Test-Path -LiteralPath $path) {

            Write-Info "Found psql at '$path'"

            return $path

        }

    }



    Write-Warn "psql.exe not found in common PostgreSQL install paths. Falling back to PATH lookup..."



    # 2. Fallback: search in PATH

    try {

        $cmd = Get-Command psql -ErrorAction Stop

        if ($cmd -and (Test-Path -LiteralPath $cmd.Path)) {

            Write-Info "Found psql in PATH at '$($cmd.Path)'"

            return $cmd.Path

        }

    } catch {

        # Ignore, handled below

    }



    return $null

}



function Get-SecurePasswordString {

    param(

        [int]$Length = 32

    )

    # Generate a secure random password suitable for PostgreSQL

    # Alphanumeric + safe symbols
    # Build character array as strings to avoid type conversion issues

    $chars = @()
    for ($c = [int][char]'a'; $c -le [int][char]'z'; $c++) {
        $chars += [char]$c
    }
    for ($c = [int][char]'A'; $c -le [int][char]'Z'; $c++) {
        $chars += [char]$c
    }
    for ($c = [int][char]'0'; $c -le [int][char]'9'; $c++) {
        $chars += [char]$c
    }
    $chars += @('!', '@', '#', '$', '%', '^', '&', '*', '-', '_', '+', '=')

    $bytes = New-Object 'System.Byte[]' ($Length)

    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)



    $resultChars = for ($i = 0; $i -lt $Length; $i++) {

        $chars[$bytes[$i] % $chars.Length]

    }

    -join $resultChars

}



# Resolve psql path

$psqlPath = Find-Psql

if (-not $psqlPath) {

    Write-ErrorMsg "psql.exe not found. Please install PostgreSQL or ensure psql is accessible."

    exit 2

}



# Resolve connection parameters

if (-not $DbSuperUser -or [string]::IsNullOrWhiteSpace($DbSuperUser)) {

    $DbSuperUser = $env:PG_SUPERUSER

}

if (-not $DbSuperUser -or [string]::IsNullOrWhiteSpace($DbSuperUser)) {

    $DbSuperUser = "postgres"

}



if (-not $DbHost -or [string]::IsNullOrWhiteSpace($DbHost)) {

    if ($env:PGHOST) {

        $DbHost = $env:PGHOST

    } else {

        $DbHost = "localhost"

    }

}



if (-not $DbPort -or $DbPort -le 0) {

    $portValue = 0
    if ($env:PGPORT -and [int]::TryParse($env:PGPORT, [ref]$portValue)) {

        $DbPort = $portValue

    } else {

        $DbPort = 5432

    }

}



Write-Info "Using superuser: $DbSuperUser"

Write-Info "Host: $DbHost, Port: $DbPort"



# Get superuser password

$superUserPassword = $env:PG_SUPERUSER_PASSWORD

if (-not $superUserPassword) {

    Write-Info "No PG_SUPERUSER_PASSWORD environment variable found."

    try {

        $securePwd = Read-Host -AsSecureString "Enter password for PostgreSQL superuser '$DbSuperUser' (input hidden)"

        if (-not $securePwd) {

            Write-ErrorMsg "No password entered. Aborting."

            exit 3

        }

        $ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePwd)

        try {

            $superUserPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)

        } finally {

            [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)

        }

    } catch {

        Write-ErrorMsg "Failed to read password from console: $($_.Exception.Message)"

        exit 1

    }

}



# Application-specific constants

$dbName   = "docdata_saas"

$dbUser   = "docdata_saas"

$envPasswordVarName = "PG_DBDATA_SAAS_PASSWORD"

$dbUserPassword = [Environment]::GetEnvironmentVariable($envPasswordVarName)



if ($dbUserPassword) {

    Write-Info "Using database user password from environment variable $envPasswordVarName"

}



# Build base psql arguments (connect to postgres maintenance DB)

$commonArgs = @(

    "-v", "ON_ERROR_STOP=1",

    "-h", $DbHost,

    "-p", $DbPort,

    "-U", $DbSuperUser,

    "-d", "postgres"

)



# Helper to run psql with SQL text

function Invoke-PsqlSql {

    param(

        [string]$Sql,

        [string]$Description

    )



    Write-Info "Executing: $Description"



    $env:PGPASSWORD = $superUserPassword



    $psi = New-Object System.Diagnostics.ProcessStartInfo

    $psi.FileName = $psqlPath

    $psi.Arguments = ($commonArgs | ForEach-Object { if ($_ -match '\s' -or $_ -match '"') { "`"$_`"" } else { $_ } }) -join ' '

    $psi.RedirectStandardOutput = $true

    $psi.RedirectStandardError  = $true

    $psi.RedirectStandardInput   = $true

    $psi.UseShellExecute        = $false



    $proc = New-Object System.Diagnostics.Process

    $proc.StartInfo = $psi



    $null = $proc.Start()

    $writer = $proc.StandardInput
    $writer.Write($Sql)
    if (-not $Sql.EndsWith("`n")) {
        $writer.WriteLine()
    }
    $writer.Close()

    $stdOut = $proc.StandardOutput.ReadToEnd()

    $stdErr = $proc.StandardError.ReadToEnd()

    $proc.WaitForExit()



    if ($stdOut) { Write-Host $stdOut.TrimEnd() }

    if ($proc.ExitCode -ne 0) {

        if ($stdErr) {

            Write-ErrorMsg $stdErr.TrimEnd()

        }

        throw "psql exited with code $($proc.ExitCode) while executing: $Description"

    }

}



try {

    Write-Info "Testing connection to PostgreSQL..."

    Invoke-PsqlSql -Sql "SELECT version();" -Description "Test connection"

} catch {

    Write-ErrorMsg "Unable to connect to PostgreSQL: $($_.Exception.Message)"

    exit 1

}



# Check if role exists

$checkUserSql = @"

SELECT 1

FROM pg_roles

WHERE rolname = '$dbUser';

"@



$userExists = $false

try {

    $env:PGPASSWORD = $superUserPassword



    $psi = New-Object System.Diagnostics.ProcessStartInfo

    $psi.FileName = $psqlPath

    $allArgs = $commonArgs + @("-t", "-A", "-c", $checkUserSql)

    $psi.Arguments = ($allArgs | ForEach-Object { if ($_ -match '\s' -or $_ -match '"') { "`"$_`"" } else { $_ } }) -join ' '

    $psi.RedirectStandardOutput = $true

    $psi.RedirectStandardError  = $true

    $psi.UseShellExecute        = $false



    $proc = New-Object System.Diagnostics.Process

    $proc.StartInfo = $psi



    $null = $proc.Start()

    $stdOut = $proc.StandardOutput.ReadToEnd()

    $stdErr = $proc.StandardError.ReadToEnd()

    $proc.WaitForExit()



    if ($proc.ExitCode -ne 0) {

        if ($stdErr) {

            Write-ErrorMsg $stdErr.TrimEnd()

        }

        throw "Failed to check if role exists."

    }



    if ($stdOut.Trim() -eq "1") {

        $userExists = $true

    }

} catch {

    Write-ErrorMsg "Error while checking if role '$dbUser' exists: $($_.Exception.Message)"

    exit 1

}



if (-not $userExists) {

    Write-Info "Role '$dbUser' does not exist. Creating role..."



    if (-not $dbUserPassword) {

        # Generate a secure random password for the new role

        $dbUserPassword = Get-SecurePasswordString -Length 32

        Write-Warn "Generated a new secure password for role '$dbUser'."

        Write-Warn "Store this password securely. It will not be shown again automatically."

        Write-Host "Generated password for '$dbUser': $dbUserPassword" -ForegroundColor Yellow

    }



    # Use dollar-quoting - in here-string, use backtick to escape $ for literal dollar signs
    $createUserSql = @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$dbUser') THEN
        CREATE ROLE "$dbUser" LOGIN PASSWORD '$dbUserPassword';
    END IF;
END
`$`$;
"@



    try {

        Invoke-PsqlSql -Sql $createUserSql -Description "Create role '$dbUser' if not exists"

    } catch {

        Write-ErrorMsg "Failed to create role '$dbUser': $($_.Exception.Message)"

        exit 1

    }

} else {

    Write-Info "Role '$dbUser' already exists."

    if ($dbUserPassword) {

        Write-Info "Updating password for existing role '$dbUser' from environment variable."

        $alterPwdSql = "ALTER ROLE ""$dbUser"" WITH PASSWORD '$dbUserPassword';"

        try {

            Invoke-PsqlSql -Sql $alterPwdSql -Description "Update password for role '$dbUser'"

        } catch {

            Write-ErrorMsg "Failed to update password for role '$dbUser': $($_.Exception.Message)"

            exit 1

        }

    } else {

        Write-Info "No password env var provided; keeping existing password for '$dbUser'."

    }

}



# Create database if not exists and set owner
# Note: CREATE DATABASE cannot be executed inside a DO block, so we check first and execute separately

$checkDbSql = "SELECT 1 FROM pg_database WHERE datname = '$dbName';"

$dbExists = $false
try {
    $env:PGPASSWORD = $superUserPassword
    
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $psqlPath
    $allArgs = $commonArgs + @("-t", "-A", "-c", $checkDbSql)
    $psi.Arguments = ($allArgs | ForEach-Object { if ($_ -match '\s' -or $_ -match '"') { "`"$_`"" } else { $_ } }) -join ' '
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.UseShellExecute        = $false
    
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $null = $proc.Start()
    $stdOut = $proc.StandardOutput.ReadToEnd()
    $stdErr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    
    if ($proc.ExitCode -eq 0 -and $stdOut.Trim() -eq "1") {
        $dbExists = $true
    }
} catch {
    # Ignore, will try to create
}

if (-not $dbExists) {
    Write-Info "Database '$dbName' does not exist. Creating database..."
    try {
        Invoke-PsqlSql -Sql "CREATE DATABASE `"$dbName`" OWNER `"$dbUser`";" -Description "Create database '$dbName'"
    } catch {
        Write-ErrorMsg "Failed to create database '$dbName': $($_.Exception.Message)"
        exit 1
    }
} else {
    Write-Info "Database '$dbName' already exists. Setting owner..."
    # Terminate connections and set owner
    $terminateSql = @"
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$dbName'
  AND pid <> pg_backend_pid();
"@
    try {
        Invoke-PsqlSql -Sql $terminateSql -Description "Terminate connections to '$dbName'"
        Invoke-PsqlSql -Sql "ALTER DATABASE `"$dbName`" OWNER TO `"$dbUser`";" -Description "Set owner of '$dbName'"
    } catch {
        Write-ErrorMsg "Failed to configure database '$dbName': $($_.Exception.Message)"
        exit 1
    }
}



# Grant privileges and set default privileges
# Note: \connect is a psql meta-command, not SQL. We need separate invocations for different databases.

# First, grant database-level privileges (connect to postgres)
$grantDbSql = @"
GRANT ALL PRIVILEGES ON DATABASE "$dbName" TO "$dbUser";
REVOKE ALL ON DATABASE "$dbName" FROM PUBLIC;
"@

# Then, grant schema-level privileges (connect to the target database)
$grantSchemaSql = @"
GRANT ALL PRIVILEGES ON SCHEMA public TO "$dbUser";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "$dbUser";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO "$dbUser";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO "$dbUser";
"@



try {

    Write-Info "Granting privileges and setting default privileges for '$dbUser' on '$dbName'..."

    # Grant database-level privileges (connect to postgres)
    try {
        Invoke-PsqlSql -Sql $grantDbSql -Description "Grant database privileges on '$dbName' to '$dbUser'"
    } catch {
        Write-ErrorMsg "Failed to grant database privileges: $($_.Exception.Message)"
        exit 1
    }

    # Grant schema-level privileges (connect to target database)
    # Build args for connecting to the target database
    $targetDbArgs = @(
        "-v", "ON_ERROR_STOP=1",
        "-h", $DbHost,
        "-p", $DbPort,
        "-U", $DbSuperUser,
        "-d", $dbName
    )

    $env:PGPASSWORD = $superUserPassword

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $psqlPath
    $psi.Arguments = ($targetDbArgs | ForEach-Object { if ($_ -match '\s' -or $_ -match '"') { "`"$_`"" } else { $_ } }) -join ' '
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.RedirectStandardInput   = $true
    $psi.UseShellExecute        = $false

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi

    $null = $proc.Start()
    $writer = $proc.StandardInput
    $writer.Write($grantSchemaSql)
    if (-not $grantSchemaSql.EndsWith("`n")) {
        $writer.WriteLine()
    }
    $writer.Close()

    $stdOut = $proc.StandardOutput.ReadToEnd()
    $stdErr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()

    if ($stdOut) { Write-Host $stdOut.TrimEnd() }

    if ($proc.ExitCode -ne 0) {
        if ($stdErr) {
            Write-ErrorMsg $stdErr.TrimEnd()
        }
        throw "psql exited with code $($proc.ExitCode) while granting schema privileges."
    }

} catch {
    Write-ErrorMsg "Failed to grant privileges on '$dbName' to '$dbUser': $($_.Exception.Message)"
    exit 1
}



Write-Host "Database setup completed successfully for '$dbName' with user '$dbUser'." -ForegroundColor Green

exit 0