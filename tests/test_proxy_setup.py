import argparse
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import proxy_setup as app


def reader(port=7897, mode='manual', socks=False):
    def read(schema, key):
        if key == 'mode':
            return mode
        if key == 'use-authentication':
            return False
        if key == 'use-same-proxy':
            return False
        if key == 'ignore-hosts':
            return ['example.local', 'localhost']
        if key == 'host':
            return '127.0.0.1' if (schema.endswith('.socks') == socks) else ''
        if key == 'port':
            return port
        raise AssertionError((schema, key))
    return read


class ProxyTests(unittest.TestCase):
    def test_dynamic_port(self):
        self.assertNotEqual(app.detect_proxy(read=reader(7897)), app.detect_proxy(read=reader(8888)))

    def test_modes_rejected(self):
        for mode in ('auto', 'none'):
            with self.assertRaises(app.SetupError):
                app.detect_proxy(read=reader(mode=mode))

    def test_bad_urls_and_credentials(self):
        for value in ('127.0.0.1:7897', 'http://a:0', 'http://a:65536',
                      'http://user:secret@a:7897', 'http://a:7897/path', 'http://a:7897\n'):
            with self.subTest(value=value), self.assertRaises(app.SetupError):
                app.validate_url(value)

    def test_ipv6(self):
        self.assertEqual(app.endpoint('::1', 7897, 'http'), 'http://[::1]:7897')

    def test_stale_environment_removed_bypass_preserved(self):
        env = app.proxy_environment(app.detect_proxy(read=reader()),
                                    {'ALL_PROXY': 'http://old:1', 'no_proxy': 'internal', 'OTHER': 'yes'})
        self.assertNotIn('ALL_PROXY', env)
        self.assertEqual(env['OTHER'], 'yes')
        self.assertIn('internal', env['NO_PROXY'])
        self.assertIn('example.local', env['NO_PROXY'])

    def test_socks(self):
        env = app.proxy_environment(app.detect_proxy(read=reader(socks=True)), {})
        self.assertEqual(env['HTTPS_PROXY'], 'socks5h://127.0.0.1:7897')

    def test_old_env_exec_removed(self):
        result = app.clean_exec('/usr/bin/env HTTP_PROXY=http://old:1 no_proxy=localhost /bin/echo %U')
        self.assertNotIn('old', result)
        self.assertIn('%U', result)

    def test_shell_rejected(self):
        with self.assertRaises(app.SetupError):
            app.clean_exec('/bin/sh -c "echo unsafe"')

    def test_actions_wrapped(self):
        result = app.render_desktop('[Desktop Entry]\nExec=/bin/echo %U\nDBusActivatable=true\n'
                                    '[Desktop Action New]\nExec=/bin/echo new\n', Path('/tmp/a b.py'), '/usr/bin/python3')
        self.assertEqual(result.count(' launch -- '), 2)
        self.assertIn('DBusActivatable=false', result)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'managed'
        self.apps = self.base / 'applications'
        self.apps.mkdir()
        self.source = self.base / 'chatgpt.desktop'
        self.source.write_text('[Desktop Entry]\nName=Test\nType=Application\nExec=/bin/echo %U\n')
        self.args = argparse.Namespace(proxy=None, desktop=str(self.source), apply=True)
        for target, kwargs in [
            ('locations', {'return_value': (self.root, self.apps)}),
            ('detect_proxy', {'return_value': app.detect_proxy(read=reader())}),
            ('check_ports', {'return_value': None}), ('refresh', {'return_value': None})]:
            mock = patch.object(app, target, **kwargs)
            mock.start()
            self.addCleanup(mock.stop)

    def test_preview_does_not_write(self):
        self.args.apply = False
        app.install(self.args)
        self.assertFalse(self.root.exists())
        self.assertEqual(list(self.apps.iterdir()), [])

    def test_install_idempotent_restore_existing(self):
        target = self.apps / self.source.name
        target.write_text('original user customization')
        app.install(self.args)
        state = (self.root / 'state.json').read_bytes()
        app.install(self.args)
        self.assertEqual(state, (self.root / 'state.json').read_bytes())
        app.restore()
        self.assertEqual(target.read_text(), 'original user customization')
        self.assertFalse(self.root.exists())

    def test_restore_new(self):
        app.install(self.args)
        app.restore()
        self.assertFalse((self.apps / self.source.name).exists())

    def test_user_changes_protected(self):
        app.install(self.args)
        target = self.apps / self.source.name
        target.write_text('changed afterwards')
        with self.assertRaises(app.SetupError):
            app.restore()
        with self.assertRaises(app.SetupError):
            app.install(self.args)
        self.assertEqual(target.read_text(), 'changed afterwards')

    def test_failed_state_write_rolls_back(self):
        target = self.apps / self.source.name
        target.write_text('original')
        original = app.atomic_write

        def fail(path, *args):
            if path.name == 'state.json':
                raise OSError('simulated')
            original(path, *args)
        with patch.object(app, 'atomic_write', side_effect=fail):
            with self.assertRaises(OSError):
                app.install(self.args)
        self.assertEqual(target.read_text(), 'original')
        self.assertFalse((self.root / 'launcher.py').exists())

    def test_launch_uses_new_configuration_and_arguments(self):
        config_path = self.base / 'config.json'
        config_path.write_text(json.dumps({'proxy': None}))
        with patch.object(app, '__file__', str(self.base / 'launcher.py')), \
                patch.object(app.os, 'execvpe') as execute:
            app.launch(['--', '/bin/echo', 'file with spaces'])
        self.assertEqual(execute.call_args.args[1], ['/bin/echo', 'file with spaces'])
        self.assertIn('HTTPS_PROXY', execute.call_args.args[2])


if __name__ == '__main__':
    unittest.main()
