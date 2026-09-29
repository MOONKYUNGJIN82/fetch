# Fetch macOS preview

Status: build configuration prepared; native builds and distribution approval
must be verified before calling this a supported release.

## Targets

- macOS 13 or later.
- Separate Apple Silicon (arm64) and Intel (x86_64) DMGs.
- Python, Qt, ffmpeg and Deno are bundled. No user Python installation required.
- Downloads default to ~/Downloads/Fetch.
- History is stored under ~/Library/Application Support/Fetch.

## Build and verification

Run packaging/build_fetch_macos.py on the matching Mac architecture after
installing requirements-fetch.txt and PyInstaller 6.22.3. The
fetch-macos.yml workflow runs these builds on the macos-preview branch.

The build checks bundled runtime dependencies, renders a UI screenshot, verifies
the app signature, and tests a relocated copy without build Python on PATH.
Artifacts include a DMG, SHA-256 checksum, verification JSON and screenshot.
These checks do not replace interactive testing of downloads, folder access,
network failures and upgrades on a physical Mac.

## Updates

The updater selects only the exact architecture's DMG from the latest stable
GitHub release and verifies its checksum. It opens the DMG and quits Fetch;
the user then replaces Fetch in Applications. Automatic app replacement and
relaunch are not implemented. A Windows-only release cannot be installed on Mac.

Do not change the latest stable release to this preview until both architectures
have passed testing and distribution signing is complete.

## Signing and distribution

Without MAC_SIGN_IDENTITY the build is a developer preview, not a public
Gatekeeper-approved installer. Ad-hoc signature verification is not Apple
notarization. Production distribution needs a Developer ID Application signing
identity and Apple notarization, followed by stapling and Gatekeeper assessment.
Provide certificates and notarization credentials through secure CI secrets,
never through source files or chat. Notarization is not yet automated here.

Mac App Store submission is separate: this build does not enable App Sandbox
and is not an App Store submission package. Store entitlements, permissions and
review requirements need a separate implementation and validation pass.
