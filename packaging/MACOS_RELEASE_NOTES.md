# Fetch 1.6.0 Mac preview

Developer preview for macOS 13 and later. This is not the stable Windows update
and is not an App Store release.

## Packages

- Fetch-macOS-arm64.dmg: Apple Silicon Macs.
- Fetch-macOS-x86_64.dmg: Intel Macs.
- Each DMG has a SHA-256 checksum file and build verification report.

Python and the media tools are bundled. Downloads default to Downloads/Fetch.
The updater selects Mac files for the current CPU architecture. It opens the
verified update DMG; replacing the app in Applications remains a manual step.

## Release gates

Developer ID signing and Apple notarization are not complete. These files must
not be advertised as Gatekeeper-approved installers. Do not disable macOS
security protections to install this preview.

Interactive testing on a user's Mac, including real downloads, folder access
and upgrades, is still required. Automated runner results are included in the
verification reports; they are not a claim that every supported service works.
