# Fetch 1.6.3 account connection validation build

- Separate Instagram and Behance account connection windows.
- Login happens on service pages in a non-persistent embedded browser.
- User explicitly saves the session after login; passwords are not stored by Fetch.
- Service-scoped cookies are encrypted with Fernet. Encryption keys use Windows Credential Manager or macOS Keychain with no plaintext fallback.
- Saved sessions survive restart and are used automatically for previews and downloads, in memory only.
- Disconnect removes the local encrypted session and its key. It does not log out external browsers or cancel in-flight jobs.
- Existing Netscape cookies.txt import remains available when embedded login is restricted. The original imported file is not modified or deleted.
- Stored-session status is not proof that a service still accepts the session. Expiry, account restrictions and automated-request blocking may still require user action.

Validation: 45 focused tests; Windows Credential Manager synthetic write/read/delete; native embedded-browser smoke test and encrypted restore.
Real Instagram/Adobe account login and authenticated download require user validation before promoting this build to stable automatic updates.
No Mac installer is included in this Windows build.
