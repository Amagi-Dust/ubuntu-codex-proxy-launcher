#!/usr/bin/env python3
"""GNOME proxy configuration and a relocatable, standard-library-only launcher."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

PROXY_KEYS = {key for name in ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy')
              for key in (name, name.upper())}
BASE_BYPASS = ['localhost', '127.0.0.1', '::1']


class SetupError(Exception):
    pass


def gget(schema, key):
    try:
        result = subprocess.run(['gsettings', 'get', schema, key], capture_output=True,
                                text=True, timeout=4, check=True)
        value = result.stdout.strip()
        if value in ('true', 'false'):
            return value == 'true'
        if value.startswith('@as '):
            value = value[4:]
        return ast.literal_eval(value)
    except (OSError, subprocess.SubprocessError, ValueError, SyntaxError) as exc:
        raise SetupError('无法读取 GNOME 系统代理，请检查桌面会话或使用 --proxy。') from exc


def validate_url(value):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in ('http', 'https', 'socks5', 'socks5h')
                or not parsed.hostname or not parsed.port or parsed.username is not None
                or parsed.password is not None or parsed.path not in ('', '/')
                or parsed.query or parsed.fragment or any(c.isspace() for c in value)
                or any(ord(c) < 32 for c in value)):
            raise ValueError()
        if not re.fullmatch(r'[A-Za-z0-9_.:\-]+', parsed.hostname):
            raise ValueError()
    except ValueError as exc:
        raise SetupError('代理地址无效；需协议、主机和端口，首版不支持认证信息。') from exc
    return value.rstrip('/')


def endpoint(host, port, scheme):
    if not host:
        return None
    host = f'[{host}]' if ':' in host and not host.startswith('[') else host
    return validate_url(f'{scheme}://{host}:{port}')


def detect_proxy(explicit=None, read=gget):
    if explicit:
        value = validate_url(explicit)
        return {'source': 'explicit', 'http': value, 'https': value, 'all': value,
                'bypass': BASE_BYPASS.copy()}
    root = 'org.gnome.system.proxy'
    mode = read(root, 'mode')
    if mode != 'manual':
        raise SetupError('系统代理已关闭。' if mode == 'none' else
                         '首版不支持 PAC/自动代理；请使用手动代理或 --proxy。')
    if read(root + '.http', 'use-authentication'):
        raise SetupError('首版不支持需要认证的代理。')
    values = {}
    for name, scheme in [('http', 'http'), ('https', 'http'), ('socks', 'socks5h')]:
        values[name] = endpoint(read(root + '.' + name, 'host'),
                                read(root + '.' + name, 'port'), scheme)
    if read(root, 'use-same-proxy') and values['http']:
        values['https'] = values['http']
        values['socks'] = None
    if not values['https'] and not values['socks']:
        raise SetupError('系统未配置 HTTPS 或 SOCKS 代理；请补齐配置或显式指定 --proxy。')
    bypass = read(root, 'ignore-hosts')
    if not isinstance(bypass, list) or not all(isinstance(v, str) for v in bypass):
        raise SetupError('系统代理绕过列表格式无效。')
    return {'source': 'gnome', 'http': values['http'], 'https': values['https'],
            'all': values['socks'], 'bypass': list(dict.fromkeys(BASE_BYPASS + bypass))}


def proxy_environment(config, original=None):
    original = dict(os.environ if original is None else original)
    old_bypass = [item.strip() for key in ('NO_PROXY', 'no_proxy')
                  for item in original.get(key, '').split(',') if item.strip()]
    env = {k: v for k, v in original.items() if k not in PROXY_KEYS}
    for name in ('http', 'https', 'all'):
        value = config[name] or (config['all'] if name != 'all' else None)
        if value:
            env[name + '_proxy'] = env[(name + '_proxy').upper()] = value
    bypass = ','.join(dict.fromkeys(config['bypass'] + old_bypass))
    env['NO_PROXY'] = env['no_proxy'] = bypass
    return env


def check_ports(config, attempts=1):
    urls = set(v for k, v in config.items() if k in ('http', 'https', 'all') and v)
    for attempt in range(attempts):
        failed = False
        for url in urls:
            p = urlsplit(url)
            try:
                with socket.create_connection((p.hostname, p.port), timeout=1):
                    pass
            except OSError:
                failed = True
        if not failed:
            return
        if attempt + 1 < attempts:
            time.sleep(1)
    raise SetupError('代理端口不可连接，请先启动代理客户端。未切换为直连。')


def locations():
    home = Path.home()
    data = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
    if not data.is_absolute():
        raise SetupError('XDG_DATA_HOME 必须是绝对路径。')
    return data / 'codex-proxy-setup', data / 'applications'


def discover_desktop(explicit=None):
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file() or path.suffix != '.desktop':
            raise SetupError('指定的 desktop 文件不存在。')
        return path
    _, apps = locations()
    roots = [apps] + [Path(p) / 'applications' for p in
                      os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':')]
    found = {}
    for root in roots:
        for name in ('chatgpt.desktop', 'codex.desktop'):
            path = root / name
            if path.is_file() and name not in found:
                found[name] = path
    if len(found) != 1:
        raise SetupError('未找到唯一应用快捷方式，请用 --desktop 指定。')
    return next(iter(found.values()))


def desktop_token(value):
    # desktop Exec escaping is not shell quoting; percent is a field-code marker.
    value = value.replace('%', '%%')
    for char in ('\\', '"', '`', '$'):
        value = value.replace(char, '\\' + char)
    return '"' + value + '"'


def clean_exec(value):
    # Deliberately restrict parsing to ordinary direct launchers and env prefixes.
    if '\\' in value or '\n' in value or '\r' in value:
        raise SetupError('不支持复杂转义的 Exec，需手动适配。')
    try:
        args = shlex.split(value)
    except ValueError as exc:
        raise SetupError('Exec 格式无效。') from exc
    if args and Path(args[0]).name == 'env':
        args.pop(0)
        while args and '=' in args[0]:
            if args[0].split('=', 1)[0] not in PROXY_KEYS:
                raise SetupError('Exec 含非代理环境设置，首版不自动改写。')
            args.pop(0)
    if not args or args[0].startswith('-') or Path(args[0]).name in ('sh', 'bash', 'flatpak', 'snap', 'env'):
        raise SetupError('不支持此启动方式；首版要求直接启动原生应用。')
    executable = shutil.which(args[0])
    if not executable:
        raise SetupError('找不到快捷方式中的应用可执行文件。')
    args[0] = executable
    encoded = []
    for arg in args:
        if arg in ('%u', '%U', '%f', '%F', '%i', '%c', '%k'):
            encoded.append(arg)
        elif '%' in arg:
            raise SetupError('不支持嵌入参数中的 desktop 字段代码。')
        else:
            encoded.append(desktop_token(arg))
    return ' '.join(encoded)


def render_desktop(source, runner, python):
    output, section, count = [], '', 0
    for line in source.splitlines():
        if line.startswith('['):
            section = line
        if line.startswith('DBusActivatable='):
            line = 'DBusActivatable=false'
        if line.startswith('Exec='):
            if section != '[Desktop Entry]' and not section.startswith('[Desktop Action '):
                raise SetupError('未知 desktop Exec 所在分组。')
            line = 'Exec=' + desktop_token(python) + ' ' + desktop_token(str(runner)) + ' launch -- ' + clean_exec(line[5:])
            count += 1
        output.append(line)
    if not count or '[Desktop Entry]' not in source:
        raise SetupError('快捷方式缺少 Desktop Entry 或 Exec。')
    return '\n'.join(output) + '\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.proxy-')
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def refresh():
    if shutil.which('update-desktop-database'):
        subprocess.run(['update-desktop-database', str(locations()[1])],
                       capture_output=True, timeout=10, check=False)


def load_state(root):
    try:
        return json.loads((root / 'state.json').read_text())
    except (OSError, ValueError) as exc:
        raise SetupError('配置状态缺失或无效。') from exc


def install(args):
    config = detect_proxy(args.proxy)
    root, apps = locations()
    if (root / 'state.json').exists():
        state = load_state(root)
        if args.desktop and Path(args.desktop).name != Path(state['target']).name:
            raise SetupError('已管理其他应用，请先 restore。')
        if args.proxy != state['proxy']:
            raise SetupError('代理模式已改变，请先 restore 再重新安装。')
        for name, expected in state['managed'].items():
            path = Path(name)
            if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != expected:
                raise SetupError('受管理文件已更改或缺失，拒绝覆盖；请检查 status。')
        print('已配置，文件未变化，无需重复安装。')
        return
    source = discover_desktop(args.desktop)
    target = apps / source.name
    runner = root / 'launcher.py'
    settings = root / 'config.json'
    if any(p.is_symlink() for p in (root, apps, target, runner, settings)):
        raise SetupError('配置目标包含符号链接，拒绝覆盖。')
    if root.exists() and any(root.iterdir()):
        raise SetupError('工具目录存在未管理文件，请先检查。')
    python = '/usr/bin/python3'
    if not Path(python).is_file():
        raise SetupError('缺少 /usr/bin/python3。')
    source_text = source.read_text()
    content = render_desktop(source_text, runner, python).encode()
    saved_bypass = []
    for line in source_text.splitlines():
        if line.startswith('Exec='):
            for token in shlex.split(line[5:]):
                if token.split('=', 1)[0] in ('NO_PROXY', 'no_proxy') and '=' in token:
                    saved_bypass.extend(v for v in token.split('=', 1)[1].split(',') if v)
    if not shutil.which('desktop-file-validate'):
        raise SetupError('缺少 desktop-file-validate，请安装 desktop-file-utils。')
    with tempfile.TemporaryDirectory() as temp:
        preview = Path(temp) / 'preview.desktop'
        preview.write_bytes(content)
        result = subprocess.run(['desktop-file-validate', str(preview)], capture_output=True, timeout=5)
        if result.returncode:
            raise SetupError('生成的快捷方式未通过格式验证。')
    print('来源：' + config['source'] + '；快捷方式：' + str(target))
    print('GNOME 模式每次启动重新读取；--proxy 模式固定地址。')
    if not args.apply:
        print('预览完成，未写入。使用 install --apply 应用配置。')
        return
    check_ports(config)
    previous = target.read_bytes() if target.exists() else None
    previous_mode = target.stat().st_mode & 0o777 if previous is not None else 0o644
    payloads = {runner: Path(__file__).read_bytes(), settings: json.dumps(
        {'proxy': args.proxy, 'bypass': saved_bypass}).encode(), target: content}
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    created = []
    try:
        if previous is not None:
            atomic_write(root / 'original.desktop', previous)
        for path, data in payloads.items():
            atomic_write(path, data, 0o644 if path == target else 0o600)
            created.append(path)
        state = {'target': str(target), 'proxy': args.proxy, 'had_original': previous is not None,
                 'backup_hash': digest(previous) if previous is not None else None,
                 'original_mode': previous_mode, 'managed': {str(p): digest(v) for p, v in payloads.items()}}
        atomic_write(root / 'state.json', json.dumps(state, indent=2).encode())
    except Exception:
        for path in reversed(created):
            if path == target and previous is not None:
                atomic_write(path, previous, previous_mode)
            else:
                path.unlink(missing_ok=True)
        (root / 'original.desktop').unlink(missing_ok=True)
        raise
    refresh()
    print('配置完成。请完全退出应用后从原图标启动；不会自动结束当前会话。')


def restore():
    root, apps = locations()
    state = load_state(root)
    target = Path(state['target'])
    allowed = {root / 'launcher.py', root / 'config.json', target}
    if target.parent != apps or target.suffix != '.desktop' or set(map(Path, state['managed'])) != allowed:
        raise SetupError('状态文件中的路径无效，拒绝恢复。')
    for name, expected in state['managed'].items():
        path = Path(name)
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != expected:
            raise SetupError('安装后文件被修改或缺失，拒绝覆盖。原备份仍保留在工具目录。')
    if state['had_original']:
        backup = (root / 'original.desktop').read_bytes()
        if digest(backup) != state['backup_hash']:
            raise SetupError('原始备份已变化，拒绝恢复。')
        atomic_write(target, backup, state['original_mode'])
    else:
        target.unlink()
    for name in ('launcher.py', 'config.json', 'original.desktop', 'state.json'):
        (root / name).unlink(missing_ok=True)
    if not any(root.iterdir()):
        root.rmdir()
    refresh()
    print('已恢复安装前的快捷方式，移除本工具生成的启动配置。')


def launch(command):
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        raise SetupError('缺少应用启动命令。')
    settings = json.loads(Path(__file__).with_name('config.json').read_text())
    config = detect_proxy(settings['proxy'])
    config['bypass'] = list(dict.fromkeys(config['bypass'] + settings.get('bypass', [])))
    check_ports(config, attempts=3)
    os.execvpe(command[0], command, proxy_environment(config))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Ubuntu GNOME 用户级 Codex 代理启动配置')
    sub = parser.add_subparsers(dest='action', required=True)
    detect = sub.add_parser('detect', help='只读检测；--check 仅检查 TCP 连通')
    detect.add_argument('--proxy')
    detect.add_argument('--check', action='store_true')
    install_parser = sub.add_parser('install', help='默认预览；--apply 才写入')
    install_parser.add_argument('--proxy')
    install_parser.add_argument('--desktop')
    install_parser.add_argument('--apply', action='store_true')
    sub.add_parser('status')
    sub.add_parser('restore')
    run = sub.add_parser('launch', help=argparse.SUPPRESS)
    run.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        if args.action == 'detect':
            config = detect_proxy(args.proxy)
            print(json.dumps(config, ensure_ascii=False, indent=2))
            if any(os.environ.get(k) for k in PROXY_KEYS - {'NO_PROXY', 'no_proxy'}):
                print('提示：存在环境代理变量；不会作为自动回退来源，也不显示其潜在凭据。')
            if args.check:
                check_ports(config)
                print('TCP 端口可连接；未验证代理协议或 OpenAI 服务可用性。')
        elif args.action == 'install':
            install(args)
        elif args.action == 'restore':
            restore()
        elif args.action == 'launch':
            launch(args.command)
        else:
            root, _ = locations()
            if not (root / 'state.json').exists():
                print('尚未安装本工具的启动配置。')
            else:
                state = load_state(root)
                for name, expected in state['managed'].items():
                    path = Path(name)
                    ok = path.is_file() and digest(path.read_bytes()) == expected
                    print(('正常：' if ok else '变更或缺失：') + name)
    except (SetupError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        message = str(exc) if isinstance(exc, SetupError) else '操作失败，请检查文件权限、配置状态与依赖。'
        print('错误：' + message, file=sys.stderr)
        if args.action == 'launch' and shutil.which('notify-send'):
            subprocess.run(['notify-send', 'Codex 代理启动失败', message], timeout=5, check=False)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
