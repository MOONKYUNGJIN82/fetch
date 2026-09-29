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

Ordinary pushes to `macos-preview` produce unsigned developer previews. To build
Gatekeeper-ready DMGs, create the GitHub Actions environment
`fetch-macos-signing` and put the following **environment secrets** in it:

- `MACOS_CERTIFICATE_P12_BASE64`: base64 of the KALLOS Developer ID Application
  `.p12`, including its private key.
- `MACOS_CERTIFICATE_PASSWORD`: password protecting that `.p12`.
- `APPLE_API_KEY_P8_BASE64`: base64 of the App Store Connect API `.p8` key.
- `APPLE_API_KEY_ID` and `APPLE_API_ISSUER`: the API key ID and issuer ID.

Restrict the signing environment to the `macos-preview` branch and require
review before allowing the job to read the secrets. Never commit any of these
values. Run **Fetch macOS preview** manually with `signed=true`. Both
architectures build, sign with KALLOS Developer ID, notarize the app and DMG,
staple the tickets, and upload the resulting DMGs as workflow artifacts. The
build fails rather than uploading a falsely labeled signed DMG if any signing
or notarization step fails. Review the artifacts and test real downloads and
updates on both CPU types before publishing a stable release.

The same corporate Developer ID certificate can sign multiple KALLOS Mac apps;
it is not tied to KALLOS Flow's bundle ID. The Mac App Store distribution
certificate and provisioning profile are not used for this GitHub DMG release.

Mac App Store submission is separate: this build does not enable App Sandbox
and is not an App Store submission package. Store entitlements, permissions and
review requirements need a separate implementation and validation pass.
