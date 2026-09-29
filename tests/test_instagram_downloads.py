import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from media_downloader import download_instagram, is_instagram_url
from instagram_downloader_ui import friendly_error

class InstagramTests(unittest.TestCase):
    def run_download(self, entries, images=True, videos=True):
        ydl = Mock()
        with tempfile.TemporaryDirectory() as directory:
            with patch("media_downloader.extract_instagram_info", return_value={"_type": "playlist", "entries": entries}):
                result = download_instagram(ydl, "https://instagram.com/p/test/", Path(directory), videos, images, lambda _: None)
        return result, ydl

    def test_photo_uses_largest_candidate_when_sizes_are_missing(self):
        ydl = Mock()
        response = io.BytesIO(b"image-bytes")
        response.headers = {"Content-Type": "image/jpeg"}
        ydl.urlopen.return_value = response
        entry = {"fetch_media_type": 1, "id": "photo", "thumbnails": [
            {"url": "https://example.com/small.jpg"},
            {"url": "https://example.com/large.jpg"}]}
        with tempfile.TemporaryDirectory() as directory:
            with patch("media_downloader.extract_instagram_info", return_value=entry):
                result = download_instagram(ydl, "https://instagram.com/p/test/", Path(directory), True, True, lambda _: None)
            self.assertEqual(result.images, 1)
            self.assertEqual(next(Path(directory).glob("*.jpg")).read_bytes(), b"image-bytes")
        self.assertEqual(ydl.urlopen.call_args.args[0].url, "https://example.com/large.jpg")
        ydl.process_ie_result.assert_not_called()

    def test_photo_disabled_does_not_abort_next_video(self):
        result, ydl = self.run_download([{"fetch_media_type": 1}, {"formats": [{"url": "https://example.com/v.mp4"}]}], images=False)
        self.assertEqual((result.skipped, result.videos, result.errors), (1, 1, []))
        ydl.process_ie_result.assert_called_once()

    def test_missing_video_is_not_downloaded_as_thumbnail(self):
        result, ydl = self.run_download([{"fetch_media_type": 2, "thumbnails": [{"url": "https://example.com/t.jpg"}]}])
        self.assertEqual(result.images, 0)
        self.assertEqual(len(result.errors), 1)
        ydl.urlopen.assert_not_called()

    def test_failed_item_does_not_abort_next_video(self):
        result, ydl = self.run_download([{"fetch_media_type": 2}, {"formats": [{"url": "https://example.com/v.mp4"}]}])
        self.assertEqual((result.videos, len(result.errors)), (1, 1))

    def test_no_formats_does_not_claim_empty_response(self):
        self.assertNotIn("cookies.txt", friendly_error("No video formats found"))

    def test_host_validation(self):
        self.assertTrue(is_instagram_url("https://www.instagram.com/p/test"))
        self.assertFalse(is_instagram_url("https://instagram.com.example.com/p/test"))
