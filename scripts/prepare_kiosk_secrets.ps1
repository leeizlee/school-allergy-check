param(
    [Parameter(Mandatory = $true)]
    [string]$SourceEnv,
    [Parameter(Mandatory = $true)]
    [string]$OutputEnv,
    [string]$AdminServerUrl = "https://school-allergy-check.onrender.com"
)

$ErrorActionPreference = "Stop"

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Name
    )

    foreach ($rawLine in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }

        $key, $value = $line.Split("=", 2)
        if ($key.Trim() -ne $Name) {
            continue
        }

        $value = $value.Trim()
        if ($value.Length -ge 2 -and $value[0] -eq $value[$value.Length - 1] -and $value[0] -in @("'", '"')) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        return $value
    }

    return ""
}

$sourcePath = (Resolve-Path -LiteralPath $SourceEnv).Path
$token = Get-EnvValue -Path $sourcePath -Name "KIOSK_SCAN_API_TOKEN"
if ($token.Length -lt 24) {
    throw "KIOSK_SCAN_API_TOKEN is missing or shorter than 24 characters."
}

$outputPath = [System.IO.Path]::GetFullPath($OutputEnv)
$outputDirectory = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$content = @(
    "ADMIN_SERVER_URL=$($AdminServerUrl.TrimEnd('/'))"
    "KIOSK_SCAN_API_TOKEN=$token"
) -join "`n"

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($outputPath, $content + "`n", $utf8NoBom)

Write-Host "Created kiosk secret file: $outputPath"
Write-Host "Token length: $($token.Length)"
