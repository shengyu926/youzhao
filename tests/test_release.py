import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release', ROOT / 'scripts/build_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_complete_runtime_root_and_no_private_or_developer_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as tmp:
            p = release.build(ROOT, Path(tmp))
            with zipfile.ZipFile(p) as z:
                names = z.namelist()
                self.assertIn('SKILL.md', names)
                self.assertIn('LICENSE', names)
                self.assertIn('scripts/memory_store.py', names)
                self.assertEqual(55, sum(n.startswith('references/') and n.endswith('.md') for n in names))
                self.assertFalse(any(n.startswith(('tests/', 'tmp/', '.git/', 'evidence/')) for n in names))
                self.assertFalse(any(n.endswith(('.sqlite3', '.db', '.pyc')) for n in names))
                self.assertNotIn('scripts/build_release.py', names)
                self.assertEqual('youzhao', json.loads(z.read('version.json'))['name'])
                self.assertIsNone(z.testzip())

    def test_rebuild_refuses_to_overwrite_existing_release(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as tmp:
            release.build(ROOT, Path(tmp))
            with self.assertRaises(FileExistsError):
                release.build(ROOT, Path(tmp))

    def test_bad_source_is_rejected_without_partial_release(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as tmp:
            with self.assertRaises((FileNotFoundError, ValueError)):
                release.build(Path(tmp) / 'absent', Path(tmp) / 'out')
            self.assertFalse((Path(tmp) / 'out').exists())

    def test_flat_and_folder_archives_have_identical_skill_content(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as tmp:
            flat = release.build(ROOT, Path(tmp))
            folder = release.build(ROOT, Path(tmp), layout='folder')
            with zipfile.ZipFile(flat) as a, zipfile.ZipFile(folder) as b:
                self.assertIn('youzhao/SKILL.md', b.namelist())
                self.assertNotIn('SKILL.md', b.namelist())
                self.assertEqual(set(a.namelist()), {n.removeprefix('youzhao/') for n in b.namelist()})
                for name in a.namelist():
                    self.assertEqual(a.read(name), b.read('youzhao/' + name))

    def test_unknown_layout_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as tmp:
            with self.assertRaises(ValueError):
                release.build(ROOT, Path(tmp), layout='unknown')


if __name__ == '__main__':
    unittest.main()
