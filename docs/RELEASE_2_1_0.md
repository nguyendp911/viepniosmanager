# ViePN iOS Manager 2.1.0 — Official GitHub Release

**Release channel:** Stable source distribution. **Windows portable ZIP is not Authenticode-signed** and **the iOS IPA is unsigned**. No Apple-issued P12/mobileprovision, code-signing certificate, notarization, or device install test was provided. The word “official” indicates a versioned release from this project's GitHub repository, **not Apple's approval**.

## Downloads
- `ViePN-Windows-Portable-2.1.0.zip`: source-based Windows portable installer, verifies a file manifest before installing.
- `ViePN-Windows-Portable-2.1.0.sha256`: SHA-256 for the above ZIP; verify before extracting.
- `ViePNMobile-2.1.0-UNSIGNED.ipa`: Apple device build **requiring signing** before installation. Do not install unsigned IPA directly.

## Changes
- 1.6: pre-delete local IPA/profile/SQLite backups with SHA-256, offline recovery, Connection Doctor.
- 1.7: searchable IPA build manager and Dev/Test/Stable/Archive channels.
- 1.8: deduplicated renewal jobs, bounded manual sign/renew retries and capped backoff.
- 2.0: improved iPhone dashboard, diagnostic panel and accessible web layout.
- 2.1: portable verified Windows installer and CI release artifacts.

## Windows installation
1. Download the ZIP and SHA-256 from **this release**. Verify SHA-256 with `Get-FileHash ViePN-Windows-Portable-2.1.0.zip -Algorithm SHA256` against the supplied file.
2. Stop existing ViePN API and remote gateway windows; unzip the downloaded ZIP to a temporary directory.
3. Double-click `Install-ViePN.bat` inside the extracted directory, then run `C:\ViePN-iOS-Manager\Start-ViePN.bat`.
4. Your existing IPA, Apple session and dashboard token within `%LOCALAPPDATA%\ViePN-iOS-Manager` are preserved; back these up independently before upgrading.
5. Use Tailscale Serve HTTPS for private remote access, not port forwarding or Funnel.

## Limitations
- The installer is a **ZIP with PowerShell/BAT**, not a digitally-signed EXE/MSI.
- The IPA has **not been signed** and cannot be installed on a non-jailbroken iPhone without valid signing.
- Apple ID auth/2FA and signing/in-place install using a real iPhone have not been validated in the user's environment. CI success confirms unit tests and compilation, not operational success.
- Credentials, bearer tokens, pairings and personal IPA archives are **never bundled** in these assets.
