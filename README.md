# sqlite3-static-link-prebuilt

简体中文 | [English](README.en.md)

为 Linux、macOS 和 Windows 构建独立的 SQLite 命令行工具。

| 平台 | 架构 | 依赖说明 |
| --- | --- | --- |
| Linux | x86、x86_64、arm（ARMv7）、arm64、mips64el、loong64 | 使用 musl 静态链接 |
| macOS | universal2（x86_64、arm64） | SQLite 编入可执行文件；依赖 macOS 系统库 |
| Windows | x86、x86_64、arm64 | MSVC 运行库静态链接（`/MT`）；依赖 Windows 系统 DLL |

## 与 SQLite 官方预编译包的区别

[SQLite 官方下载页](https://sqlite.org/download.html)提供由 SQLite 项目发布的预编译工具包。本项目不是官方二进制的镜像，而是下载官方 SQLite amalgamation 源码，校验官方提供的文件大小和 SHA3-256 后，再按本项目的构建配置编译和测试。

| 对比项 | SQLite 官方预编译包 | 本项目 |
| --- | --- | --- |
| Linux 架构与链接 | 官方下载页按其列出的系统和架构提供对应工具包；当前 Linux CLI 工具包面向 x64 | 提供 x86、x86_64、ARMv7、arm64、mips64el、loong64；全部使用 musl 静态链接，不依赖 glibc |
| 工具内容 | 官方 Linux/macOS CLI 工具包除 `sqlite3` 外，还包含 `sqldiff`、`sqlite3_analyzer` 和 `sqlite3_rsync` | 只提供 `sqlite3` 命令行工具 |
| 构建配置 | 由 SQLite 项目维护和发布 | 由本项目 CI 从官方源码构建，并启用 FTS5、JSON1、R*Tree |
| 其他平台 | 以官方页面实际列出的平台和架构为准 | 提供 macOS universal2 和 Windows x86、x86_64、arm64；这些系统仍依赖操作系统提供的库或 DLL |

如果需要 SQLite 官方打包的完整工具集，请使用[官方预编译包](https://sqlite.org/download.html)；如果需要 Linux musl 静态二进制或官方 Linux 工具包未列出的架构，可使用本项目。两者的编译配置可能不同，启用的扩展和运行依赖也不应假定完全一致。

正式二进制和 `SHA256SUMS` 可在 [GitHub Releases](https://github.com/axetroy/sqlite3-static-link-prebuilt/releases) 下载。

## 手动构建并验证

不必等每周的发布检查。要立即构建所有平台并验证二进制，但不创建 Release：

1. 打开仓库的 [Actions](https://github.com/axetroy/sqlite3-static-link-prebuilt/actions) 页面，选择 **SQLite CI**。
2. 点击 **Run workflow**，选择要构建的分支。
3. `sqlite_version` 留空会使用 SQLite 最新稳定版；也可以填写明确版本号。
4. 点击 **Run workflow**。运行成功后，在本次 workflow run 页面底部的 **Artifacts** 区域下载各平台产物。

此流程会运行 Linux、macOS、Windows 的构建和 smoke test，只上传 Actions Artifacts，不发布 GitHub Release。

## 手动检查并发布

要立即检查 SQLite 是否有尚未发布的新版本，并在有新版本时构建、验证和发布：

1. 在 [Actions](https://github.com/axetroy/sqlite3-static-link-prebuilt/actions) 页面选择 **SQLite Release**，点击 **Run workflow**。
2. 选择仓库默认分支（当前为 `main`）。
3. 首次运行建议保持 `dry_run` 勾选。这样只检查版本，不构建或发布。
4. 确认要正式发布时，再运行一次并取消勾选 `dry_run`。

正式运行会检查 SQLite 官方最新稳定版：只有该版本尚未发布时，才会构建所有平台、验证二进制、生成 `SHA256SUMS` 并创建 GitHub Release。如果当前最新版本已经发布，则不会重复构建或覆盖现有 Release。正式发布必须从默认分支运行。

**注意：** `dry_run` 默认开启。若要真正发布，必须明确取消勾选；仅点击 **Run workflow** 不会自动发布。

## 自动发布

**SQLite Release** 工作流每周一 02:17 UTC（北京时间 10:17）检查 SQLite 官方稳定版。有新版本时会自动构建、验证并发布；push 相关 CI 文件或脚本只进行版本检查，不会因此创建 Release。

更多架构、构建和发布细节见 [design.md](./design.md)。

## 开源许可

本项目使用 [MIT License](./LICENSE)。
