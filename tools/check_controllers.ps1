$ErrorActionPreference = 'Stop'

$devices = @(Get-CimInstance Win32_PnPEntity |
    Where-Object {
        $_.Name -match 'Xbox|XINPUT|Wireless Controller|DualSense|DualShock|PlayStation|Gamepad' -or
        $_.DeviceID -match 'VID_045E|VID_054C|IG_00'
    } |
    Select-Object Name, Status, PNPClass, DeviceID)

$xbox = $devices | Where-Object { $_.Name -match 'Xbox|XINPUT' -or $_.DeviceID -match 'VID_045E|IG_00' }
$sony = $devices | Where-Object { $_.Name -match 'Wireless Controller|DualSense|DualShock|PlayStation' -or $_.DeviceID -match 'VID_054C' }

$report = [pscustomobject]@{
    checkedAt = (Get-Date).ToString('s')
    xboxControllerDetected = [bool]$xbox
    ps5ControllerDetected = [bool]$sony
    detectedControllerLikeDevices = $devices
    ikemenJoystickSlots = [pscustomobject]@{
        p1 = 0
        p2 = 1
        p3 = 2
        p4 = 3
    }
    expectedMapping = [pscustomobject]@{
        movement = 'D-pad'
        mugenA = 'A / Cross'
        mugenB = 'B / Circle'
        mugenC = 'Right Trigger / R2'
        mugenX = 'X / Square'
        mugenY = 'Y / Triangle'
        mugenZ = 'Right Bumper / R1'
        assistD = 'Left Bumper / L1'
        assistW = 'Left Trigger / L2'
        start = 'Start / Options'
        menu = 'Back / Share'
    }
    note = 'Plug controllers in before launching IKEMEN. If the PS5 pad is not detected as a game controller over Bluetooth, use USB, Steam Input, or DS4Windows Xbox emulation.'
}

$outDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'operator_console\controller_reports'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$out = Join-Path $outDir ("controller_detection_{0}.json" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $out -Encoding UTF8
$report | ConvertTo-Json -Depth 6
Write-Host "Report written to $out"
