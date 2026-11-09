# ViePN iOS Manager 2.2.1 — Official Stable Release

## What's fixed
- The Windows portable installer now reports its **actual manifest version** rather than the outdated fixed string `2.1.2`.
- A single `VERSION` file drives the portable manifest version.
- Free Apple ID signing now preserves nested iOS `.appex` extensions rather than dropping `PlugIns` before signing.
- The signer provisions app and extension bundle identifiers separately; extension bundle identifiers preserve the containing app prefix.
- Extension provisioning profiles are stored separately and inspected against the target bundle identifier and device.
- A new `python -m viepn.keyboard_diagnostics path/to/signed.ipa [UDID]` reports IPA packaging issues.
- Automated regression tests cover the keyboard extension packaging flow.

## Release guarantees
The release workflow must finish tests and build both the Windows ZIP and unsigned iOS IPA. It checks SHA-256 sums, validates the Windows manifest is `2.2.1`, runs the actual portable installer in a clean Windows directory, and compares the packaged signing code/installer with the checked-out release source. Only then can GitHub publish `v2.2.1`. Existing releases are not overwritten.

## Update
On Windows close ViePN while signing/installation jobs are idle, then run `C:\ViePN-iOS-Manager\Update-ViePN.bat`. The updater selects the latest stable GitHub release, checks both SHA-256 files and confirms the portable manifest version equals the release tag. Your user profiles, IPA library, Apple login session and stored data are preserved.

The iPhone IPA `ViePNMobile-2.2.1-UNSIGNED.ipa` still needs valid signing for actual device installation.

**Known limitation:** A valid IPA structure and provisioning metadata do not by themselves prove a valid cryptographic CodeDirectory signature or that iOS registered an extension. Apple Personal Team capabilities and App ID limits still apply. The signing flow needs an actual Windows + iPhone integration test with the user's certificate, device, and supported zsign before declaring keyboard registration fully resolved.
