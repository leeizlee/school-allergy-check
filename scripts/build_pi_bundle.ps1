$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$deployRoot = Join-Path $repoRoot "deploy"
$bundleDir = Join-Path $deployRoot "raspberry_pi"
$oneFileDir = Join-Path $deployRoot "raspberry_pi_onefile"
$runtimeDir = Join-Path $bundleDir "runtime"
$zipPath = Join-Path $deployRoot "raspberry_pi_bundle.zip"
$oneFileZipPath = Join-Path $deployRoot "raspberry_pi_onefile.zip"

function Get-LocalSecretValue {
    param([string]$Key)

    $localSecretsPath = Join-Path $repoRoot "config\local_secrets.bat"
    if (-not (Test-Path $localSecretsPath)) {
        return ""
    }

    foreach ($rawLine in Get-Content -LiteralPath $localSecretsPath -Encoding utf8) {
        $line = $rawLine.Trim()
        if (-not $line.StartsWith("set ", [System.StringComparison]::OrdinalIgnoreCase)) {
            continue
        }

        $assignment = $line.Substring(4).Trim()
        if ($assignment.StartsWith('"') -and $assignment.EndsWith('"') -and $assignment.Length -ge 2) {
            $assignment = $assignment.Substring(1, $assignment.Length - 2)
        }

        $separatorIndex = $assignment.IndexOf("=")
        if ($separatorIndex -lt 1) {
            continue
        }

        $name = $assignment.Substring(0, $separatorIndex).Trim()
        if ($name -eq $Key) {
            return $assignment.Substring($separatorIndex + 1)
        }
    }

    return ""
}

function ConvertTo-ShellSingleQuoted {
    param([string]$Value)

    return "'" + $Value.Replace("'", "'\''") + "'"
}

$script:Utf8NoBomEncoding = New-Object System.Text.UTF8Encoding -ArgumentList $false

function Set-Utf8NoBomFile {
    param(
        [string]$Path,
        [string]$Value
    )

    $normalizedValue = $Value -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText($Path, $normalizedValue, $script:Utf8NoBomEncoding)
}

if (Test-Path $bundleDir) {
    Remove-Item -LiteralPath $bundleDir -Recurse -Force
}

if (Test-Path $oneFileDir) {
    Remove-Item -LiteralPath $oneFileDir -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $bundleDir, $runtimeDir, $oneFileDir | Out-Null

Copy-Item -LiteralPath (Join-Path $repoRoot "app_kiosk.py") -Destination (Join-Path $bundleDir "app_kiosk.py") -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "app_kiosk.py") -Destination (Join-Path $oneFileDir "app_kiosk.py") -Force

Set-Utf8NoBomFile -Path (Join-Path $bundleDir "requirements.txt") -Value @'
requests
lgpio
spidev
'@

Set-Utf8NoBomFile -Path (Join-Path $bundleDir "start_kiosk.sh") -Value @'
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f "./kiosk_secrets.env" ]; then
  set -a
  . ./kiosk_secrets.env
  set +a
fi

export ADMIN_SERVER_DISCOVERY_URL="https://leeizlee.github.io/school-allergy-check/latest-url.json"
: "${KIOSK_SCAN_API_TOKEN:?Set KIOSK_SCAN_API_TOKEN in kiosk_secrets.env before running this kiosk}"
export NGROK_URL_FILE="runtime/ngrok_url.txt"
export PYTHONIOENCODING="utf-8"
export PYTHONUNBUFFERED="1"

python3 app_kiosk.py
'@

Set-Utf8NoBomFile -Path (Join-Path $bundleDir "README.md") -Value @'
# Raspberry Pi Kiosk Bundle

## Files
- `app_kiosk.py`: RFID kiosk server
- `requirements.txt`: Python packages for Raspberry Pi
- `start_kiosk.sh`: simple launcher
- `kiosk.service.example`: systemd service template
- `kiosk_secrets.example.env`: sample local kiosk secret file
- `runtime/`: optional fallback folder

## What this bundle does
- Reads RFID cards on the Raspberry Pi
- Fetches the current admin server URL from:
  - `https://leeizlee.github.io/school-allergy-check/latest-url.json`
- Sends scan results to the admin server

## 1. Copy to Raspberry Pi
Copy the entire `raspberry_pi` folder to the Pi.

Suggested location:
- `/home/pi/raspberry_pi`

## 2. Enable SPI
```bash
sudo raspi-config
```
- Interface Options
- SPI
- Enable

## 3. Install packages
```bash
sudo apt update
sudo apt install -y python3-pip python3-dev python3-tk build-essential
cd /home/pi/raspberry_pi
python3 -m pip install -r requirements.txt
```

## 4. Run manually
Create the local kiosk secret file first:

```bash
cd /home/pi/raspberry_pi
cp kiosk_secrets.example.env kiosk_secrets.env
nano kiosk_secrets.env
```

Put the same `KIOSK_SCAN_API_TOKEN` value that the admin server uses.

```bash
cd /home/pi/raspberry_pi
chmod +x start_kiosk.sh
./start_kiosk.sh
```

## 5. Optional: run on boot with systemd
1. Copy `kiosk.service.example` to `/etc/systemd/system/kiosk.service`
2. Replace `__APP_DIR__` with your real install path
3. Enable the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable kiosk.service
sudo systemctl start kiosk.service
sudo systemctl status kiosk.service
```

## Notes
- If you change the GitHub Pages repo or discovery URL, edit `start_kiosk.sh`
- `kiosk_secrets.env` is a private local file. Do not upload it to GitHub.
- `runtime/ngrok_url.txt` is only a fallback; the main discovery path is the JSON URL above
'@

Set-Utf8NoBomFile -Path (Join-Path $bundleDir "kiosk.service.example") -Value @'
[Unit]
Description=RFID Kiosk Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=__APP_DIR__
EnvironmentFile=-__APP_DIR__/kiosk_secrets.env
Environment=ADMIN_SERVER_DISCOVERY_URL=https://leeizlee.github.io/school-allergy-check/latest-url.json
Environment=NGROK_URL_FILE=runtime/ngrok_url.txt
Environment=PYTHONIOENCODING=utf-8
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 __APP_DIR__/app_kiosk.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
'@

$kioskToken = $env:KIOSK_SCAN_API_TOKEN
if (-not $kioskToken) {
    $kioskToken = Get-LocalSecretValue "KIOSK_SCAN_API_TOKEN"
}

Set-Utf8NoBomFile -Path (Join-Path $bundleDir "kiosk_secrets.example.env") -Value @'
# Optional after cloud deployment:
# ADMIN_SERVER_URL=https://your-admin-server.example.com
KIOSK_SCAN_API_TOKEN=replace-with-the-same-token-as-admin-server
'@

if ($kioskToken) {
    Set-Utf8NoBomFile -Path (Join-Path $bundleDir "kiosk_secrets.env") -Value ("KIOSK_SCAN_API_TOKEN=" + (ConvertTo-ShellSingleQuoted $kioskToken) + "`n")
}

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

if (Test-Path $oneFileZipPath) {
    Remove-Item -LiteralPath $oneFileZipPath -Force
}

Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $zipPath -Force
Compress-Archive -Path (Join-Path $oneFileDir "*") -DestinationPath $oneFileZipPath -Force

Write-Host "Created Raspberry Pi bundle:"
Write-Host " - $bundleDir"
Write-Host " - $zipPath"
Write-Host "Created Raspberry Pi one-file bundle:"
Write-Host " - $oneFileDir"
Write-Host " - $oneFileZipPath"
