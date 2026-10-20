import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / 'tmp')
        self.work = Path(self.tmp.name)
        self.env = dict(os.environ, YOUZHAO_MEMORY_DIR=str(self.work / 'new'),
                        GOUTOUJUNSHI_MEMORY_DIR=str(self.work / 'old'),
                        LOCALAPPDATA=str(self.work / 'system'), XDG_DATA_HOME=str(self.work / 'system'),
                        TEMP=str(self.work), TMP=str(self.work), PYTHONUTF8='1')

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, *args, ok=True):
        p = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/memory_store.py'), *args],
                           env=self.env, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(0 if ok else 1, p.returncode, p.stdout + p.stderr)
        return json.loads(p.stdout)

    def write(self, value='测试A', source='user_explicit', scope='object', ok=True):
        delta = dict(scope=scope, subject_id='test-a', field='display_label', value=value,
                     source_type=source, source_ref='synthetic:test', confidence='high')
        return self.call('apply', '--json', json.dumps(delta, ensure_ascii=False), ok=ok)

    def test_status_uses_new_namespace_without_creating_database(self):
        data = self.call('status')
        self.assertEqual(str((self.work / 'new/memory.sqlite3').resolve()), data['path'])
        self.assertFalse(data['exists'])
        self.assertFalse((self.work / 'new').exists())

    def test_consent_required_before_creation_or_write(self):
        self.call('enable', ok=False)
        self.write(ok=False)
        self.assertFalse((self.work / 'new').exists())

    def test_correction_undo_pause_and_delete(self):
        self.call('enable', '--confirm')
        self.write()
        self.write('测试A更正')
        self.assertEqual('测试A更正', self.call('show')['memories'][0]['value'])
        self.call('undo')
        self.assertEqual('测试A', self.call('show')['memories'][0]['value'])
        self.call('pause')
        self.write('不能写入', ok=False)
        self.call('resume')
        self.assertEqual(1, self.call('context', '--subject-id', 'test-a')['count'])
        self.call('revoke', '--delete', '--confirm')
        self.assertFalse((self.work / 'new/memory.sqlite3').exists())

    def test_assistant_inference_cannot_be_saved_as_object_fact(self):
        self.call('enable', '--confirm')
        self.write(source='assistant_inference', ok=False)
        self.assertEqual(0, self.call('show')['count'])

    def test_legacy_environment_and_files_are_not_changed(self):
        old = self.work / 'old'
        old.mkdir()
        sentinel = old / 'memory.sqlite3'
        sentinel.write_bytes(b'legacy sentinel: do not overwrite')
        self.call('enable', '--confirm')
        self.write()
        self.assertEqual(b'legacy sentinel: do not overwrite', sentinel.read_bytes())
        self.assertTrue((self.work / 'new/memory.sqlite3').exists())


if __name__ == '__main__':
    unittest.main()
