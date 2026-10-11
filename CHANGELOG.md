# 更新日志

## 2026-10-11（JST）— 前置条件提示与快速启动

- UI 顶部醒目标注配置前必须启动 Clash/Mihomo 等代理客户端并开启其系统代理功能。
- README 中文和英文说明开头新增快速启动，重复提供 IDE 运行 main.py、终端运行 main.py 和 CLI 帮助入口。
- 主要文件：gui.py、README.md、PROJECT_OVERVIEW.md、CHANGELOG.md。
- 验证：GUI 提示内容及布局、README 中英文启动命令、完整测试和 Python 编译检查。
- 自动版本提交：已完成。

## 2026-10-11（JST）— GNOME 系统代理启用操作

- 新增 UI/CLI“启用系统代理”：读取 GNOME 中保留的手动地址，先校验端口，再切换当前用户代理模式为 Manual；重复操作幂等。
- UI 将此操作放在流程首位，并显示 Ubuntu 设置中的手动开启路径，自动操作失败后仍可继续配置。
- 不启动 Clash/Mihomo、不猜测或改写代理地址；代理客户端未运行或地址无效时不改变系统模式。
- 主要文件：proxy_setup.py、gui.py、tests/test_proxy_setup.py、tests/test_gui.py、README.md、PROJECT_OVERVIEW.md、CHANGELOG.md。
- 验证：自动启用、已启用幂等、端口检查失败不改模式、GUI 命令映射及完整回归测试。
- 自动版本提交：已完成。

## 2026-10-09（JST）— README 英文用户说明

- 在完整中文说明之后追加英文用户指南，覆盖测试提示、问题背景、解决原理、支持范围、安装操作、配置位置、安全边界、恢复及限制。
- 确定英文项目名 `Ubuntu Codex Proxy Launcher`，推荐仓库/包名 `ubuntu-codex-proxy-launcher`；保留内部数据目录名以兼容现有配置。
- 保持中文为首要说明，英文内容使用相同的已验证事实和谨慎表述，不扩大兼容性承诺。
- 主要文件：README.md、CHANGELOG.md。
- 验证：Markdown 差异检查、相对链接和中英文关键路径核对通过；本次不修改程序行为。
- 自动版本提交：已完成。

## 2026-10-09（JST）— GitHub 提交准备

- 审核拟提交文件及敏感内容，确认真实用户配置、历史、启动器备份和桌面快捷方式均位于仓库外。
- 扩充忽略规则，排除本地环境文件、根目录运行配置/历史/状态、日志、备份、IDE 私有目录、虚拟环境和缓存。
- 移除固定 Python 3.12 的 `.python-version`，由 uv 在目标设备选择符合 Python 3.10+ 的解释器，避免 Ubuntu 22.04 被无必要地强制到 3.12；实际 3.10 兼容性仍待验证。
- 主要文件：`.gitignore`、README.md、PROJECT_OVERVIEW.md、CHANGELOG.md。
- 验证：完整测试、Python 编译、uv 锁文件、desktop 预览、JSON/VS Code 格式、敏感内容和拟提交清单检查。
- 自动版本提交：已完成。

## 2026-10-09（JST）— 新用户文档与分享准备

- README 首行加入设备测试不充分提示，补充问题背景、已知证据与未确认原因、解决流程和适用环境矩阵。
- 补充新用户环境准备、GUI/CLI 操作、启动验证、数据保存位置及 GitHub 分享边界；明确配置与历史不在项目目录。
- 更新项目说明中的单设备验收状态，记录用户对图标启动及端口变化后的正常使用反馈。
- 主要文件：README.md、PROJECT_OVERVIEW.md、CHANGELOG.md。
- 验证：文档命令、文件路径与当前实现逐项核对，检查本地文件引用与差异格式；本次不修改程序行为，不宣称新增设备兼容性测试。
- 自动版本提交：已完成。

## 2026-10-09（JST）— 配置与操作历史分离

- config.json 仅保存界面配置，history.json 单独保存最近 100 条记录；清空记录不再写配置文件。
- 启动时迁移旧混合格式，历史写入成功后才移除配置历史字段，迁移重试去重。
- 主要文件：gui.py、config.example.json、tests/test_gui.py、README.md、PROJECT_OVERVIEW.md。
- 验证：20 项测试通过，覆盖旧格式迁移和清空不改变配置；临时目录 GUI 清空检查通过。真实用户记录将在重新启动界面时迁移。
- 自动版本提交：已完成。

## 2026-10-09（JST）— 清空操作记录

- 记录区新增清空按钮，同步清除界面和 JSON 历史，保留代理设置；写入失败保留记录，执行操作期间禁用。
- 主要文件：gui.py、README.md、PROJECT_OVERVIEW.md。
- 验证：临时配置下验证清空持久化、设置保留及保存失败保护。
- 自动版本提交：已完成。

## 2026-10-09（JST）— 按模式显示输入区域

- 跟随模式隐藏代理地址和快捷方式输入框，显示四步操作说明；手动模式显示输入框。
- 切换保留手动值，跟随模式执行时忽略手动快捷方式，避免隐藏输入影响检测。
- 主要文件：gui.py、tests/test_gui.py、README.md、PROJECT_OVERVIEW.md。
- 验证：19 项测试通过；Tk 模式切换、字段值保留和布局显示检查通过。
- 自动版本提交：已完成。

## 2026-10-09（JST）— IDE 一键启动入口

- 新增 main.py 作为图形界面统一启动入口。
- 新增 VS Code 启动配置，使用 uv 的 .venv/bin/python；补充 Python 扩展推荐与 IDE 使用说明。
- 主要文件：main.py、.vscode/launch.json、.vscode/settings.json、.vscode/extensions.json、README.md、PROJECT_OVERVIEW.md。
- 验证：入口导入与 Python 语法、VS Code JSON 格式及入口/解释器路径检查通过；未实际操作 VS Code F5。
- 自动版本提交：已完成。

## 2026-10-09（JST）— 图形界面与 JSON 配置

- 新增 Tkinter 操作界面，复用 CLI 实现检测、预览、应用、状态和恢复，后台进程避免阻塞界面。
- 用户 JSON 保存模式、地址、快捷方式和最近 100 条带时间的操作记录；原子写入、0600 权限、拒绝认证代理，损坏配置不覆盖。
- 添加配置示例及启动说明，区分界面设置和已应用启动配置。
- 主要文件：gui.py、config.example.json、tests/test_gui.py、README.md、PROJECT_OVERVIEW.md。
- 验证：19 项自动化测试、Tk 窗口初始化和状态按钮执行检查、Python 编译检查；未通过 GUI 修改真实快捷方式。
- 自动版本提交：已完成。

## 2026-10-09（JST）— 第一版工具与 uv 环境

- 建立 uv/Python 3.12 环境和锁文件，无第三方 Python 依赖，初始化本地 Git main 分支。
- 实现 GNOME 手动代理检测、显式地址、端口检查、预览、用户级安装、启动时动态读取、状态校验与备份恢复。
- 保留绕过项，清除旧代理变量，支持普通 desktop 启动参数和动作；配置失败回滚，保护安装后用户修改。
- 安装的启动器独立运行，不依赖项目目录或 uv 环境。
- 主要文件：proxy_setup.py、tests/test_proxy_setup.py、pyproject.toml、uv.lock、.python-version、.gitignore、README.md、PROJECT_OVERVIEW.md。
- 验证：uv 离线同步成功，15 项隔离测试通过，Python 编译和差异检查通过；本机 GNOME 检测、TCP 端口连接和 desktop 格式预览通过。未对真实桌面应用安装，也未退出当前应用验证登录或对话加载。
- 自动版本提交：已完成。
