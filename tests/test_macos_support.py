import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import update_manager as updates
import media_downloader as media

class MacSupportTests(unittest.TestCase):
    def test_installer_architecture(self):
        self.assertEqual(updates.installer_asset_name('darwin', 'arm64'), 'Fetch-macOS-arm64.dmg')
        self.assertEqual(updates.installer_asset_name('darwin', 'x86_64'), 'Fetch-macOS-x86_64.dmg')
        self.assertEqual(updates.installer_asset_name('win32', 'AMD64'), 'Fetch.Setup.exe')

    def test_mac_does_not_select_windows_installer(self):
        data = {'tag_name': 'v9.0.0', 'assets': [{'name': 'Fetch.Setup.exe'}]}
        with patch.object(updates.sys, 'platform', 'darwin'), patch.object(updates.platform, 'machine', return_value='arm64'), patch.object(updates, '_request_json', return_value=data):
            self.assertIsNone(updates.check_for_update('1.5.0'))

    def test_mac_selects_matching_asset_and_digest(self):
        name = 'Fetch-macOS-arm64.dmg'
        data = {'tag_name': 'v9.0.0', 'assets': [
            {'name': 'Fetch.Setup.exe'},
            {'name': name, 'digest': 'sha256:' + 'a' * 64, 'browser_download_url':
             'https://github.com/MOONKYUNGJIN82/fetch/releases/download/v9.0.0/' + name}]}
        with patch.object(updates.sys, 'platform', 'darwin'), patch.object(updates.platform, 'machine', return_value='arm64'), patch.object(updates, '_request_json', return_value=data):
            result = updates.check_for_update('1.5.0')
        self.assertEqual(result.asset_name, name)
        self.assertEqual(result.sha256, 'a' * 64)

    def test_frozen_deno_location(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / 'runtime'
            runtime.mkdir()
            (runtime / 'deno').touch()
            with patch.object(sys, '_MEIPASS', directory, create=True), patch.object(sys, 'platform', 'darwin'):
                self.assertEqual(media.bundled_js_runtimes()['deno']['path'], str(runtime / 'deno'))

    def test_mac_defaults_use_user_folders(self):
        from instagram_downloader_ui import app_data_dir, default_download_dir
        with tempfile.TemporaryDirectory() as directory, patch.object(Path, 'home', return_value=Path(directory)), patch.object(sys, 'platform', 'darwin'):
            self.assertEqual(default_download_dir(), Path(directory) / 'Downloads/Fetch')
            self.assertEqual(app_data_dir(), Path(directory) / 'Library/Application Support/Fetch')
