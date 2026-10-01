# Fetch 1.6.4 for Windows

## Changes
- Added separate Instagram and Behance account connection windows.
- Saved sessions are encrypted and reused after restarting Fetch. Passwords are not stored by Fetch.
- Added disconnect and service-scoped cookie import options.
- Added a local diagnostic report with app/runtime versions, bundled downloader tools, storage write checks and recent error categories.
- Diagnostic reports exclude raw logs, URLs, personal paths, cookies and tokens. Nothing is uploaded automatically.

## Update
In Fetch 1.6.2, choose Update Check and approve the update. This installer includes Python; a separate Python installation is not required.

49 focused tests and the standalone Windows runtime checks passed.

## Known limitations
Real-account Instagram/Behance login and authenticated downloads still require user validation. Sites may restrict embedded login or automated downloads even with a valid session. Cookie import remains available. A saved session does not guarantee continued access; expired sessions need reconnecting.

This release supplies the Windows installer only; existing Mac releases are unchanged.
