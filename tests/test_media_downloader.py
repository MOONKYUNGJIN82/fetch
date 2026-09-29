from __future__ import annotations

import unittest
from unittest.mock import patch

from media_downloader import extract_behance_media, normalize_page_text


class MediaDownloaderTests(unittest.TestCase):
    def test_normalize_page_text_unescapes_json_urls(self) -> None:
        source = r"https:\/\/mir-s3-cdn-cf.behance.net\/project_modules\/max_1200\/abc.jpg?x=1\u0026y=2"
        self.assertIn(
            "https://mir-s3-cdn-cf.behance.net/project_modules/max_1200/abc.jpg?x=1&y=2",
            normalize_page_text(source),
        )

    def test_extract_behance_media_dedupes_to_larger_image(self) -> None:
        page = r"""
        <img src="https://mir-s3-cdn-cf.behance.net/project_modules/disp/asset.jpg">
        <img src="https://mir-s3-cdn-cf.behance.net/project_modules/max_2800/asset.jpg">
        <script>var video = "https:\/\/mir-s3-cdn-cf.behance.net\/project_modules\/video\/clip.mp4";</script>
        """
        with patch("media_downloader.fetch_text", return_value=page):
            images, videos = extract_behance_media("https://www.behance.net/gallery/123/name")

        self.assertEqual(images, ["https://mir-s3-cdn-cf.behance.net/project_modules/max_2800/asset.jpg"])
        self.assertEqual(videos, ["https://mir-s3-cdn-cf.behance.net/project_modules/video/clip.mp4"])


if __name__ == "__main__":
    unittest.main()
