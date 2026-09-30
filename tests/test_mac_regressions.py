import io
import json
import os
import ssl
import time
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QThread, Slot, Qt, QBuffer, QIODevice
from PySide6.QtGui import QImage, QCloseEvent
from PySide6.QtWidgets import QApplication
import instagram_downloader_ui as ui
import update_manager as updates
from network_support import tls_context

URL = 'https://www.youtube.com/watch?v=lO3lG-qXU14&list=RDlO3lG-qXU14&start_radio=1'


class MacRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def release(self, version='1.6.1', **fields):
        return {'tag_name': f'v{version}-macos-preview.1', 'prerelease': True,
                'assets': [{'name': 'Fetch-macOS-arm64.dmg', 'digest': 'sha256:' + 'a'*64,
                            'browser_download_url': 'https://github.com/MOONKYUNGJIN82/fetch/releases/download/test/Fetch-macOS-arm64.dmg'}], **fields}

    def test_mac_preview_update_and_no_repeat(self):
        with patch.object(updates.sys, 'platform', 'darwin'), patch.object(updates.platform, 'machine', return_value='arm64'), patch.object(updates, '_request_json', return_value=[self.release()]):
            self.assertEqual(updates.check_for_update('1.6.0').version, '1.6.1')
            self.assertIsNone(updates.check_for_update('1.6.1'))

    def test_mac_skips_drafts_and_unrelated_previews(self):
        for data in (self.release(draft=True), self.release(tag_name='v99.0.0-experimental')):
            with patch.object(updates.sys, 'platform', 'darwin'), patch.object(updates, '_request_json', return_value=[data]):
                self.assertIsNone(updates.check_for_update('1.6.0'))

    def test_tls_has_trust_roots_without_build_machine_paths(self):
        with patch.dict(os.environ, {'SSL_CERT_FILE': '/missing-build-cert.pem', 'SSL_CERT_DIR': '/missing-build-certs'}):
            context = tls_context()
        self.assertTrue(context.get_ca_certs())
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_clipboard_queue_preview_and_thread_lifecycle(self):
        image = QImage(128, 72, QImage.Format_RGB32)
        image.fill(Qt.red)
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, 'PNG')
        image_bytes = bytes(buffer.data())

        def response(request, **kwargs):
            url = request if isinstance(request, str) else request.full_url
            self.assertIsNotNone(kwargs.get('context'))
            if 'oembed' in url:
                self.assertNotIn('start_radio', url)
                return io.BytesIO(json.dumps({'title': 'Video preview'}).encode())
            return io.BytesIO(image_bytes)

        with patch.object(ui.MainWindow, 'load_settings'), patch.object(ui.MainWindow, 'save_settings'), patch.object(ui.MainWindow, 'load_history', return_value=[]), patch.object(ui.MainWindow, 'check_updates'), patch.object(ui.urllib.request, 'urlopen', side_effect=response), patch.object(ui, 'YoutubeDL') as extractor:
            window = ui.MainWindow('Arial')
            window.ui_thread_id = threading.get_ident()
            window.callback_threads = []
            find_item = window.find_queue_item
            def observed_find(url):
                window.callback_threads.append((threading.get_ident(), window.ui_thread_id))
                return find_item(url)
            window.find_queue_item = observed_find
            window.clipboard_timer.stop()
            self.app.clipboard().setText(URL)
            window.scan_clipboard()
            window.scan_clipboard()
            self.assertEqual(window.queue_list.count(), 1)
            closing = QCloseEvent()
            window.closeEvent(closing)
            self.assertFalse(closing.isAccepted())
            window.add_urls_to_queue([f'https://youtu.be/{i:011d}' for i in range(15)])
            deadline = time.monotonic() + 30
            while window.thumbnail_thread is not None and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.005)
            self.assertIsNone(window.thumbnail_thread)
            self.assertGreaterEqual(len(window.callback_threads), 32)
            self.assertTrue(all(a == b for a, b in window.callback_threads), window.callback_threads)
            self.assertFalse(window.queue_list.item(0).icon().isNull())
            extractor.assert_not_called()
            window.download_thread = object()
            window.worker = object()
            window.clear_download_worker()
            self.assertIsNone(window.download_thread)
            self.assertEqual(window.thread(), self.app.thread())
            self.assertIsNone(window.worker)
            window.close()

    def test_preview_failure_returns_error_without_raising(self):
        worker = ui.ThumbnailWorker(URL, None)
        results = []
        worker.finished.connect(lambda *args: results.append(args))
        with patch.object(ui.urllib.request, 'urlopen', side_effect=OSError('offline')):
            worker.run()
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][1])

    def test_update_starts_after_worker_finishes_during_confirmation(self):
        with patch.object(ui.MainWindow, 'load_settings'), patch.object(ui.MainWindow, 'save_settings'), patch.object(ui.MainWindow, 'load_history', return_value=[]), patch.object(ui.MainWindow, 'download_update') as download:
            window = ui.MainWindow('Arial')
            window.clipboard_timer.stop()
            window.update_thread = object()
            def confirm(*args):
                window.clear_update_worker()
                return ui.QMessageBox.Yes
            update = updates.UpdateInfo('9.0.0', '', 'Fetch-macOS-arm64.dmg', 'https://github.com/test', 'a'*64)
            with patch.object(ui.QMessageBox, 'question', side_effect=confirm):
                window.update_check_finished(True, update, '')
            download.assert_called_once_with(update)
            window.close()


if __name__ == '__main__':
    unittest.main()
