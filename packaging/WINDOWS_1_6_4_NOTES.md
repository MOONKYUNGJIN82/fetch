# Fetch 1.6.4 Windows validation build

Adds a local diagnostic report preview and explicit copy button.

- Reports app/runtime/dependency versions, FFmpeg/Deno availability, a temporary-file write check and free space.
- Reports only session-file presence, never session contents or credentials.
- Recent activity is classified into fixed error labels and HTTP codes. Raw messages, URLs, usernames, tokens and paths are excluded.
- No server requests, automatic upload, account decryption or live login validation are performed.
- Includes the 1.6.3 account connection changes still awaiting real-account validation.

49 focused tests passed, including report privacy, temporary-file cleanup and bounded error output. Native dialog worker/copy/close smoke test passed.
Not promoted to stable automatic updates pending user account/download validation.
