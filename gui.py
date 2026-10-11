"""Tk UI: background CLI operations, persistent preferences and operation history."""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from proxy_setup import SetupError, atomic_write, validate_url

DEFAULT = {'schema_version': 1, 'mode': 'system', 'proxy_url': '',
           'desktop_path': ''}


def config_path():
    base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    if not base.is_absolute():
        raise SetupError('XDG_CONFIG_HOME 必须为绝对路径。')
    return base / 'codex-proxy-setup' / 'config.json'


def validate_config(data):
    if (not isinstance(data, dict) or data.get('schema_version') != 1
            or data.get('mode') not in ('system', 'manual')
            or not isinstance(data.get('proxy_url'), str)
            or not isinstance(data.get('desktop_path'), str)):
        raise SetupError('JSON 配置格式无效，请先检查或备份配置文件。')
    if data['proxy_url']:
        validate_url(data['proxy_url'])
    return {key: data[key] for key in DEFAULT}


def validate_history(records):
    if not isinstance(records, list):
        raise SetupError('JSON 操作记录格式无效。')
    for item in records:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str)
                                               for k in ('time', 'action', 'result', 'output')):
            raise SetupError('JSON 操作记录格式无效。')
    return records


def load_history(path):
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise SetupError('JSON 历史文件格式无效。')
    return validate_history(data.get('history'))


def save_history(path, records):
    validate_history(records)
    if path.is_symlink():
        raise SetupError('历史文件是符号链接，拒绝覆盖。')
    data = {'schema_version': 1, 'history': records[-100:]}
    atomic_write(path, (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())


def migrate_history(path):
    if not path.exists():
        return
    old = json.loads(path.read_text())
    config = validate_config(old)
    if 'history' not in old:
        return
    records = validate_history(old['history'])
    target = path.with_name('history.json')
    combined = list(load_history(target))
    for record in records:
        if record not in combined:
            combined.append(record)
    combined.sort(key=lambda item: item['time'])
    # Persist history first; a retry after an interrupted migration deduplicates it.
    save_history(target, combined)
    save_config(path, config)


def load_config(path):
    if not path.exists():
        return dict(DEFAULT)
    return validate_config(json.loads(path.read_text()))


def save_config(path, data):
    data = validate_config(data)
    if path.is_symlink():
        raise SetupError('配置文件是符号链接，拒绝覆盖。')
    atomic_write(path, (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())


def command_for(action, config):
    args = [sys.executable, str(Path(__file__).with_name('proxy_setup.py'))]
    args += {'启用系统代理': ['enable-proxy'], '检测代理': ['detect', '--check'], '预览配置': ['install'],
             '应用配置': ['install', '--apply'], '检查状态': ['status'],
             '恢复原配置': ['restore']}[action]
    if action in ('检测代理', '预览配置', '应用配置'):
        if config['mode'] == 'manual':
            args += ['--proxy', validate_url(config['proxy_url'])]
        if action != '检测代理' and config['mode'] == 'manual' and config['desktop_path']:
            args += ['--desktop', config['desktop_path']]
    return args


class App:
    def __init__(self, root, path=None):
        self.root = root
        self.path = path or config_path()
        migrate_history(self.path)
        self.data = load_config(self.path)
        self.history_path = self.path.with_name('history.json')
        self.history = load_history(self.history_path)
        self.proc = None
        self.output_file = None
        self.root.title('Codex 代理配置')
        self.root.geometry('900x720')
        self.root.minsize(760, 560)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Codex 代理配置', font=('', 20, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='启用系统代理 → 检测 → 预览 → 应用。应用后完全退出 Codex，再从原图标启动。').pack(anchor='w', pady=(5, 16))
        self.mode = tk.StringVar(value=self.data['mode'])
        self.proxy = tk.StringVar(value=self.data['proxy_url'])
        self.desktop = tk.StringVar(value=self.data['desktop_path'])
        form = ttk.LabelFrame(frame, text='启动配置', padding=12)
        form.pack(fill='x')
        self.widgets = []
        for column, (text, value) in enumerate([('跟随 GNOME 系统代理', 'system'), ('手动固定地址', 'manual')]):
            radio = ttk.Radiobutton(form, text=text, variable=self.mode, value=value, command=self.sync_mode)
            radio.grid(row=0, column=column, sticky='w', pady=5)
            self.widgets.append(radio)
        self.system_steps = ttk.Label(form, text=(
            '1. 先启动 Clash/Mihomo，再点击“启用系统代理”。\n'
            '2. 点击“检测代理”，再点击“预览配置”，在下方查看结果。\n'
            '3. 点击“应用配置”，然后“检查状态”。\n'
            '4. 完全退出 Codex，再从原图标启动。\n'
            '按钮开启失败时：Ubuntu 设置 → 网络 → 网络代理 → 打开开关 → 选择 Manual，\n'
            '填写代理客户端的 HTTP/HTTPS 地址和端口，然后从第 2 步继续。'),
            justify='left', wraplength=690)
        self.system_steps.grid(row=1, column=0, columnspan=3, sticky='ew', pady=8)
        self.manual_fields = ttk.Frame(form)
        self.manual_fields.grid(row=2, column=0, columnspan=3, sticky='ew')
        self.manual_fields.columnconfigure(1, weight=1)
        ttk.Label(self.manual_fields, text='代理地址').grid(row=1, column=0, sticky='w')
        self.proxy_entry = ttk.Entry(self.manual_fields, textvariable=self.proxy, width=52)
        self.proxy_entry.grid(row=1, column=1, sticky='ew', pady=6)
        ttk.Label(self.manual_fields, text='例如 http://127.0.0.1:7897；不支持认证代理').grid(row=2, column=1, sticky='w')
        ttk.Label(self.manual_fields, text='应用快捷方式').grid(row=3, column=0, sticky='w')
        entry = ttk.Entry(self.manual_fields, textvariable=self.desktop)
        entry.grid(row=3, column=1, sticky='ew', pady=8)
        self.widgets.append(entry)
        browse = ttk.Button(self.manual_fields, text='选择…', command=self.browse)
        browse.grid(row=3, column=2, padx=8)
        self.widgets.append(browse)
        ttk.Label(self.manual_fields, text='快捷方式留空自动检测；手动代理地址固定，不跟随系统变化。').grid(row=4, column=0, columnspan=3, sticky='w')
        form.columnconfigure(1, weight=1)
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=14)
        for action in ('启用系统代理', '检测代理', '预览配置', '应用配置', '检查状态', '恢复原配置'):
            button = ttk.Button(buttons, text=action, command=lambda a=action: self.run(a))
            button.pack(side='left', padx=(0, 6))
            self.widgets.append(button)
        save = ttk.Button(buttons, text='保存设置', command=self.save)
        save.pack(side='left')
        self.widgets.append(save)
        self.status = tk.StringVar(value='就绪：保存设置只记录界面选项，“应用配置”才修改快捷方式。')
        ttk.Label(frame, textvariable=self.status, wraplength=820).pack(anchor='w')
        history_bar = ttk.Frame(frame)
        history_bar.pack(fill='x', pady=(12, 4))
        ttk.Label(history_bar, text='操作记录（自动保留最近 100 条）').pack(side='left')
        clear_button = ttk.Button(history_bar, text='清空记录', command=self.clear_history)
        clear_button.pack(side='right')
        self.widgets.append(clear_button)
        self.log = ScrolledText(frame, wrap='word', font=('', 11), height=14)
        self.log.pack(fill='both', expand=True)
        self.log.configure(state='disabled')
        ttk.Label(frame, text=f'配置：{self.path}\n记录：{self.history_path}', wraplength=820).pack(anchor='w', pady=(8, 0))
        for record in self.history:
            self.append_record(record)
        self.sync_mode()
        if not self.path.exists():
            save_config(self.path, self.data)
        if not self.history_path.exists():
            save_history(self.history_path, self.history)

    def sync_mode(self):
        if self.mode.get() == 'manual':
            self.system_steps.grid_remove()
            self.manual_fields.grid()
        else:
            self.manual_fields.grid_remove()
            self.system_steps.grid()
        self.proxy_entry.configure(state='normal' if self.mode.get() == 'manual' and not self.proc else 'disabled')

    def browse(self):
        selected = filedialog.askopenfilename(filetypes=[('应用快捷方式', '*.desktop')])
        if selected:
            self.desktop.set(selected)

    def snapshot(self):
        data = {**self.data, 'mode': self.mode.get(), 'proxy_url': self.proxy.get().strip(),
                'desktop_path': self.desktop.get().strip()}
        validate_config(data)
        if data['mode'] == 'manual':
            validate_url(data['proxy_url'])
        return data

    def save(self):
        try:
            data = self.snapshot()
            save_config(self.path, data)
            self.data = data
            self.status.set('设置已保存；尚未修改应用快捷方式。')
            return True
        except (SetupError, OSError, ValueError) as exc:
            messagebox.showerror('保存失败', str(exc))
            return False

    def run(self, action):
        if self.proc:
            return
        if action in ('应用配置', '恢复原配置') and not messagebox.askyesno(
                action, '将备份并修改用户级快捷方式。继续？' if action == '应用配置'
                else '将恢复安装前的快捷方式。用户后续修改会受到保护。继续？'):
            return
        if not self.save():
            return
        try:
            args = command_for(action, self.data)
            # A temporary file avoids pipe-buffer deadlocks and blocking the UI thread.
            import tempfile
            self.output_file = tempfile.TemporaryFile()
            self.proc = subprocess.Popen(args, stdout=self.output_file, stderr=subprocess.STDOUT)
        except (OSError, SetupError) as exc:
            if self.output_file:
                self.output_file.close()
            messagebox.showerror('启动失败', str(exc))
            return
        self.action = action
        for widget in self.widgets:
            widget.configure(state='disabled')
        self.sync_mode()
        self.status.set(f'正在{action}…')
        self.root.after(150, self.poll)

    def poll(self):
        if self.proc.poll() is None:
            self.root.after(150, self.poll)
            return
        code = self.proc.returncode
        self.output_file.seek(0)
        output = self.output_file.read().decode('utf-8', errors='replace')[-16000:]
        self.output_file.close()
        self.proc = None
        record = {'time': datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'),
                  'action': self.action, 'result': '成功' if code == 0 else '失败', 'output': output}
        self.history = (self.history + [record])[-100:]
        self.append_record(record)
        self.status.set(f'{self.action}：{record["result"]}。详情见操作记录。')
        try:
            save_history(self.history_path, self.history)
        except (OSError, SetupError, ValueError):
            self.status.set('操作已结束，但记录保存失败；请检查 JSON 文件及权限。')
        for widget in self.widgets:
            widget.configure(state='normal')
        self.sync_mode()

    def clear_history(self):
        if self.proc:
            return
        try:
            save_history(self.history_path, [])
        except (OSError, SetupError, ValueError):
            messagebox.showerror('清空失败', '记录未清除，请检查配置文件及权限。')
            return
        self.history = []
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')
        self.status.set('操作记录已清空并保存，代理设置保持不变。')

    def append_record(self, record):
        self.log.configure(state='normal')
        self.log.insert('end', f'[{record["time"]}] {record["action"]} · {record["result"]}\n{record["output"]}\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def close(self):
        if self.proc:
            messagebox.showinfo('操作正在进行', '请等待操作完成后再关闭，以免中断配置写入。')
            return
        if self.save() or messagebox.askyesno('关闭窗口', '设置未保存，是否放弃本次界面输入并关闭？'):
            self.root.destroy()


def main():
    root = tk.Tk()
    try:
        App(root)
    except (SetupError, OSError, ValueError) as exc:
        messagebox.showerror('无法读取配置', f'{exc}\n原配置未覆盖。')
        root.destroy()
        return 1
    root.mainloop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
