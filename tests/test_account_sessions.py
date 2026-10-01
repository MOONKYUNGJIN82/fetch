import http.cookiejar
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from account_sessions import SessionStore, service_for_url, cookies_for_url, apply_session


class Backend:
    def __init__(self):
        self.data = {}

    def get_password(self, service, name):
        return self.data.get((service, name))

    def set_password(self, service, name, value):
        self.data[service, name] = value

    def delete_password(self, service, name):
        self.data.pop((service, name), None)


def cookie(domain=".instagram.com", expires=None):
    return http.cookiejar.Cookie(0, "sessionid", "fake-secret-for-tests", None, False,
                                 domain, True, True, "/", True, True, expires,
                                 expires is None, None, None, {})


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.backend = Backend()
        self.store = SessionStore(self.temp.name, self.backend)

    def test_roundtrip_is_encrypted_and_scoped(self):
        self.store.save("instagram", [cookie(), cookie(".behance.net"), cookie(".evilinstagram.com")])
        raw = self.store.path("instagram").read_bytes()
        self.assertNotIn(b"fake-secret", raw)
        self.assertNotIn(b"instagram", raw)
        jar = self.store.load("instagram")
        self.assertEqual(len(jar), 1)
        self.assertEqual(next(iter(jar)).value, "fake-secret-for-tests")
        self.assertIsNone(jar.filename)

    def test_remove_deletes_key_and_file(self):
        self.store.save("instagram", [cookie()])
        self.store.remove("instagram")
        self.assertFalse(self.store.path("instagram").exists())
        self.assertFalse(self.backend.data)

    def test_expired_rejected(self):
        with self.assertRaises(ValueError):
            self.store.save("instagram", [cookie(expires=int(time.time()) - 1)])
        self.assertFalse(self.store.path("instagram").exists())

    def test_tampering_fails_closed(self):
        self.store.save("instagram", [cookie()])
        self.store.path("instagram").write_bytes(b"corrupted")
        with self.assertRaises(Exception):
            self.store.load("instagram")

    def test_url_scope(self):
        self.assertEqual(service_for_url("https://www.instagram.com/p/test"), "instagram")
        self.assertIsNone(service_for_url("https://instagram.com.evil.org"))
        self.assertIsNone(service_for_url("https://youtube.com/watch?v=test"))
        self.assertEqual(cookies_for_url("https://instagram.com", Path("manual.txt")), Path("manual.txt"))

    def test_lookup_uses_own_service(self):
        self.store.save("instagram", [cookie()])
        with patch("account_sessions.SessionStore", return_value=self.store):
            self.assertEqual(len(cookies_for_url("https://instagram.com/p/test")), 1)
            self.assertIsNone(cookies_for_url("https://behance.net/gallery/test"))

    def test_ydl_keeps_cookies_in_memory(self):
        from yt_dlp import YoutubeDL
        self.store.save("instagram", [cookie()])
        jar = self.store.load("instagram")
        with YoutubeDL({"quiet": True}) as ydl:
            apply_session(ydl, jar)
            self.assertIs(ydl.cookiejar, jar)
            self.assertIn("sessionid=", ydl.cookiejar.get_cookie_header("https://www.instagram.com/"))
            self.assertIsNone(ydl.cookiejar.get_cookie_header("https://behance.net/"))

    def test_import_filters_and_leaves_source_unchanged(self):
        source = Path(self.temp.name) / "source.txt"
        jar = http.cookiejar.MozillaCookieJar(str(source))
        jar.set_cookie(cookie())
        jar.set_cookie(cookie(".behance.net"))
        jar.save(ignore_discard=True)
        original = source.read_bytes()
        self.store.import_file("instagram", source)
        self.assertEqual(len(self.store.load("instagram")), 1)
        self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
