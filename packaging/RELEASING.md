# Fetch release checklist

An installer build alone is not a published update. Unless the user explicitly requests a local-only or preview build, an update delivery must include GitHub publication and compatibility verification.

1. Run focused tests and standalone runtime checks. Document unverified behavior honestly.
2. Bump the app and launcher versions. Build the standalone installer and SHA256 file.
3. Commit the matching Fetch source and push to MOONKYUNGJIN82/fetch. Use the full commit SHA as release target.
4. Create a draft release with Fetch.Setup.exe and its SHA256 file. Never replace an existing published version's assets.
5. Compare the GitHub asset digest with the locally built installer SHA256 before publishing.
6. Publish the Windows release as Latest, not Draft or Prerelease, so existing Windows versions can discover it.
7. Verify check_for_update using the previous supported app version, then download and verify the installer through the updater. Do not silently install it on the user's PC.
8. Report the public release link, versions verified and remaining test limitations.

Mac-only previews must not become Latest in a way that hides the Windows installer from old Windows updaters. Signed Mac builds and actual installation tests must be reported separately, not inferred from Windows checks.
