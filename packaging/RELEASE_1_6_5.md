# Fetch 1.6.5

- Compatibility mode prefers a combined MP4 file, then another combined video/audio file. When none is available, it automatically selects video and audio streams for merging using bundled FFmpeg.
- Korean and English interface options are available in the header. The selected language is remembered and applies on the next launch. Website pages and third-party technical logs keep their original language.
- Format-unavailable failures have a specific diagnostic category instead of a generic error.
- Includes encrypted Instagram/Behance sessions and private local diagnostics from 1.6.4. Actual service login and downloads remain subject to session expiry and service restrictions.

Windows: approve the in-app update or run Fetch.Setup.exe. No separate Python installation is required.

macOS: choose the DMG for Apple Silicon (arm64) or Intel (x86_64). Move Fetch to Applications. The Mac updater opens the matching DMG; replacement is manual. Mac files are published only after signing, Apple notarization and native execution checks pass. This is direct distribution, not an App Store release.
