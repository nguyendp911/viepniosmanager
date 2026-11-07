# ViePN iOS Manager 2.1.2 — Automatic Update

**Stable release:** One-click update of Windows source and iOS IPA.

## New updater
- `Update-ViePN.bat` (installed in `C:\ViePN-iOS-Manager`) fetches the newest **stable GitHub Release** directly from this repository.
- Verifies the published SHA-256 for the Windows Portable ZIP **and** unsigned iOS IPA before making changes.
- Extracts and updates Windows source into `C:\ViePN-iOS-Manager`, with old source backed up in `code-backups` by the checksum-verified installer.
- Downloads `ViePNMobile-VERSION-UNSIGNED.ipa` to `C:\ViePN-iOS-Manager\IPA`. Old downloaded IPA builds are preserved.
- If the ViePN API/gateway are running, the updater checks the job state; it refuses to stop active signing/installing/renewal jobs or unknown processes.
- Preserves `%LOCALAPPDATA%\ViePN-iOS-Manager` (IPA library, SQLite, Apple sessions and dashboard token) and other personal folders.

## First upgrade from 2.1.1
Download `ViePN-Windows-Portable-2.1.2.zip` and SHA-256 from this release, check the ZIP hash, unzip it and run `Install-ViePN.bat` once. After this, use **`Update-ViePN.bat` for future versions**, followed by `Start-ViePN.bat` to launch services.

## Files
- `ViePN-Windows-Portable-2.1.2.zip` — Windows source, installer and updater BAT.
- `ViePN-Windows-Portable-2.1.2.sha256` — Windows ZIP checksum.
- `ViePNMobile-2.1.2-UNSIGNED.ipa` — iPhone build, not signed.
- `ViePNMobile-2.1.2-UNSIGNED.ipa.sha256` — iPhone IPA checksum.

**Limitations:** This remains a portable BAT/PowerShell distribution, not a signed MSI/EXE. The iOS IPA is **unsigned** and requires valid provisioning/signing before installing. No credentials or personal data are packed into the release. CI validates packaging and compilation; hardware workflows on your computer/iPhone need local testing.
