$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$deployRoot = Join-Path $repoRoot "deploy"
$localSecretsPath = Join-Path $repoRoot "config\local_secrets.bat"
$serviceAccountPath = Join-Path $repoRoot "config\service_account.json"
$outputPath = Join-Path $deployRoot "render_env_private.env"

function New-UrlSafeSecret {
    param([int]$BytesLength)

    $bytes = New-Object byte[] $BytesLength
    $rng = [System.Security.Cryptography.RNGCryptoServiceProvider]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Get-LocalSecretValues {
    param([string]$Path)

    $values = @{}
    if (-not (Test-Path $Path)) {
        throw "Missing local secrets file: $Path"
    }

    foreach ($rawLine in Get-Content -LiteralPath $Path -Encoding Default) {
        if ($rawLine -match '^\s*set\s+"?([^=]+)=(.*)"?\s*$') {
            $key = $Matches[1]
            $value = $Matches[2]
            if ($value.EndsWith('"')) {
                $value = $value.Substring(0, $value.Length - 1)
            }
            $values[$key] = $value
        }
    }

    return $values
}

function Add-SecretIfMissing {
    param(
        [string]$Key,
        [string]$Value
    )

    $text = Get-Content -LiteralPath $localSecretsPath -Raw -Encoding Default
    if ($text -notmatch ('(?m)^\s*set\s+"?' + [regex]::Escape($Key) + '=')) {
        Add-Content -LiteralPath $localSecretsPath -Encoding Default -Value ('set "' + $Key + '=' + $Value + '"')
    }
}

function Set-Utf8NoBomFile {
    param(
        [string]$Path,
        [string]$Value
    )

    $encoding = New-Object System.Text.UTF8Encoding -ArgumentList $false
    [System.IO.File]::WriteAllText($Path, ($Value -replace "`r`n", "`n"), $encoding)
}

New-Item -ItemType Directory -Force -Path $deployRoot | Out-Null

Add-SecretIfMissing "FLASK_SECRET_KEY" (New-UrlSafeSecret 48)
Add-SecretIfMissing "DEFAULT_STUDENT_PASSWORD" (New-UrlSafeSecret 18)
Add-SecretIfMissing "PUBLIC_ADMIN_URL" "https://replace-after-render-deploy.onrender.com"
Add-SecretIfMissing "RFID_DASHBOARD_URL" "https://replace-after-render-deploy.onrender.com/kiosk"

if (-not (Test-Path $serviceAccountPath)) {
    throw "Missing service account file: $serviceAccountPath"
}

$values = Get-LocalSecretValues $localSecretsPath
$serviceAccountB64 = [Convert]::ToBase64String([System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $serviceAccountPath)))

$envValues = [ordered]@{
    APP_ENV = "production"
    SESSION_COOKIE_SECURE = "1"
    SESSION_TIMEOUT_MINUTES = "60"
    FLASK_SECRET_KEY = $values["FLASK_SECRET_KEY"]
    KIOSK_SCAN_API_TOKEN = $values["KIOSK_SCAN_API_TOKEN"]
    DEFAULT_STUDENT_PASSWORD = $values["DEFAULT_STUDENT_PASSWORD"]
    SERVICE_ACCOUNT_JSON_B64 = $serviceAccountB64
    OPENAI_API_KEY = $values["OPENAI_API_KEY"]
    MENU_SHEET_ID = $values["MENU_SHEET_ID"]
    STUDENT_SHEET_ID = $values["STUDENT_SHEET_ID"]
    LOGIN_SHEET_ID = $values["LOGIN_SHEET_ID"]
    LOG_SHEET_ID = $values["LOG_SHEET_ID"]
    PUBLIC_ADMIN_URL = $values["PUBLIC_ADMIN_URL"]
    RFID_DASHBOARD_URL = $values["RFID_DASHBOARD_URL"]
}

$lines = foreach ($item in $envValues.GetEnumerator()) {
    if (-not [string]$item.Value) {
        throw "Missing value for $($item.Key)"
    }
    "$($item.Key)=$($item.Value)"
}

Set-Utf8NoBomFile -Path $outputPath -Value (($lines -join "`n") + "`n")

Write-Host "Created private Render environment file:"
Write-Host " - $outputPath"
Write-Host "Values were not printed. Do not upload this file to GitHub."
