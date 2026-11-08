# ViePN 2.2.0 — Tailscale Device Registration + Bluetooth LE Discovery

**Scope:** ViePN iOS can now register itself as a **remote device** with ViePN Windows using its existing authenticated Tailscale HTTPS connection. Optional Bluetooth Low Energy (BLE) discovery can detect when the *ViePN app* is running near the Windows PC (Windows needs Bluetooth LE hardware). No USB cable is needed **to register or display the remote device**.

### First-time setup

1. On Windows, update to 2.2.0 using `C:\ViePN-iOS-Manager\Update-ViePN.bat`. Restart the unified `Start-ViePN.bat`.
2. Optional nearby BLE support (Windows): run `C:\ViePN-iOS-Manager\windows\Enable-ViePN-Bluetooth.bat` **once**. This installs the Python Bleak library into ViePN's isolated `.venv`. Windows must have a BLE adapter with Bluetooth enabled.
3. Sign and install **ViePNMobile-2.2.0-UNSIGNED.ipa** on the iPhone. Tailscale must already reach your private Windows gateway over HTTPS.
4. On iPhone, go to **Kết nối → Kết nối không dây ViePN → Đăng ký iPhone qua Tailscale**. The app also registers when connected and opened.
5. To discover nearby devices over Bluetooth, enable **Phát Bluetooth ViePN khi ở gần Windows** while ViePN is in the foreground. Approve the iOS Bluetooth permission.
6. On Windows dashboard choose **Thiết bị → iPhone/iPad từ xa → Quét Bluetooth gần Windows**; or tap **Quét BLE từ Windows** on the iPhone. Nearby ViePN BLE instances are correlated to already authenticated registered remote devices.

### What this does

- Remote devices appear separately from Apple USB/Wi-Fi paired devices; each has a random application-specific UUID, device name, and last seen/online state.
- On iPhone **Thư viện IPA → Ký và cài ứng dụng**, the dropdown includes the remotely registered iPhone even when Windows detects no USB device.
- BLE provides nearby discovery via an ephemeral random session UUID readable from a private CoreBluetooth GATT service. No bearer token, password, iOS UDID, 2FA code, or Apple credential is transmitted via BLE.
- Windows only displays BLE observations matching a device first registered over authenticated HTTPS. BLE does not cryptographically authenticate device ownership; an advertising or GATT token might be imitated by a nearby attacker. **It does not authorize sensitive operations.**
- The remote registration is refreshed when the iOS app opens/reconnects, and online indicates activity in the last 3 minutes. No always-on iOS background process is promised.
- BLE advertising works in the foreground only; iOS background restrictions and Windows BLE adapter/driver quality may affect discovery.

### Important limitations

**Bluetooth / Tailscale are not Apple's device pairing, signing or installation mechanism.** A remote iPhone in the picker is not marked Apple-paired, and the direct Apple usbmux install button is disabled for remote-only devices. To install IPA cable-free you need a separate Apple-supported deployment route, such as a properly provisioned OTA installation or MDM enrollment. These are not part of this release.

The feature was tested for payload parsing, API authorization, BLE GATT matching via mocks, iOS compilation, and Windows source packaging. Real Bluetooth discovery on your Windows adapter and iPhone must be verified on the actual hardware.

### Security

- API endpoints require the existing bearer token over your private Tailscale HTTPS gateway. BLE signals never carry this token.
- The registered random iPhone identifier is not an Apple UDID and does not grant Apple USB pairing or installation privileges.
- The API does not expose arbitrary BLE devices or MAC addresses: only pre-registered ViePN devices are reported.
- Windows Bluetooth scanning is optional; no blanket antivirus exceptions, privileged USB workarounds or public port forwarding.
