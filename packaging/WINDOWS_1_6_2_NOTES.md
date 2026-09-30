# Fetch 1.6.2 - Windows

- Apply the selected cookies.txt session to Behance page, preview and media requests, with domain-scoped cookies.
- Support direct Behance video downloads when image saving is disabled.
- Save direct media atomically, reject empty/truncated/HTML responses, and continue processing later files after a failure.
- Distinguish access denied, request limits, invalid sessions, TLS errors and uncertain Instagram responses.
- Include clipboard/thumbnail threading safeguards, bundled TLS roots and update lifecycle fixes.
- Python is bundled; no separate Python installation is required.

Known limitations: the reported WISE Behance project currently returns HTTP 403 to unauthenticated requests. This update does not bypass access controls or guarantee access after login. Select a valid cookies.txt from your own browser only for content your account can access. Do not share this file publicly. The reported Instagram post has not been provided, so that specific failure remains unverified.

Validation: 37 focused tests and standalone runtime checks. Fresh installation on a separate clean PC has not been performed for this build.
