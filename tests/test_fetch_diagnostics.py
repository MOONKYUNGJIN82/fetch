import tempfile
import unittest
from pathlib import Path
from fetch_diagnostics import build_report, error_categories, folder_check


class DiagnosticsTests(unittest.TestCase):
    def test_report_excludes_sensitive_log_data(self):
        secret = "HTTP Error 403 https://user:password@example.com/private?token=SECRET\nCookie: sessionid=TOPSECRET\nC:\\Users\\PRIVATE\\file.mp4 error\nuser@private.example failed"
        with tempfile.TemporaryDirectory() as directory:
            report = build_report(directory, secret, ['instagram'], True)
            self.assertEqual(list(Path(directory).iterdir()), [])
            for value in ('SECRET', 'TOPSECRET', 'PRIVATE', 'example.com', 'user@', directory, 'password'):
                self.assertNotIn(value, report)
            self.assertIn('HTTP 403', report)
            self.assertIn('쓰기 성공', report)
            self.assertIn('Instagram 세션 파일: 있음', report)

    def test_missing_folder_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'missing'
            self.assertIn('폴더 없음', folder_check(path)[0])
            self.assertFalse(path.exists())

    def test_errors_are_bounded(self):
        self.assertEqual(len(error_categories('HTTP Error 429\n' * 1000)), 15)
        self.assertEqual(error_categories('success'), [])

    def test_unknown_errors_do_not_copy_original(self):
        self.assertEqual(error_categories('failed with private-secret'), ['기타 오류 (원문 제외)'])


if __name__ == '__main__':
    unittest.main()
