import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location('repair', Path(__file__).parents[1] / 'repair.py')
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='codex-recovery-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'package' / 'plugins'
        self.mirror = self.root / 'home' / 'plugin-resources' / 'plugins'
        marketplace = self.source / repair.MARKETPLACE
        marketplace.parent.mkdir(parents=True)
        marketplace.write_text(json.dumps({'name': 'openai-bundled', 'plugins': []}))
        asset = self.source / 'openai-bundled' / 'plugins' / 'computer-use' / 'plugin.json'
        asset.parent.mkdir(parents=True)
        asset.write_text(json.dumps({'name': 'computer-use'}))
        (self.source / 'asset.bin').write_bytes(bytes(range(256)))

    def test_missing_and_corrupt_mirror(self):
        self.assertFalse(repair.check_plugins(self.source, self.mirror))
        repair.sync_plugins(self.source, self.mirror)
        self.assertTrue(repair.check_plugins(self.source, self.mirror, deep=True))
        copied = self.mirror / 'asset.bin'
        copied.write_bytes(b'x' * 256)
        self.assertTrue(repair.check_plugins(self.source, self.mirror, deep=False))
        self.assertFalse(repair.check_plugins(self.source, self.mirror, deep=True))
        repair.sync_plugins(self.source, self.mirror)
        self.assertEqual(copied.read_bytes(), bytes(range(256)))

    def test_missing_obsolete_and_idempotence(self):
        repair.sync_plugins(self.source, self.mirror)
        copied = self.mirror / 'asset.bin'
        before = copied.stat().st_mtime_ns
        repair.sync_plugins(self.source, self.mirror)
        self.assertEqual(before, copied.stat().st_mtime_ns)
        copied.unlink()
        self.assertFalse(repair.check_plugins(self.source, self.mirror))
        repair.sync_plugins(self.source, self.mirror)
        (self.mirror / 'obsolete').write_text('obsolete')
        self.assertFalse(repair.check_plugins(self.source, self.mirror))
        repair.sync_plugins(self.source, self.mirror)
        self.assertFalse((self.mirror / 'obsolete').exists())

    def test_invalid_source_does_not_modify_mirror(self):
        repair.sync_plugins(self.source, self.mirror)
        before = (self.mirror / 'asset.bin').read_bytes()
        (self.source / repair.MARKETPLACE).write_text('{invalid')
        with self.assertRaises(json.JSONDecodeError):
            repair.sync_plugins(self.source, self.mirror)
        self.assertEqual(before, (self.mirror / 'asset.bin').read_bytes())

    def test_source_and_mirror_cannot_overlap(self):
        with self.assertRaises(RuntimeError):
            repair.sync_plugins(self.source, self.source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
