# ViePN iOS Manager 2.1.3 — Windows Installer Hotfix

**Stable hotfix.** Repairs the `Resolve-Path : Illegal characters in path` error when launching `Install-ViePN.bat` from a Windows ZIP extraction directory.

## Fixed
- The Windows BAT previously passed a quoted source directory ending with `\` to PowerShell. Windows command-line quoting could combine `-Source` with `-Destination` and produce an illegal path. The BAT now lets the installer script resolve its source directory itself.
- CI now exercises the **actual** `Install-ViePN.bat` entry point on Windows, with an isolated test installation destination, in addition to the PowerShell syntax test and existing installer tests.
- Maintains the one-click `Update-ViePN.bat` for updating Windows files from verified stable GitHub Releases and downloading the matching unsigned IPA into `C:\ViePN-iOS-Manager\IPA`.

## Install or update
- If your existing ViePN version has a working `Update-ViePN.bat`, run it to obtain the latest stable release after it is published.
- If you're still on 2.1.2 and `Install-ViePN.bat` fails, either download the 2.1.3 ZIP and run its fixed BAT, or run this command using the extracted 2.1.2 source (if the files exist):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\NGUYENDP\Downloads\ViePN-Windows-Portable-2.1.2\windows\install-portable.ps1" -Destination "C:\ViePN-iOS-Manager"
```

Stop ViePN backend/gateway before installing. Data inside `%LOCALAPPDATA%\ViePN-iOS-Manager` is not overwritten; the installer backs up replaced code into `code-backups`.

**This is a portable ZIP/PowerShell installation (not signed MSI/EXE).** iOS `.ipa` is **unsigned** and must be signed before installation on iPhone.
