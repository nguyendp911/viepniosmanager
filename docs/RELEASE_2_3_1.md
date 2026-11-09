# ViePN iOS Manager v2.3.1 — Fix zsign Chưa cài (Windows)

This stable hotfix addresses the Windows dashboard incorrectly showing **zsign: Chưa cài** even when the official portable ZIP includes its checksum-pinned bundled signer.

## Fixes

- All P12 signing jobs now locate and execute the bundled `backend/viepn/applekit/vendor/zsign.exe` when the configured signer is the default `zsign`, without editing Windows PATH.
- Dashboard `/api/overview` uses the same resolver as the signing engine, so **zsign: Sẵn sàng** reflects the actual executable.
- Dashboard now recognizes P12 + provisioning profile imported using local `Import-ViePN-Certificate.bat`, not just legacy environment variables.
- Explicit custom signer paths stay explicit; if missing, signing fails with a useful error instead of silently running something else.
- Added regression tests for bundled signer lookup, dashboard statuses, and signing command resolution.
- Includes the Ad Hoc certificate signing and Tailscale OTA workflow introduced in 2.3.0.

## Upgrade on Windows

1. Close all running ViePN windows and any signing jobs.
2. Run `C:\ViePN-iOS-Manager\Update-ViePN.bat`. Alternatively, download the **ViePN-Windows-Portable-2.3.1.zip** from this Release, extract and run `Install-ViePN.bat`.
3. Open `C:\ViePN-iOS-Manager\Start-ViePN.bat`.
4. In the Windows dashboard `http://127.0.0.1:8765`, check **Công cụ hệ thống → zsign: Sẵn sàng**.
5. Check file `C:\ViePN-iOS-Manager\backend\viepn\applekit\vendor\zsign.exe` exists. If not, re-run the checksum-verified official installer.
6. Your P12 and profile remain on the local machine; the updater does not upload them.

**Important:** `zsign: Sẵn sàng` means the signer executable is discoverable; it does not prove a particular IPA has been signed. For an Ad Hoc IPA, use **Ký IPA Ad Hoc không cần USB**, check the signing job succeeded, then choose the **new signed IPA** to create an OTA install link. The **Gửi lệnh cài lên iPhone** button is the separate Apple usbmux installation workflow and requires an appropriately signed IPA and a device paired with Windows.

The iOS release asset is **unsigned**, and device signing, provisioning and actual iPhone installation are not validated by CI.
