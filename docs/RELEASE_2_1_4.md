# ViePN 2.1.4 Stable — Windows BAT installer fixes

## Resolved
- Fixed `Resolve-Path : Illegal characters in path` when `Install-ViePN.bat` is started from a ZIP extraction directory such as `C:\Users\NGUYENDP\Downloads\ViePN-Windows-Portable-2.1.2`.
- The launcher no longer passes a quoted `-Source` path ending with a backslash, which could cause Windows command-line argument parsing to merge the next argument.
- Switched Windows installer SHA-256 checks to a streamed built-in .NET cryptography implementation to work on Windows PowerShell without depending on the `Get-FileHash` cmdlet.
- GitHub Actions now runs **the actual `Install-ViePN.bat`**, not only the underlying PowerShell script, in an isolated Windows installation test.

## Install
1. Download `ViePN-Windows-Portable-2.1.4.zip` and `ViePN-Windows-Portable-2.1.4.sha256` from this release; verify checksum.
2. Close ViePN API and gateway windows, unzip to a **new temporary folder**, and run `Install-ViePN.bat` within it.
3. After successful installation, open `C:\ViePN-iOS-Manager\Start-ViePN.bat`.
4. From then on, `C:\ViePN-iOS-Manager\Update-ViePN.bat` updates the stable Windows source and downloads the matching iOS IPA to `C:\ViePN-iOS-Manager\IPA`.

User data, IPA library, token, and Apple sessions in `%LOCALAPPDATA%\ViePN-iOS-Manager` are preserved. Replaced code is backed up in `code-backups`.

## Important
- Windows remains an unsigned Portable ZIP/BAT/PowerShell build, **not a signed MSI/EXE**.
- iPhone IPA `ViePNMobile-2.1.4-UNSIGNED.ipa` is unsigned and must be signed with an appropriate Apple certificate and provisioning profile before installing on a device.
- CI tests package integrity and Windows installation, but cannot confirm operation in every individual Windows/iPhone environment.
