# ViePN iOS Manager app icon

Icon source: uploaded ViePN shield illustration from the project owner.

- `ViePNMobile/Assets.xcassets/AppIcon.appiconset/Source-Icon.jpg` is a compact, reduced-resolution copy for GitHub CI. It is a *fallback* for builds.
- `ViePNMobile/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png` is the preferred full-quality file (1024x1024 RGB PNG).
- To replace the fallback with the exact high-resolution icon, download the AppIcon ZIP from the ChatGPT session and copy `ViePNMobile/Assets.xcassets/` to `ios/ViePNMobile/Assets.xcassets/`. Commit the PNG to the repository.

The `ios/scripts/prepare-app-icon.sh` script generates the PNG from the compact JPEG only if the high-resolution PNG is absent. The CI build runs it before invoking Xcode. XcodeGen uses `ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon`.

iOS applies system icon corner rounding at display time. No rounded-rectangle mask or transparency is required in the 1024 PNG.
