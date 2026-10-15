# PowerShell release packaging script for CCC Wake'n'Bake Membership Entitlements
$ErrorActionPreference = 'Stop'
$deployDir = $PSScriptRoot
$pluginDir = Join-Path $deployDir 'ccc-wnb-membership-entitlements'
$baselineZip = Join-Path $deployDir 'ccc-wnb-membership-entitlements-v0.4.0-baseline.zip'
$baselineSha = Join-Path $deployDir 'ccc-wnb-membership-entitlements-v0.4.0-baseline.zip.sha256'
$mx4bZip = Join-Path $deployDir 'ccc-wnb-membership-entitlements-v0.4.0-mx4b.zip'
$mx4bSha = Join-Path $deployDir 'ccc-wnb-membership-entitlements-v0.4.0-mx4b.zip.sha256'
$activeZip = Join-Path $deployDir 'ccc-wnb-membership-entitlements.zip'
$activeSha = Join-Path $deployDir 'ccc-wnb-membership-entitlements.zip.sha256'

# 1. Ensure baseline is preserved
if (!(Test-Path $baselineZip)) {
    if (Test-Path $activeZip) {
        Copy-Item $activeZip $baselineZip
        $h = (Get-FileHash $baselineZip -Algorithm SHA256).Hash
        Set-Content $baselineSha ($h + "`n")
        Write-Host "Preserved baseline ZIP: $baselineZip (SHA: $h)"
    }
}

# 2. Build MX-4B release ZIP using tar
Set-Location $deployDir
if (Test-Path $mx4bZip) { Remove-Item $mx4bZip -Force }
& tar.exe -a -cf ccc-wnb-membership-entitlements-v0.4.0-mx4b.zip ccc-wnb-membership-entitlements
$hMx4b = (Get-FileHash $mx4bZip -Algorithm SHA256).Hash
Set-Content $mx4bSha ($hMx4b + "`n")
Write-Host "Packaged MX-4B ZIP: $mx4bZip (SHA: $hMx4b)"

# 3. Mirror into active release ZIP
Copy-Item $mx4bZip $activeZip -Force
Set-Content $activeSha ($hMx4b + "`n")
Write-Host "Updated active ZIP: $activeZip (SHA: $hMx4b)"

# 4. Verify contents
Write-Host "`nContents of ${activeZip}:"
& tar.exe -tf $activeZip
