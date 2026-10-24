# 技术方案：GitHub Actions 多架构 Alpine + musl 静态编译 SQLite3

## 1. 背景与目标

SQLite 官方预编译二进制依赖较高版本的 glibc，在低版本 Linux 环境（如 CentOS 7、旧版 Debian）中无法直接运行。在 glibc 环境下做“伪静态”编译并不可靠，部分符号仍可能动态依赖 NSS 等库。

**目标**：通过 GitHub Actions，在 Alpine Linux（musl libc）环境中为 `x86`（32 位）、`x86_64` 和 `arm64` 架构分别编译出**完全静态链接**的 SQLite3 命令行工具，产物可在任意 Linux 发行版上直接运行，不依赖目标系统的 glibc 或 musl 版本。

**预期产物**：
- `sqlite3-linux-x86`（i386 静态二进制）
- `sqlite3-linux-x86_64`（x86_64 静态二进制）
- `sqlite3-linux-arm64`（aarch64 静态二进制）

三者均为 ELF 静态链接可执行文件，`file` 命令输出应显示 “statically linked” 或 “static-pie linked”。


## 2. 技术路线选择

采用 **QEMU 模拟 + 目标架构 Alpine 容器内原生编译** 的方式，而非配置交叉编译工具链。

理由：
- 交叉编译 musl 工具链（如 `aarch64-linux-musl-gcc`）配置复杂，容易出现链接错误。
- 在 QEMU 模拟的目标架构 Alpine 容器中，直接使用该架构的原生 `gcc`（即 musl-gcc），编译过程与在真实 arm64 机器上一致，成功率更高。
- GitHub Actions 社区已有成熟模式：使用 `docker/setup-qemu-action` 启用模拟，再通过 `docker run` 运行目标架构的 Alpine 镜像。


## 3. 前置条件

### 3.1 CI 实时下载源码

无需将 SQLite 源码提交到仓库。每次 CI 运行时，调用仓库中的 `scripts/download_sqlite.py`，从 SQLite 官方下载页解析最新发布的 `sqlite-amalgamation-*.zip`，并根据官方元数据校验文件大小和 SHA3-256 后，提取 `shell.c`、`sqlite3.c`、`sqlite3.h`。脚本也支持按版本下载，供发布流程锁定检查到的版本。CI runner 需要可访问 `www.sqlite.org` 并提供 Python 3 标准库。

官方 amalgamation 压缩包包含 CLI 和静态编译所需的上述三个文件。使用官方发布页而非固定版本号，可以在每次运行时构建当时最新的 SQLite 稳定发布版。

### 3.2 GitHub Actions 权限

构建 Workflow 使用 `actions/upload-artifact` 保存验证产物，只需 `contents: read`。定时发布的检查任务也使用只读权限，只有最终发布 job 获得 `contents: write` 以创建 Release。


## 4. Workflow 文件设计

### 4.1 文件路径与触发条件

文件路径：`.github/workflows/build-sqlite-musl.yml`

触发条件：
- `workflow_dispatch`（可选指定 SQLite 版本，留空时构建最新版本）
- `workflow_call`（由定时发布工作流调用并传入固定版本）
- `push` 修改相关 Workflow 或 `scripts/**` 时自动构建。
- 此工作流只上传 GitHub Actions Artifact；正式 Release 由 `.github/workflows/release-sqlite.yml` 发布。

### 4.2 完整 Workflow 内容

```yaml
name: Build Static SQLite3 (Alpine + musl)

on:
  workflow_dispatch:
    inputs:
      sqlite_version:
        description: SQLite version to build (blank means latest)
        required: false
        type: string
        default: ''
  workflow_call:
    inputs:
      sqlite_version:
        description: SQLite version to build (blank means latest)
        required: false
        type: string
        default: ''
  push:
    paths:
      - '.github/workflows/build-sqlite-musl.yml'
      - '.github/workflows/release-sqlite.yml'
      - 'scripts/**'

permissions:
  contents: read

jobs:
  build:
    name: Build sqlite3 for ${{ matrix.arch }}
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        include:
          - arch: x86
            platform: linux/386
            qemu-platform: 386
          - arch: x86_64
            platform: linux/amd64
            qemu-platform: amd64
          - arch: arm64
            platform: linux/arm64
            qemu-platform: arm64

    steps:
      - name: Checkout repository
        uses: actions/checkout@v7.0.1

      - name: Download SQLite amalgamation
        env:
          SQLITE_VERSION: ${{ inputs.sqlite_version }}
        run: |
          if [ -n "$SQLITE_VERSION" ]; then
            python3 scripts/download_sqlite.py --version "$SQLITE_VERSION"
          else
            python3 scripts/download_sqlite.py
          fi

      # 仅 x86_64 可直接在 runner 上运行
      - name: Set up QEMU
        if: matrix.arch != 'x86_64'
        uses: docker/setup-qemu-action@v4.4.0
        with:
          platforms: ${{ matrix.qemu-platform }}

      # 在目标架构的 Alpine 容器中编译
      - name: Compile static sqlite3 inside Alpine
        run: |
          docker run --rm \
            -v "${{ github.workspace }}:/work" \
            -w /work \
            --platform ${{ matrix.platform }} \
            alpine:latest \
            sh -c '
              set -e
              apk add --no-cache build-base
              gcc -Os -static \
                -DSQLITE_ENABLE_FTS5 \
                -DSQLITE_ENABLE_JSON1 \
                -DSQLITE_ENABLE_RTREE \
                shell.c sqlite3.c \
                -o sqlite3-linux-${{ matrix.arch }} \
                -lpthread -ldl -lm
            '

      # 验证产物确实是静态链接
      - name: Verify static linkage
        run: |
          file sqlite3-linux-${{ matrix.arch }}
          if file sqlite3-linux-${{ matrix.arch }} | grep -Eq "statically linked|static-pie linked"; then
            echo "Binary is statically linked"
          else
            echo "Binary is NOT statically linked"
            exit 1
          fi

      # 在目标架构 Alpine 容器内执行，非 x86_64 架构通过 QEMU 运行
      - name: Smoke test in target Alpine
        run: |
          docker run --rm \
            -v "${{ github.workspace }}:/work" \
            -w /work \
            --platform ${{ matrix.platform }} \
            alpine:latest \
            sh -c '
              set -eu
              version=$(./sqlite3-linux-${{ matrix.arch }} --version)
              printf "%s\n" "$version"
              test -n "$version"
              query=$(./sqlite3-linux-${{ matrix.arch }} ":memory:" "SELECT sqlite_version();")
              printf "SQLite query result: %s\n" "$query"
              test -n "$query"
            '

      - name: Upload artifact
        uses: actions/upload-artifact@v7.0.2
        with:
          name: sqlite3-static-${{ matrix.arch }}
          path: sqlite3-linux-${{ matrix.arch }}
          if-no-files-found: error
```

### 4.3 定时检查与 Release 发布

发布工作流位于 `.github/workflows/release-sqlite.yml`，每周一 02:17 UTC 检查 SQLite 官方稳定版，并支持手动触发。相关 Workflow 或脚本变更的 push 也会运行只读版本检查，但不会发布。手动运行默认 `dry_run: true`，只检查并报告，不构建或发布；要手动发布时需显式关闭 dry run。

检查脚本 `scripts/check_sqlite_update.py` 将官方最新版本与仓库中 `sqlite3-v<版本>` Release 比较。已有正式 Release 时结束；若发现草稿/预发布 Release，或同名 Git tag 已存在但没有 Release，则停止并要求人工处理，不自动覆盖。发现新版本时，将确切版本号传给可复用构建工作流。三种架构都完成编译、静态链接检查和目标环境运行测试后，发布工作流下载构建产物、生成 `SHA256SUMS`，并创建对应 GitHub Release。

检查和构建 job 仅有 `contents: read` 权限；只有 Release job 持有 `contents: write`。发布并发通过 concurrency group 串行化。定时 Workflow 需合并到默认分支后才会按计划运行。

### 4.4 关键设计说明

**（1）基础镜像选择**
- 所有架构统一使用官方多架构镜像 `alpine:latest`，并通过 `--platform` 选择 `linux/386`、`linux/amd64` 或 `linux/arm64`。
- `apk add --no-cache build-base` 从对应 Alpine 版本的仓库安装当前可用版本的编译工具链。
- Workflow 使用当前核对到的稳定版 Actions：`actions/checkout@v7.0.1`、`docker/setup-qemu-action@v4.4.0`、`actions/upload-artifact@v7.0.2` 和 `actions/download-artifact@v8.0.2`。SQLite amalgamation 在每次运行时从官方发布页动态发现、下载并校验。

**（2）编译命令的取舍**
- `shell.c sqlite3.c`：同时编译命令行入口和 SQLite 库。
- `-Os`：优化体积，与 SQLite 官方 CLI 预编译二进制的策略一致。
- `-static`：强制静态链接，这是产物的核心要求。
- `-DSQLITE_ENABLE_FTS5`：启用全文搜索（现代应用常用）。
- `-DSQLITE_ENABLE_JSON1`：启用 JSON 函数。
- `-DSQLITE_ENABLE_RTREE`：启用 R*Tree 索引扩展。
- `-lpthread -ldl -lm`：SQLite 所需的线程、动态加载、数学库。静态链接时这些库的静态版本由 musl 提供。

**（3）静态链接验证逻辑**
使用 `file` 命令检查输出是否包含 “statically linked” 或 “static-pie linked”。不同 Alpine/GCC 版本可能默认生成普通静态 ELF 或静态 PIE；两者都不依赖动态系统库。若都未匹配，则 Workflow 失败，防止有问题的产物被上传。

**（4）目标架构运行验证**
每个构建任务都会在对应架构的 `alpine:latest` 容器中执行生成的二进制，检查 `--version` 输出并运行 `SELECT sqlite_version();` 查询。x86 和 arm64 使用前置配置的 QEMU/binfmt 模拟器执行；x86_64 在 runner 原生架构上运行。运行测试不依赖编译容器中的构建工具链，只使用目标 Alpine 用户空间。


## 5. 执行流程与产物获取

### 5.1 触发构建

- 验证构建：手动运行构建 Workflow，或 push 修改相关 Workflow/`scripts/` 时触发；只上传 Actions Artifact。
- 发布检查：push 修改相关 Workflow/`scripts/` 时只检查版本，不发布。
- 定时发布：每周一 02:17 UTC 检查新版本。发现未发布的稳定版后，构建并验证所有架构，再发布到 GitHub Release。
- 手动发布：运行 `Check and Release SQLite`，默认 dry run；确认后关闭 dry run 才会创建 Release。
- 定时运行只在默认分支生效；发布 tag 为 `sqlite3-v<SQLite版本>`。

### 5.2 并行执行

三个矩阵任务同时运行，每个任务均在其目标架构的 `alpine:latest` 容器中编译并执行 smoke test：
- `Build sqlite3 for x86_64`：在 amd64 容器中原生编译和运行。
- `Build sqlite3 for x86`：通过 QEMU 在 386 容器中编译和运行。
- `Build sqlite3 for arm64`：通过 QEMU 在 arm64 容器中编译和运行。

### 5.3 产物下载

构建 Workflow 成功后，在 Actions 运行页面底部的 “Artifacts” 区域可下载临时验证产物：
- `sqlite3-static-x86.zip`
- `sqlite3-static-x86_64.zip`
- `sqlite3-static-arm64.zip`

定时发布成功后，同样的二进制及 `SHA256SUMS` 会作为附件出现在对应的 GitHub Release 中。


## 6. 验收标准

| 检查项 | 方法 | 预期结果 |
|---|---|---|
| 三种架构均为静态链接 | `file sqlite3-linux-*` | 输出含 `statically linked` 或 `static-pie linked` |
| 三种架构均可执行 | 在对应的 Alpine 目标架构容器中运行 `--version` 和 SQLite 查询 | 打印 SQLite 版本，并输出 `sqlite_version()` 查询结果 |
| 已发布版本跳过重复构建 | 定时运行时检查对应的 `sqlite3-v<版本>` Release | 不重新编译、不重复发布 |
| Release 发布前置条件 | 故意使一个架构的构建/运行测试失败 | 不创建 GitHub Release |
| Release 校验文件 | 检查 Release 附件中的 `SHA256SUMS` | 覆盖三个架构的二进制文件 |
| 无 glibc 依赖 | `ldd sqlite3-linux-x86_64` | 输出 `not a dynamic executable` |
| 跨环境运行 | 将 x86_64 产物拷贝到 CentOS 7 或 Debian 10 运行 | 正常执行，无 `.so` 缺失报错 |


## 7. 已知限制与注意事项

**（1）扩展加载的兼容性**
静态链接 musl 的 SQLite 在加载动态扩展（`.so` 文件）时，若扩展本身是为 glibc 编译的，可能存在兼容性问题。本方案的目标是 SQLite CLI 本身，不涉及扩展加载场景。若后续需要支持扩展，建议扩展也以 musl 为目标编译。

**（2）QEMU 模拟的性能开销**
x86 和 arm64 构建通过 QEMU 用户态模拟执行，编译速度慢于原生。对于 SQLite 这种规模（单文件 amalgamation），耗时仍在可接受范围内。若未来需要编译更大的项目，可考虑使用 GitHub Actions 的目标架构原生 runner。

**（3）SQLite 版本升级**
Workflow 每次运行时自动获取 SQLite 官方下载页列出的最新 amalgamation，并使用官方 SHA3-256 元数据校验，无需手动替换源码文件。编译选项如需调整（如增删 `SQLITE_ENABLE_*` 宏），修改 Workflow 中的 `gcc` 命令行。

**（4）滚动更新与可复现性**
按“依赖更新到最新”的要求使用 `alpine:latest` 以及 Alpine 仓库当前可用的 `build-base`。这会自动使用更新的 Alpine、musl 和编译器版本，但构建结果不再完全可复现；如需可复现构建，应将镜像和依赖版本固定到明确版本或镜像 digest。


## 8. 参考依据

- SQLite 官方推荐使用 amalgamation 源码编译，CLI 构建需要 `sqlite3.c` + `sqlite3.h` + `shell.c`。
- SQLite 官方编译选项 `-DSQLITE_ENABLE_FTS5`、`-DSQLITE_ENABLE_JSON1`、`-DSQLITE_ENABLE_RTREE` 的说明。
- 社区已有使用 Alpine + musl 静态编译 SQLite 并生成约 0.8MB 无依赖二进制的实践。
- GitHub Actions 中通过 `docker/setup-qemu-action` + 目标架构容器实现多架构构建的成熟模式。
- 使用 `file` 命令检查二进制是否静态链接的标准做法。
