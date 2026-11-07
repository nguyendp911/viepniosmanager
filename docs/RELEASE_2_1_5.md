# ViePN iOS Manager 2.1.5 — Fix verified backup before deleting IPA

This Stable hotfix addresses the Windows-side message:

> Không thể sao lưu IPA trước khi xóa: Windows đang khóa một file hoặc từ chối quyền đọc/ghi.

## Fixes
- Changes local backup to **read each IPA once** while streaming into its ZIP, eliminating unnecessary additional file reads that can collide with Windows antivirus scanning and sharing locks.
- Retries transient Windows PermissionError failures at most 3 times.
- Verifies ZIP checksums before committing the backup file; if any IPA/profile is missing, corrupt or inaccessible, **nothing is deleted**.
- The error response now identifies the failed backup operation and an IPA/profile SHA prefix, without exposing paths, Apple ID, sessions or credentials.
- Fix applies to both Windows web dashboard and iPhone remote management, which share the Windows backend.

## Upgrade
- If using ViePN 2.1.4+, run `C:\ViePN-iOS-Manager\Update-ViePN.bat` to install the latest Stable GitHub Release, then run `Start-ViePN.bat`.
- Otherwise download the Windows Portable ZIP, verify its SHA256, extract and install using `Install-ViePN.bat`. Stop ViePN backend and gateway before installing.
- The IPA Release file is unsigned, requires valid signing before iPhone installation. The updated Windows backend is what fixes the deletion problem; iOS IPA reinstallation is not necessary for the backup error message.

## If the error persists
Use the new stage/SHA detail to identify which local file or step fails. Check your user's Windows backup directory permissions and available disk space; avoid disabling antivirus or weakening filesystem permissions. No destructive action takes place if the snapshot fails.
