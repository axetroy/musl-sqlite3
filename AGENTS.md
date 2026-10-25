# AGENTS.md

## 项目概况

本仓库通过 GitHub Actions 从 SQLite 官方下载页获取并校验 amalgamation 源码，构建、测试和发布 Linux、macOS、Windows 的 `sqlite3` 命令行工具。Linux 二进制使用 musl 静态链接；macOS 和 Windows 仍依赖操作系统提供的库。

## 目录与职责

- `scripts/download_sqlite.py`：查找 SQLite 发布版本，校验下载文件大小和 SHA3-256，并提取构建所需源码。
- `scripts/http_utils.py`：共享的有限次数 HTTP 重试逻辑。
- `scripts/check_sqlite_update.py`：检查最新 SQLite 版本是否已有正式 GitHub Release。
- `scripts/windows/CMakeLists.txt`：Windows 构建配置。
- `tests/`：Python 标准库 `unittest` 测试。
- `.github/workflows/ci-sqlite.yml`：编排源码校验和所有平台的 CI 构建。
- `.github/workflows/build-sqlite-*.yml`：Linux、macOS 和 Windows 的构建、验证与产物上传。
- `.github/workflows/release-sqlite.yml`：定时或手动检查版本，并在满足条件时发布 Release。
- `design.md`：构建目标、架构和发布设计的详细说明。

## 开发与验证

- 运行 Python 辅助脚本测试：

  ```sh
  python3 -m unittest discover -s tests
  ```

- Python 脚本仅依赖标准库；不要为已有功能引入第三方依赖，除非需求确实需要。
- 修改构建或发布 workflow 时，核对输入、权限、触发条件、目标架构和产物名称是否在调用方与可复用 workflow 间保持一致。
- 完整平台构建及 smoke test 在 GitHub Actions 对应 runner 中执行；本地无法验证的平台行为应明确说明，不要用单个平台的结果代替全平台验证。
- 更新支持的平台、构建选项或发布行为时，同步检查并更新 `README.md`、`README.en.md` 和 `design.md` 中相关说明。

## 构建与发布约束

- 不要将下载得到的 SQLite amalgamation 源码或构建二进制提交到仓库；CI 会按需下载、校验并在短期 artifact 中传递源码。
- 保留对官方 SQLite 文件大小及 SHA3-256 的校验，以及对生成二进制架构、链接依赖和 SQLite 版本查询的验证。
- 不要让普通 CI 或脚本变更自动创建 Release。手动运行发布 workflow 时，`dry_run` 默认开启；实际发布需明确关闭，并从默认分支运行。
- 发布前必须确保所有目标平台构建和 smoke test 成功；不要覆盖已有 Release 或在未经确认时处理冲突的 Git tag。
