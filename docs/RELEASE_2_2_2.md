# ViePN iOS Manager v2.2.2 — Free Apple ID signing with keyboard extensions

This release fixes **apple_install failed: zsign not found** when signing IPAs that contain an iOS keyboard extension.

- **No paid Apple Developer account or purchased certificates are required.** ViePN still obtains a temporary development certificate and the 7-day provisioning profiles using your own authenticated free Apple ID (Personal Team). The signing library is a local code-signing tool, not a paid certificate.
- Windows Portable now bundles the official MIT-licensed zsign v1.1.3 Windows x64 executable. The release workflow downloads a **version-pinned** archive from the upstream GitHub release and verifies SHA-256 `6fb5e12a5b7179cfe7e729aa471b35ccf86474eba33d8203df119bf62bad77f7` before packaging.
- Keyboard Extensions (`.appex`) are preserved, provisioned with their own bundle IDs/profiles, and not silently deleted.
- Installer reports the actual release manifest version. Release checks compare packaged source to the release commit, validate archives/checksums and smoke-test the Windows installer.
- You can run `python -m viepn.keyboard_diagnostics signed.ipa [UDID]` from the backend directory to examine the extension metadata and provisioning profiles.

## Installation
Close any active ViePN signing jobs. Run `C:\ViePN-iOS-Manager\Update-ViePN.bat` to install v2.2.2 from the latest stable GitHub release. Your local Apple ID session, keys, and IPA library are preserved. Re-sign your **original unsigned ViePN AI Keyboard IPA**, not an already re-signed IPA.

## Limitations
There is still a free Apple Personal Team limit on app IDs/capabilities; the keyboard extension consumes an additional app ID. The signer and its profiles must pass **actual on-device installation and iOS keyboard registration** before we can declare the issue fixed on your phone. The unsigned ViePNMobile IPA in this release is not the ViePN AI Keyboard IPA.
