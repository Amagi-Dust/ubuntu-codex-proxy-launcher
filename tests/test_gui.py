import json
from pathlib import Path
import tempfile
import unittest

import gui
from proxy_setup import SetupError


class ConfigTests(unittest.TestCase):
    def test_persistence_and_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            data = gui.load_config(path)
            data['mode'] = 'manual'
            data['proxy_url'] = 'http://127.0.0.1:8888'
            gui.save_config(path, data)
            self.assertEqual(gui.load_config(path), data)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_migrate_and_clear_preserves_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            history = path.with_name('history.json')
            record = {'time': 'now', 'action': '检测代理', 'result': '成功', 'output': 'ok'}
            path.write_text(json.dumps({**gui.DEFAULT, 'history': [record]}))
            gui.migrate_history(path)
            self.assertNotIn('history', json.loads(path.read_text()))
            self.assertEqual(gui.load_history(history), [record])
            original = path.read_bytes()
            gui.migrate_history(path)
            gui.save_history(history, [])
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(gui.load_history(history), [])

    def test_credentials_not_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            data = {**gui.DEFAULT, 'proxy_url': 'http://user:secret@localhost:7897'}
            with self.assertRaises(SetupError):
                gui.save_config(path, data)
            self.assertFalse(path.exists())

    def test_corrupt_json_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            path.write_text('broken')
            with self.assertRaises(ValueError):
                gui.load_config(path)
            self.assertEqual(path.read_text(), 'broken')

    def test_commands_preserve_paths_and_modes(self):
        data = {**gui.DEFAULT, 'mode': 'manual', 'proxy_url': 'http://localhost:8888',
                'desktop_path': '/tmp/path with spaces/app.desktop'}
        args = gui.command_for('应用配置', data)
        self.assertIn('--apply', args)
        self.assertEqual(args[-1], data['desktop_path'])
        self.assertIn('--proxy', args)
        self.assertNotIn('--proxy', gui.command_for('检查状态', data))
        self.assertNotIn('--apply', gui.command_for('预览配置', data))
        data['mode'] = 'system'
        args = gui.command_for('预览配置', data)
        self.assertNotIn('--proxy', args)
        self.assertNotIn('--desktop', args)


if __name__ == '__main__':
    unittest.main()
