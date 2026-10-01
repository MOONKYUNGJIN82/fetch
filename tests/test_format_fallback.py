import unittest
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError
from media_downloader import COMPAT_VIDEO_FORMAT
from fetch_diagnostics import error_categories


class FormatFallbackTests(unittest.TestCase):
    def select(self, formats):
        with YoutubeDL({'format': COMPAT_VIDEO_FORMAT, 'quiet': True, 'no_warnings': True}) as ydl:
            return ydl.process_ie_result({'id': 'test', 'title': 'test', 'extractor': 'test', 'formats': formats}, download=False)

    def fmt(self, name, video, audio, ext='mp4', height=720):
        return {'format_id': name, 'url': 'https://example.invalid/' + name,
                'vcodec': video, 'acodec': audio, 'ext': ext, 'height': height}

    def test_mp4_single_file_remains_first_choice(self):
        result = self.select([self.fmt('single', 'avc1', 'mp4a'),
                              self.fmt('video', 'avc1', 'none', height=1080),
                              self.fmt('audio', 'none', 'mp4a', ext='m4a', height=None)])
        self.assertEqual(result['format_id'], 'single')

    def test_split_streams_fall_back_to_merge(self):
        result = self.select([self.fmt('video', 'avc1', 'none'),
                              self.fmt('audio', 'none', 'mp4a', ext='m4a', height=None)])
        self.assertEqual([f['format_id'] for f in result['requested_formats']], ['video', 'audio'])

    def test_other_single_format_still_works(self):
        result = self.select([self.fmt('webm', 'vp9', 'opus', ext='webm')])
        self.assertEqual(result['format_id'], 'webm')

    def test_audio_only_is_not_reported_as_video_success(self):
        with self.assertRaises((DownloadError, ExtractorError)):
            self.select([self.fmt('audio', 'none', 'mp4a', ext='m4a', height=None)])

    def test_format_failure_has_diagnostic_category(self):
        self.assertEqual(error_categories('ERROR: Requested format is not available'), ['미디어 추출'])


if __name__ == '__main__':
    unittest.main()
