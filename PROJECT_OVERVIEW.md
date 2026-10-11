# Ubuntu Codex Proxy Launcher

## 目标与状态

英文项目名为 **Ubuntu Codex Proxy Launcher**，推荐 GitHub 仓库名为 `ubuntu-codex-proxy-launcher`。为兼容已经安装的版本，用户配置及数据目录继续使用内部标识 `codex-proxy-setup`。

自动读取 Ubuntu 上 Clash/Mihomo 等客户端对应的代理信息，为 ChatGPT/Codex 生成持久的用户级启动配置。

第一版已实现，使用 uv 管理 Python 3.12 环境，无第三方 Python 依赖，并使用本地 Git 管理版本。用户已反馈在本机应用配置并从图标启动正常，系统代理端口变更后仍可使用。尚未完成充分的多设备测试，Ubuntu 22.04 仅为兼容候选。

已有人工案例：启动环境变量指向 `http://127.0.0.1:7897` 后，用户确认能够登录并使用 Codex；用户级 `chatgpt.desktop` 可保存同样设置。案例不代表所有 Ubuntu 版本、客户端或应用组件均已验证。云端对话曾间歇性超时，根因未确认。

## 已实现能力

- 检测代理来源、校验地址；对环境代理存在作提示，不自动回退或显示敏感值。
- 定位应用启动入口和 desktop 文件。
- 预览、备份并生成用户级配置，验证格式并提供恢复。
- 默认每次启动重新读取 GNOME 手动代理；显式 `--proxy` 为固定地址模式。
- UI/CLI 可在校验 GNOME 已保存地址和端口后将代理模式切换为 Manual；不启动代理客户端、不静默改写地址。

本机验证 Ubuntu 24.04.5、Python 3.12.3、uv 0.12.3。支持普通原生应用 desktop 入口。依赖 gsettings 和 desktop-file-validate，notify-send 可选。详细操作见 README.md：`detect` 检测、`install` 预览、`install --apply` 应用、`status` 检查、`restore` 恢复。

优先级为显式地址 > GNOME 手动代理；环境变量只提示存在，不作为回退。动态检测、端口检查、环境变量设置后执行原应用。默认写入用户数据目录中的 applications 与 codex-proxy-setup，安装后通过系统 Python 启动，无需保留 uv 环境。

## 文件结构

- `AGENTS.md`：工作约定、配置安全、验证与自动版本管理。
- `CHANGELOG.md`：实质性修改和验证记录。
- `PROJECT_OVERVIEW.md`：目标、现状和待办。
- `proxy_setup.py`：检测、配置、启动、恢复与 CLI。
- `tests/test_proxy_setup.py`：隔离目录自动化测试。
- `pyproject.toml`、`uv.lock`：uv 环境，按当前系统选择符合 Python 3.10+ 的解释器。
- `README.md`：安装使用、验证和限制。
- `gui.py`：Tkinter 界面、异步操作及 JSON 配置/历史持久化。
- `main.py`：IDE 图形界面统一启动入口。
- `.vscode/`：F5/Ctrl+F5 启动配置、uv 解释器路径与扩展推荐。
- `config.example.json`：界面配置示例；真实配置保存于用户配置目录。
- `tests/test_gui.py`：JSON 持久化、凭据拒绝、损坏保护及命令参数测试。

## 限制与后续工作

固定代理地址不会自动跟随端口变化；代理关闭可能导致联网失败；已运行应用可能需要完全退出后重新启动。用户级快捷方式可能保留旧安装路径，升级后需核对。

测试使用隔离目录，覆盖端口变化、非法配置、旧环境清理、启动参数、重复执行、恢复与失败回滚。TCP 检查不等于目标服务验证。PAC、认证代理、Snap/Flatpak、复杂 shell Exec 和自动直连不支持；环境与 GNOME 冲突时始终采用所选明确来源。

图形界面通过 `uv run python gui.py` 启动，复用 CLI，提供检测、预览、应用、状态、恢复和保存设置。模式、地址和快捷方式保存在 ~/.config/codex-proxy-setup/config.json，最近 100 条记录单独保存在同目录 history.json。旧混合格式启动时自动迁移；清空记录只写 history.json。保存界面选项不会自动应用到已安装启动器。

UI 顶部醒目标注配置前必须启动 Clash/Mihomo 等客户端并开启其系统代理功能。跟随模式显示“启用系统代理”为第一步，用于校验 GNOME 中已保存的端点并将模式切换为 Manual。按钮失败时，用户通常只需在 Ubuntu 设置中手动切换为 Manual；只有端点为空或错误时才填写地址和端口。之后自动检测代理和快捷方式；手动模式显示两个输入框。切换时保留手动值，但跟随模式执行命令不携带隐藏的手动地址或快捷方式。

记录区提供“清空记录”，同步清空 JSON 历史并保留设置；写入失败时保留现有记录，操作执行期间禁用。

用户配置与历史保存在用户配置目录，实际启动器与备份保存在用户数据目录，并非全部保存在项目内。GitHub 仅分享源码、文档、示例和环境声明；README 提供新用户操作流程、支持矩阵与完整路径说明。

后续优先完成 Ubuntu 22.04/更多设备验证和更多安装方式兼容。不需要机器人环境、Windows 提交脚本或 NTFS 镜像。
