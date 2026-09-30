import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import update_manager as updates


class UpdateTests(unittest.TestCase):
    def release(self, digest=None):
        return {"tag_name": "v1.5.0", "assets": [{
            "name": "Fetch.Setup.exe",
            "browser_download_url": "https://github.com/MOONKYUNGJIN82/fetch/releases/download/v1.5.0/Fetch.Setup.exe",
            "digest": digest,
        }]}

    def test_old_install_detects_new_version_and_checksum(self):
        with patch.object(updates, "_request_json", return_value=self.release("sha256:" + "a" * 64)):
            found = updates.check_for_update("1.4.7")
        self.assertEqual(found.version, "1.5.0")
        self.assertEqual(found.sha256, "a" * 64)

    def test_missing_checksum_blocks_update(self):
        with patch.object(updates, "_request_json", return_value=self.release()):
            with self.assertRaises(RuntimeError):
                updates.check_for_update("1.4.7")

    def test_current_version_is_not_offered_again(self):
        with patch.object(updates, "_request_json", return_value=self.release()):
            self.assertIsNone(updates.check_for_update("1.5.0"))

    def test_draft_and_prerelease_are_not_offered(self):
        for field in ("draft", "prerelease"):
            data = self.release("sha256:" + "a" * 64)
            data[field] = True
            with patch.object(updates, "_request_json", return_value=data):
                self.assertIsNone(updates.check_for_update("1.4.7"))

    def download(self, digest, content_length=7):
        response = io.BytesIO(b"payload")
        response.headers = {"Content-Length": str(content_length)}
        update = updates.UpdateInfo("1.5.0", "", "Fetch.Setup.exe",
            "https://github.com/MOONKYUNGJIN82/fetch/releases/download/v1.5.0/Fetch.Setup.exe", digest)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(updates.tempfile, "mkdtemp", return_value=directory), patch.object(updates.urllib.request, "urlopen", return_value=response):
                try:
                    result = updates.download_installer(update)
                    return result.read_bytes()
                finally:
                    self.assertFalse(list(Path(directory).glob("*.part")))

    def test_verified_installer_is_saved(self):
        self.assertEqual(self.download(hashlib.sha256(b"payload").hexdigest()), b"payload")

    def test_checksum_mismatch_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.download("b" * 64)

    def test_truncated_installer_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.download(hashlib.sha256(b"payload").hexdigest(), 20)

    def test_foreign_download_url_is_rejected(self):
        update = updates.UpdateInfo("1.5.0", "", "Fetch.Setup.exe", "https://example.com/setup.exe", "a" * 64)
        with self.assertRaises(RuntimeError):
            updates.download_installer(update)
