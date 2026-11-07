# ViePN iOS Manager 2.1.6 — Fix iPhone device picker

This stable release fixes the **Thư viện IPA → Ký và cài ứng dụng → Chọn thiết bị** list appearing empty even when Windows detects an iPhone.

## Fixed
- iOS recognizes the actual `pymobiledevice3 usbmux list` keys `Identifier`, `UniqueDeviceID`, `DeviceName` and nested `Properties.SerialNumber` as well as older names.
- Windows API normalizes devices to consistent `udid` and `name` fields for both dashboard and the remote iOS application.
- **Quét lại** refresh button, loading state, an explicit device-discovery error, and useful empty-state guidance in the IPA library.
- Failures in `/api/devices` are no longer silently treated as an empty list.
- Regression tests cover USB, Wi-Fi/legacy and nested device formats, plus authenticated API responses.
- Compatible with iOS 16.0+.

## Update Windows and iOS
1. Run `C:\ViePN-iOS-Manager\Update-ViePN.bat` to install the official latest version, and restart `Start-ViePN.bat`. Alternatively install the Windows ZIP using `Install-ViePN.bat`.
2. The matching **unsigned** IPA is saved under `C:\ViePN-iOS-Manager\IPA\ViePNMobile-2.1.6-UNSIGNED.ipa` by the updater. Sign it with a valid provisioning profile and install on your iPhone.
3. In the iOS app open **Thư viện IPA → Ký và cài ứng dụng → Quét lại**.
4. The list shows only devices that **the Windows host** discovers via usbmux. Tailscale VPN connectivity alone does **not** pair an iPhone to the Windows host. If empty, connect your phone via USB, unlock it, choose **Trust This Computer**, and check the Windows command `.venv\Scripts\python.exe -m pymobiledevice3 usbmux list`. For Wi-Fi, enable pairing and discoverability with the Windows Apple Mobile Device Service.

## Safety and caveats
The IPA is unsigned and cannot be installed directly without proper signing. This release does not bypass Apple's pairing, signing or installation requirements. CI confirms build and unit tests; a real Windows+iPhone device connection must be tested locally.
