import http.cookiejar
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock
from urllib.error import HTTPError

import behance_browser as browser
import media_downloader as media

URL = 'https://www.behance.net/gallery/143132317/-X-LAMER'
PLAYER = 'https://www-ccv.adobe.io/v1/player/ccv/example/embed?api_key=behance1'


class BehanceBrowserTests(unittest.TestCase):
    def setUp(self):
        browser._cache.clear()

    def test_only_https_project_urls(self):
        self.assertTrue(browser.valid_project(URL))
        for url in ('http://www.behance.net/gallery/1/a', 'https://behance.net.evil/gallery/1/a',
                    'https://example.com/gallery/1/a', 'https://www.behance.net/login',
                    'https://user@www.behance.net/gallery/1/a'):
            with self.assertRaises(ValueError):
                browser.render_project(url)

    def test_only_403_projects_use_browser(self):
        with patch.object(media, 'open_media_url', side_effect=HTTPError(URL, 403, '', {}, None)), \
                patch.object(browser, 'render_project', return_value='page') as render:
            self.assertEqual(media.fetch_text(URL), 'page')
            render.assert_called_once_with(URL, None)
        for url, status in ((URL, 429), (URL, 404), ('https://example.com/', 403)):
            with patch.object(media, 'open_media_url', side_effect=HTTPError(url, status, '', {}, None)), \
                    patch.object(browser, 'render_project') as render:
                with self.assertRaises(HTTPError):
                    media.fetch_text(url)
                render.assert_not_called()

    def test_cache_and_bounded_process(self):
        with patch.object(browser.subprocess, 'run', return_value=Mock(returncode=0, stdout=json.dumps({'html': 'page'}))) as run:
            self.assertEqual(browser.render_project(URL), 'page')
            self.assertEqual(browser.render_project(URL), 'page')
            run.assert_called_once()
            self.assertEqual(run.call_args.kwargs['timeout'], 55)
            self.assertNotIn(URL, run.call_args.args[0])

    def test_browser_failure_is_not_cached(self):
        with patch.object(browser.subprocess, 'run', return_value=Mock(returncode=3, stderr='private data')):
            with self.assertRaisesRegex(RuntimeError, 'could not load') as error:
                browser.render_project(URL)
            self.assertNotIn('private data', str(error.exception))
            self.assertFalse(browser._cache)
        with patch.object(browser.subprocess, 'run', side_effect=subprocess.TimeoutExpired('helper', 55)):
            with self.assertRaises(subprocess.TimeoutExpired):
                browser.render_project(URL)

    def test_cookies_scoped_and_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cookies.txt'
            path.write_text('# Netscape HTTP Cookie File\n.behance.net\tTRUE\t/\tTRUE\t2147483647\tsession\ttest\n.example.com\tTRUE\t/\tTRUE\t2147483647\tother\tsecret\n')
            records = browser.cookie_records(path)
            self.assertEqual([r['name'] for r in records], ['session'])
            with patch.object(browser.subprocess, 'run', return_value=Mock(returncode=0, stdout=json.dumps({'html': 'private'}))) as run:
                browser.render_project(URL, path)
                browser.render_project(URL, path)
                self.assertEqual(run.call_count, 2)
                self.assertFalse(browser._cache)
                self.assertNotIn('secret', run.call_args.kwargs['input'])

    def test_embedded_player_allowlist(self):
        page = '<iframe src="' + PLAYER + '"></iframe><iframe src="https://www-ccv.adobe.io.evil/embed"></iframe>'
        with patch.object(media, 'fetch_text', return_value=page):
            images, videos = media.extract_behance_media(URL)
        self.assertEqual(videos.embeds, [PLAYER])
        self.assertEqual(images, [])
        self.assertEqual(videos, [])

    def test_embedded_player_download_does_not_refetch_blocked_project(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(media, 'extract_behance_media', return_value=([], media.BehanceVideos(embeds=[PLAYER]))), \
                patch.object(media, 'YoutubeDL') as ydl:
            result = media.download_urls([URL], Path(directory))
            ydl.return_value.__enter__.return_value.extract_info.assert_called_once_with(PLAYER, download=True)
            self.assertEqual(result.videos, 1)
            self.assertFalse(result.errors)

    def test_embedded_failure_is_reported_even_when_images_succeed(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(media, 'extract_behance_media', return_value=(['image'], media.BehanceVideos(embeds=[PLAYER]))), \
                patch.object(media, 'download_direct_files', side_effect=[1, 0]), \
                patch.object(media, 'YoutubeDL') as ydl:
            ydl.return_value.__enter__.return_value.extract_info.side_effect = RuntimeError('video failed')
            result = media.download_urls([URL], Path(directory))
            self.assertEqual(result.images, 1)
            self.assertEqual(len(result.errors), 1)
            self.assertFalse(result.ok)


if __name__ == '__main__':
    unittest.main()
