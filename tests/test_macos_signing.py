import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'packaging/build_fetch_macos.py'
spec = importlib.util.spec_from_file_location('build_fetch_macos', SCRIPT)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class NotarizationTests(unittest.TestCase):
    def credentials(self):
        return patch.dict(os.environ, {
            'APPLE_API_KEY': '/tmp/AuthKey_TEST.p8',
            'APPLE_API_KEY_ID': 'TEST',
            'APPLE_API_ISSUER': 'TEST-ISSUER',
        })

    def test_accepted_dmg_is_stapled_and_validated(self):
        with self.credentials(), patch.object(builder.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps({'status': 'Accepted'}), '')) as submit, patch.object(builder, 'run') as command:
            builder.notarize(Path('/tmp/Fetch.dmg'))
        self.assertIn('--wait', submit.call_args.args[0])
        self.assertEqual(command.call_count, 2)
        self.assertEqual(command.call_args_list[0].args[:3], ('xcrun', 'stapler', 'staple'))

    def test_rejected_submission_cannot_be_stapled(self):
        with self.credentials(), patch.object(builder.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps({'status': 'Invalid'}), '')), patch.object(builder, 'run') as command:
            with self.assertRaisesRegex(RuntimeError, 'notarization failed'):
                builder.notarize(Path('/tmp/Fetch.dmg'))
        command.assert_not_called()

    def test_missing_credentials_fail_before_submission(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(builder.subprocess, 'run') as submit:
            with self.assertRaisesRegex(RuntimeError, 'requires Apple notarization credentials'):
                builder.notarize(Path('/tmp/Fetch.dmg'))
        submit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
