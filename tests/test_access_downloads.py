import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import urllib.request
import media_downloader as media
from instagram_downloader_ui import friendly_error


class AccessDownloadTests(unittest.TestCase):
    def response(self, payload=b'image', content_type='image/jpeg', length=5):
        response = io.BytesIO(payload)
        response.headers = {'Content-Type': content_type, 'Content-Length': str(length)}
        return response

    def test_behance_page_uses_selected_cookie_file(self):
        with patch.object(media, 'fetch_text', return_value='') as fetch:
            media.extract_behance_media('https://www.behance.net/gallery/123/a', cookies=Path('session.txt'))
        fetch.assert_called_once_with('https://www.behance.net/gallery/123/a', cookies=Path('session.txt'))

    def test_cookies_are_domain_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cookies.txt'
            path.write_text('# Netscape HTTP Cookie File\n.behance.net\tTRUE\t/\tFALSE\t2147483647\tsession\ttest-only\n')
            with patch.object(media.urllib.request, 'build_opener') as build:
                media.open_media_url('https://www.behance.net/', 20, path)
                handler = next(h for h in build.call_args.args if isinstance(h, urllib.request.HTTPCookieProcessor))
            same_site = urllib.request.Request('https://www.behance.net/')
            other_site = urllib.request.Request('https://example.com/')
            handler.cookiejar.add_cookie_header(same_site)
            handler.cookiejar.add_cookie_header(other_site)
            self.assertEqual(same_site.get_header('Cookie'), 'session=test-only')
            self.assertIsNone(other_site.get_header('Cookie'))

    def test_failed_file_is_not_cached_and_next_file_downloads(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(media, 'open_media_url', side_effect=[self.response(b'ab', length=5), self.response()]):
            folder = Path(directory)
            errors = []
            count = media.download_direct_files(['https://a.behance.net/a.jpg', 'https://a.behance.net/b.jpg'], folder, 'image', errors=errors)
            self.assertEqual(count, 1)
            self.assertEqual(len(errors), 1)
            self.assertFalse((folder / '001_a.jpg').exists())
            self.assertFalse(list(folder.glob('*.part')))
            self.assertEqual((folder / '002_b.jpg').read_bytes(), b'image')

    def test_html_is_not_saved_as_media(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(media, 'open_media_url', return_value=self.response(content_type='text/html')):
            with self.assertRaises(ValueError):
                media.download_direct_files(['https://a.behance.net/a.jpg'], Path(directory), 'image')
            self.assertFalse(list(Path(directory).iterdir()))

    def test_video_only_behance_uses_direct_video_and_cookies(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(media, 'extract_behance_media', return_value=([], ['https://a.behance.net/project_modules/video/a.mp4'])) as extract, patch.object(media, 'download_direct_files', return_value=1) as download, patch.object(media, 'YoutubeDL') as ydl:
            result = media.download_urls(['https://www.behance.net/gallery/123/a'], Path(directory), cookies=Path('session.txt'), include_images=False)
            self.assertEqual(result.videos, 1)
            self.assertFalse(result.errors)
            self.assertEqual(extract.call_args.kwargs['cookies'], Path('session.txt'))
            self.assertEqual(download.call_args.args[5], Path('session.txt'))
            ydl.assert_not_called()

    def test_unrelated_images_and_spoofed_hosts_are_excluded(self):
        page = 'https://behance.net.evil.test/project_modules/a.jpg https://a.behance.net/avatars/b.jpg https://a.behance.net/project_modules/c.jpg'
        with patch.object(media, 'fetch_text', return_value=page):
            images, _ = media.extract_behance_media('https://www.behance.net/gallery/123/a')
        self.assertEqual(images, ['https://a.behance.net/project_modules/c.jpg'])

    def test_access_errors_are_not_all_instagram_login(self):
        self.assertIn('403', friendly_error('HTTP Error 403: Forbidden', 'Behance'))
        self.assertNotIn('Instagram', friendly_error('HTTP Error 403: Forbidden', 'Behance'))
        self.assertIn('요청 제한', friendly_error('login required or rate limit 429', 'Instagram'))
        self.assertIn('세션', friendly_error('login required', 'Instagram', True))
        self.assertEqual(friendly_error('cookie helper crashed', 'Behance'), 'cookie helper crashed')
        self.assertIn('확정할 수 없습니다', friendly_error('Requested content is not available, rate-limit reached or login required', 'Instagram'))
