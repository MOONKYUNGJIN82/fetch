# Fetch 1.6.6 (Windows)

- Behance project pages that return HTTP 403 now retry in the bundled browser engine. No extra browser or Python installation is required.
- Preview and download share the same page-reading path.
- Embedded Adobe, Vimeo and YouTube players are resolved directly instead of requesting the blocked Behance page again.
- Embedded video failures remain visible even when images succeed. Project/player-specific filenames prevent different embedded videos from colliding.
- Browser rendering is isolated from the main UI, time-limited, and uses an off-the-record profile. Existing Behance cookies are domain-filtered and passed in memory, without exporting them to disk. No TLS checks are disabled.

Verification: 65 focused tests; Windows bundled-runtime thumbnail test; the reported Behance project 143132317 saved four images and one video without a login. The complete saved video decoded successfully with FFmpeg.

Limits: this does not promise access to every project, private content, login challenges or blocked networks. Real authenticated Behance sessions were not tested. This release contains the Windows installer only; the previously published Mac 1.6.5 remains available and does not contain this fix. No App Store submission is included.
