import ast
import os
import re
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox
import localization as l


class LocalizationTests(unittest.TestCase):
    def tearDown(self):
        l.set_language('ko')

    def test_all_wrapped_literals_have_english(self):
        l.set_language('en')
        root = Path(__file__).resolve().parents[1]
        misses = []
        for name in ('instagram_downloader_ui.py', 'account_dialog.py'):
            for node in ast.walk(ast.parse((root / name).read_text(encoding='utf-8'))):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'tr'):
                    continue
                argument = node.args[0]
                text = (argument.value if isinstance(argument, ast.Constant) else
                        ''.join(v.value if isinstance(v, ast.Constant) else 'VALUE' for v in argument.values)
                        if isinstance(argument, ast.JoinedStr) else '')
                if re.search('[가-힣]', l.tr(text)):
                    misses.append(text)
        self.assertEqual(misses, [])

    def test_templates_preserve_values(self):
        l.set_language('en')
        self.assertEqual(l.tr('저장 위치: /my/path'), 'Destination: /my/path')
        self.assertEqual(l.tr('1/2개 다운로드 완료, 1개 실패\n\n'), '1/2 downloads completed, 1 failed\n\n')
        l.set_language('ko')
        self.assertEqual(l.tr('다운로드'), '다운로드')

    def test_ui_language_choice_is_saved(self):
        import instagram_downloader_ui as ui
        app = QApplication.instance() or QApplication([])
        l.set_language('en')
        with patch.object(ui.MainWindow, 'load_settings'), patch.object(ui.MainWindow, 'save_settings'), patch.object(ui.MainWindow, 'load_history', return_value=[]), patch.object(ui.MainWindow, 'check_updates'), patch.object(ui, 'QSettings') as settings, patch.object(QMessageBox, 'information'):
            window = ui.MainWindow('Arial')
            window.clipboard_timer.stop()
            self.assertEqual(window.download_button.text(), 'Download')
            self.assertEqual(window.language_combo.currentData(), 'en')
            window.language_combo.setCurrentIndex(0)
            settings.return_value.setValue.assert_any_call('language', 'ko')
            window.close()
            window.deleteLater()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
