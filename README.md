> **测试提示：本程序尚未经过充分的多设备、多系统版本测试，目前仍为早期版本。仅在一台 Ubuntu 24.04.5 GNOME 设备上获得实际使用反馈，不能保证适用于所有 Ubuntu 版本、硬件、代理客户端或 Codex 安装方式。请先检测和预览，再应用配置。**

# Ubuntu Codex 代理启动配置

从 GNOME 手动系统代理读取地址，为 ChatGPT/Codex 安装用户级桌面启动器。之后点击原图标时重新检测代理，不再每次输入 `env ... chatgpt`。系统代理更新端口后，下次启动自动读取新端口。

## 为什么编写这个项目

本项目源自一次 Ubuntu 上 ChatGPT/Codex 启动与联网问题：代理客户端已经运行，但应用仍无法正常使用；通过命令行显式设置 HTTP_PROXY、HTTPS_PROXY 等代理环境变量后，用户确认能够启动、登录并使用 Codex。

这组对照结果支持“应用启动时需要合适的代理环境”这一判断，但并未通过完整网络日志证明所有故障的唯一根因。桌面系统代理、终端环境变量和 TUN 是不同机制，应用各组件也可能采用不同的网络设置。开启系统代理不等于每个应用进程都会读取并使用它。

历史排查中还出现过部分云端对话加载超时。该问题的具体原因未确认，不能直接归因为旧进程、缓存、WebSocket 或代理端口，也不应承诺本工具一定解决所有超时。

本工具适用于“应用本身可运行，但需要显式代理环境才能正常联网”的场景。它不修复缺少系统库、应用崩溃、账户权限、服务故障或不兼容的安装包，也不提供代理节点或网络服务。

## 解决方式

配置工具读取代理和应用入口，备份原有用户快捷方式，再生成新的用户级启动入口。后续流程是：

```text
点击原应用图标
  → 启动本工具的用户级 launcher.py
  → 读取当前 GNOME 系统代理（或使用手动固定地址）
  → 检查代理 TCP 端口
  → 设置大小写代理环境变量和绕过列表
  → 执行原应用
```

不改写系统安装文件或全局代理，不需要 root 来应用配置。启动器不会主动关闭已有应用，因此配置或端口改变后，应完全退出再从图标启动。命令行直接输入 `chatgpt` 不会经过这个桌面入口。

用户已反馈：应用配置后从图标启动正常；端口由 7897 改为 7890 后仍可正常使用。这是单设备功能反馈，不是跨设备认证或对具体网络路径的抓包验证。

## 适用设备与支持范围

本工具主要取决于操作系统、桌面环境和应用安装方式，不绑定电脑品牌，也不要求特定 GPU。

| 环境 | 当前范围 |
| --- | --- |
| Ubuntu 24.04.5 + GNOME | 已有单设备使用反馈及本机测试 |
| Ubuntu 22.04 + GNOME | 兼容候选，尚未在真实设备和 Python 3.10 上完成验证 |
| 其他 Ubuntu 版本或 GNOME Linux 发行版 | 未验证，不作支持承诺 |
| KDE、XFCE 等非 GNOME 桌面 | 自动跟随模式不支持；显式地址模式仍需单独验证 |
| Windows、macOS | 当前不支持 |
| Clash、Clash Verge、Mihomo 或其他客户端 | 不绑定品牌；需提供可用代理并正确写入 GNOME 设置，或手动指定地址 |
| Snap、Flatpak、复杂 shell 启动入口 | 首版不支持 |

Python 源码声明要求 3.10+，实际开发测试使用 3.12；这不等于已完成各 Python 版本验证。Codex/ChatGPT 应用自身也必须兼容目标设备。本工具与应用安装包的兼容性应分别验证。

## 环境

- Ubuntu GNOME、Python 3.10+（开发环境使用 uv + Python 3.12）。
- `gsettings`、`desktop-file-validate`（desktop-file-utils）。可选 `notify-send`，用于图标启动失败提示。
- 首版支持原生应用的普通 `.desktop` 入口；不支持 Snap/Flatpak、复杂 shell 启动命令、PAC 和带认证的代理。
- 本机验证环境：Ubuntu 24.04.5、Python 3.12.3、uv 0.12.3。

## 使用

### 新用户准备

1. 安装能够在本机运行的 ChatGPT/Codex，确认存在普通 `.desktop` 应用入口。
2. 启动代理客户端，开启 GNOME 手动系统代理，并确认代理地址和端口有效。
3. 下载或克隆本项目，进入项目根目录，安装 uv。
4. Ubuntu 系统依赖可通过下面命令安装（需要管理员权限，仅用于安装依赖）：

```bash
sudo apt install python3 python3-tk desktop-file-utils libglib2.0-bin libnotify-bin
uv sync --locked
uv run python -c "import tkinter; print(tkinter.TkVersion)"
uv run python main.py
```

uv 会选择满足 Python 3.10+ 要求的解释器。推荐使用 Ubuntu 自带的 Python，以便配合 `python3-tk`；若 uv 选择了独立下载的 Python，该解释器也必须自身支持 Tkinter。上面的导入检查失败时，先解决解释器/Tk 依赖再运行 UI。

### 推荐操作顺序

1. 保持“跟随 GNOME 系统代理”，此模式只显示步骤，不显示手动输入框。
2. 点击“检测代理”，确认读取到的地址与客户端一致。端口可连接不等于代理协议或远端服务已验证。
3. 点击“预览配置”，确认目标快捷方式；此时不会写入启动配置。
4. 点击“应用配置”，确认后工具备份并写入用户级文件。
5. 点击“检查状态”，查看每个文件的具体状态。“操作成功”只表示命令执行结束，必须同时阅读输出；“尚未安装”不代表已配置。
6. 完全退出 ChatGPT/Codex，再通过原图标打开，实际发送消息并验证所需功能。

已正常配置后不必每天运行本工具。跟随模式下，只要客户端和 GNOME 代理设置同步更新，下次完整启动就会读取新端口。

手动模式下填写完整地址（如 `http://127.0.0.1:7897`），快捷方式可留空自动检测，也可选择 `.desktop` 文件。该模式保存固定地址，端口变化需重新配置。

### 图形界面

**VS Code 一键运行：**打开整个项目文件夹，安装推荐的 Python / Python Debugger 扩展，按 F5（调试）或 Ctrl+F5（直接运行），选择“启动 Codex 代理配置界面”。配置固定使用本项目 uv 创建的 `.venv/bin/python`。

也可以打开根目录 `main.py`，点击“运行 Python 文件”。若 VS Code 曾记住其他解释器，请通过“Python: Select Interpreter”选择本项目 `.venv/bin/python`。其他 IDE 同样将 `main.py` 设置为运行入口、选择此解释器即可。

完成环境准备后可直接运行。新电脑需先执行 `uv sync --locked` 创建环境；VS Code 启动配置不会自动安装依赖。

```bash
uv sync --locked
uv run python gui.py
```

界面提供检测代理、预览配置、应用配置、检查状态、恢复原配置、保存设置。
操作记录右侧的“清空记录”会清除界面和 JSON 中的全部历史，保留代理设置；操作执行期间按钮禁用。清除后无法通过本工具恢复。
默认跟随系统代理，也可选择手动固定地址；快捷方式留空则自动检测。
跟随模式隐藏两个输入框，显示检测、预览、应用及重启的操作步骤，并自动寻找快捷方式。
切换手动模式后显示代理地址和快捷方式输入框；切回跟随模式保留手动值，但不使用它们执行操作。
应用与恢复操作有确认提示，后台执行时界面不会阻塞，操作结果显示在记录区。
关闭窗口自动保存设置。保存设置不代表已应用到 Codex 启动器。

界面配置保存在 `~/.config/codex-proxy-setup/config.json`，最近 100 条操作记录单独保存在同目录的 `history.json`。
（设置 `XDG_CONFIG_HOME` 时使用对应目录），权限为 0600。
项目的 `config.example.json` 展示格式。此文件与安装后的启动器 config.json 职责不同：
界面 config.json 只保存用户选项，history.json 只保存历史；清空记录不写配置文件。
旧版混合文件在下次启动时自动迁移，先保存历史，再移除配置中的 history 字段。
启动器 JSON 保存已应用模式，不会在保存界面时自动同步。
配置损坏时提示并保留原文件，不静默覆盖。手动代理不接受账号密码。

UI 使用 Tkinter，uv 不负责安装系统 Tk 库；若报缺少 tkinter，请安装 Ubuntu 的 `python3-tk`。
本机系统 Python 和 uv 环境均已验证可导入 Tkinter 8.6。

### 命令行

在项目目录运行：

```bash
uv sync --locked
uv run python proxy_setup.py detect --check
uv run python proxy_setup.py install
uv run python proxy_setup.py install --apply
```

`install` 默认只预览，`--apply` 才写入并备份已有快捷方式。完成后手动完全退出应用，再点击原图标。不自动关闭会话，也不修改全局代理。

```bash
# 查看受管理文件是否完整
uv run python proxy_setup.py status
# 恢复安装前的快捷方式
uv run python proxy_setup.py restore
# 无法自动定位应用时显式指定（仍先预览）
uv run python proxy_setup.py install --desktop /usr/share/applications/chatgpt.desktop
# 显式固定地址：不会自动跟随 GNOME 设置
uv run python proxy_setup.py install --proxy http://127.0.0.1:7897
```

显式选项在正式应用时需再次传入。变更已安装的模式或更新启动器代码，请先恢复，再重新安装；重复安装同一配置不会覆盖文件。

安装后启动器使用系统 `/usr/bin/python3`，无需启动 uv 或保留项目目录。执行恢复仍需本工具代码。

## 来源与行为

1. 有 `--proxy` 时使用该固定地址。
2. 否则每次启动读取 GNOME 手动代理，读取 HTTP、HTTPS、SOCKS 和绕过列表。
3. 环境代理变量不作为自动回退来源：避免从旧进程继承旧端口。检测时提示其存在，不输出潜在凭据。

HTTP 与 HTTPS 的系统设置可以不同；GNOME HTTPS 栏表示用于 HTTPS 目标的 HTTP 代理，不能据此推断代理服务器自身使用 TLS。SOCKS 使用 `socks5h`。代理客户端本身的协议支持仍需实际验证。

启动前对配置的端口进行有限次数 TCP 连接检查，失败通知并停止，不自动直连。此检查不验证代理协议、出口节点或 OpenAI 服务。主机名 DNS 解析耗时仍受操作系统影响。GNOME 例外项、原快捷方式中 NO_PROXY 和启动环境的例外项合并保留，但 CIDR/通配符是否生效取决于应用组件。

## 备份与安全

**并非所有文件都在项目目录。** 项目保存源码、示例和环境声明，个人配置、操作历史以及实际安装的启动器保存在用户目录，不随克隆项目自动迁移。

| 默认位置 | 用途 | 是否应提交 GitHub |
| --- | --- | --- |
| 项目内 `config.example.json` | 不含个人数据的配置格式示例 | 是 |
| 项目内 `pyproject.toml`、`uv.lock` | Python 要求与 uv 锁定环境 | 是 |
| 项目内 `.venv/` | 本机虚拟环境 | 否，已忽略 |
| `~/.config/codex-proxy-setup/config.json` | 界面配置：模式、手动地址、快捷方式路径 | 否 |
| `~/.config/codex-proxy-setup/history.json` | 最近 100 条操作记录 | 否 |
| `~/.local/share/codex-proxy-setup/config.json` | 已应用的启动模式和绕过项，与界面配置不同 | 否 |
| `~/.local/share/codex-proxy-setup/launcher.py` | 安装后的独立启动器副本 | 否，仓库保留其源代码 |
| `~/.local/share/codex-proxy-setup/state.json` | 管理目标及内容校验值 | 否 |
| `~/.local/share/codex-proxy-setup/original.desktop` | 原用户快捷方式备份（原来存在时） | 否 |
| `~/.local/share/applications/<应用名>.desktop` | 实际生效的用户快捷方式 | 否 |

`XDG_CONFIG_HOME` 可改变前两项用户配置的根目录，`XDG_DATA_HOME` 可改变安装文件的根目录。“保存设置”只写界面 config.json；“应用配置”才写启动器配置；“清空记录”只清空 history.json。

文件放在 `$XDG_DATA_HOME`，未设置时使用 `~/.local/share`：

- `applications/<原desktop文件名>`：用户级快捷方式，覆盖系统同名入口。
- `codex-proxy-setup/launcher.py`：独立启动代码。
- `codex-proxy-setup/config.json`：检测模式与保留的绕过项。
- `codex-proxy-setup/original.desktop`：原用户快捷方式备份（原先存在时）。
- `codex-proxy-setup/state.json`：变更记录与内容校验值。

重复执行不叠加包装。恢复前检查生成文件与备份；发现用户后续修改就拒绝覆盖。目录私有、状态文件权限为 0600。备份可能含原快捷方式中的私人配置，不要提交或分享此目录。

恢复原配置不会删除界面选项和历史；删除项目文件夹也不会卸载已安装启动器。要撤销启动修改，请先使用“恢复原配置”。如需迁移到其他设备，复制项目后重新检测安装，不要直接套用带有旧路径和校验值的 state.json。

## GitHub 分享与问题反馈

仓库应包含源码、测试、README、项目说明、更新日志、示例 JSON、uv 锁文件和 IDE 配置。不要上传实际用户配置、历史记录、快捷方式备份或虚拟环境。当前默认个人数据在仓库外；如果手动复制回项目，请在提交前再次检查。

反馈问题时提供 Ubuntu 版本、桌面环境、Python 版本、应用安装方式、代理模式、失败步骤和经过脱敏的错误信息。不要上传代理凭据或完整私人日志。

项目尚未指定开源许可证。公开推送不等于授予他人任意使用和分发权；正式对外发布前由维护者选择许可证。当前文档更新不执行远程推送。

## 限制

- 必须先运行代理客户端并启用 GNOME 手动系统代理；PAC、TUN-only 或关闭状态需手动指定受支持的代理地址。
- 若客户端改端口却未更新 GNOME，工具无法凭空获得新值。
- 当前已运行进程不受修改影响；终端直接输入 `chatgpt` 也不经过此快捷方式。
- 不保证所有应用组件支持代理变量，不保证消除云端对话超时。
- 不支持代理认证、自动直连回退或客户端私有配置解析。
- 应用升级改变入口后需重新检测安装；自定义复杂快捷方式不会被静默改写。

## 开发验证

```bash
uv run python -m unittest discover -s tests -v
uv run python -m py_compile proxy_setup.py
git diff --check
```

测试在临时目录进行，不改真实桌面设置。uv 环境无第三方 Python 依赖。
