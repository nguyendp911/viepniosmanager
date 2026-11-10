# Download the unsigned iOS build for an exact ViePN main commit.
# Uses authenticated GitHub CLI; does not access or store Apple credentials.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{40}$')][string]$Commit,
    [string]$Destination = 'C:\ViePN-iOS-Manager'
)
$ErrorActionPreference = 'Stop'
$Repo = 'nguyendp911/viepniosmanager'
$Name = 'ViePNMobile-unsigned-ipa'
$root = [IO.Path]::GetFullPath($Destination)
$ipaDir = Join-Path $root 'IPA'
$stage = $null
try {
    if (-not (Get-Command gh.exe -ErrorAction SilentlyContinue)) {
        Write-Warning 'iOS IPA not downloaded: GitHub CLI (gh) is missing. Install https://cli.github.com/ then run gh auth login.'
        return
    }
    & gh.exe auth status --hostname github.com 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'iOS IPA not downloaded: sign in to GitHub CLI once using gh auth login.'
        return
    }
    Write-Host "[ViePN] Looking for successful iOS build of commit $($Commit.Substring(0,12))..."
    # GitHub Actions artifacts are tied to workflow runs, not direct raw GitHub URLs.
    $json = & gh.exe run list --repo $Repo --workflow ci.yml --commit $Commit --limit 20 --json databaseId,headSha,conclusion,status
    if ($LASTEXITCODE -ne 0) { throw 'Could not list GitHub Actions runs.' }
    $runs = @($json | ConvertFrom-Json)
    $run = @($runs | Where-Object {
        $_.headSha -eq $Commit -and $_.conclusion -eq 'success' -and $_.status -eq 'completed'
    } | Select-Object -First 1)
    if ($run.Count -eq 0) {
        Write-Warning "No successful complete CI workflow for this commit yet. Check https://github.com/$Repo/actions and retry Update-ViePN.bat later."
        return
    }
    $stage = Join-Path $env:TEMP ('ViePN-iOS-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    & gh.exe run download ([string]$run[0].databaseId) --repo $Repo --name $Name --dir $stage
    if ($LASTEXITCODE -ne 0) { throw 'iOS artifact unavailable or expired.' }
    $ipa = Join-Path $stage 'ViePNMobile-UNSIGNED.ipa'
    if (-not (Test-Path -LiteralPath $ipa -PathType Leaf)) { throw 'Downloaded artifact has no ViePNMobile-UNSIGNED.ipa.' }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($ipa)
    try {
        $plist = @($zip.Entries | Where-Object { $_.FullName -match '^Payload/[^/]+\.app/Info\.plist$' })
        if ($plist.Count -ne 1) { throw 'Downloaded IPA is invalid: expected one app Info.plist.' }
    } finally { $zip.Dispose() }
    if (-not (Test-Path -LiteralPath $ipaDir)) { New-Item -Path $ipaDir -ItemType Directory -Force | Out-Null }
    $target = Join-Path $ipaDir ("ViePNMobile-main-$($Commit.Substring(0,12))-UNSIGNED.ipa")
    # Use the commit in the filename; never overwrite an existing signed IPA.
    if (Test-Path -LiteralPath $target) {
        Write-Host "[OK] Matching iOS IPA already exists: $target" -ForegroundColor Green
        return
    }
    $temporary = Join-Path $ipaDir ('.viepn-' + [guid]::NewGuid().ToString('N') + '.ipa')
    try {
        Copy-Item -LiteralPath $ipa -Destination $temporary -ErrorAction Stop
        $expected = (Get-FileHash -LiteralPath $ipa -Algorithm SHA256).Hash
        $actual = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash
        if ($actual -ne $expected) { throw 'Downloaded IPA checksum mismatch.' }
        Move-Item -LiteralPath $temporary -Destination $target -ErrorAction Stop
    } finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force } }
    Write-Host "[OK] iOS IPA saved: $target" -ForegroundColor Green
    Write-Host '[NOTE] UNSIGNED IPA: import into ViePN and sign with an eligible Apple certificate/profile before installing.'
} catch {
    Write-Warning ("iOS IPA download failed (Windows update is unaffected): " + $_.Exception.Message)
} finally {
    if ($stage -and (Test-Path -LiteralPath $stage)) { Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue }
}
