# 技术方案：GitHub Actions 多架构 Alpine + musl 静态编译 SQLite3

## 1. 背景与目标

SQLite 官方预编译二进制依赖较高版本的 glibc，在低版本 Linux 环境（如 CentOS 7、旧版 Debian）中无法直接运行。在 glibc 环境下做“伪静态”编译并不可靠，部分符号仍可能动态依赖 NSS 等库。

**目标**：通过 GitHub Actions，在 Alpine Linux（musl libc）环境中为 `x86`（32 位）、`x86_64` 和 `arm64` 架构分别编译出**完全静态链接**的 SQLite3 命令行工具，产物可在任意 Linux 发行版上直接运行，不依赖目标系统的 glibc 或 musl 版本。

**预期产物**：
- `sqlite3-linux-x86`（i386 静态二进制）
- `sqlite3-linux-x86_64`（x86_64 静态二进制）
- `sqlite3-linux-arm64`（aarch64 静态二进制）

三者均为 ELF 静态链接可执行文件，`file` 命令输出应显示 “statically linked”。


## 2. 技术路线选择

采用 **QEMU 模拟 + 目标架构 Alpine 容器内原生编译** 的方式，而非配置交叉编译工具链。

理由：
- 交叉编译 musl 工具链（如 `aarch64-linux-musl-gcc`）配置复杂，容易出现链接错误。
- 在 QEMU 模拟的目标架构 Alpine 容器中，直接使用该架构的原生 `gcc`（即 musl-gcc），编译过程与在真实 arm64 机器上一致，成功率更高。
- GitHub Actions 社区已有成熟模式：使用 `docker/setup-qemu-action` 启用模拟，再通过 `docker run` 运行目标架构的 Alpine 镜像。


## 3. 前置条件

### 3.1 仓库文件要求

仓库根目录（或指定路径）下需包含 SQLite amalgamation 源码包中的以下文件：
- `sqlite3.c`
- `sqlite3.h`
- `shell.c`

**说明**：SQLite 官方推荐使用 amalgamation（合并源码）进行编译，因为所有代码生成和转换步骤已完成，编译最简单，且编译器能进行更激进的优化（性能提升 5%~10%）。从 SQLite 官网下载 `sqlite-amalgamation-*.zip` 解压即可获得上述三个文件。

### 3.2 GitHub Actions 权限

Workflow 需要能够使用 `actions/upload-artifact` 上传产物，默认权限即可满足。


## 4. Workflow 文件设计

### 4.1 文件路径与触发条件

文件路径：`.github/workflows/build-sqlite-musl.yml`

触发条件：
- `workflow_dispatch`（手动触发，便于调试）
- `push` 到 tags（如 `v*`，用于版本发布时自动构建）

### 4.2 完整 Workflow 内容

```yaml
name: Build Static SQLite3 (Alpine + musl)

on:
  workflow_dispatch:
  push:
    tags:
      - 'v*'

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

      - name: Verify amalgamation sources
        run: |
          for source in shell.c sqlite3.c sqlite3.h; do
            if [ ! -f "$source" ]; then
              echo "::error::Required SQLite amalgamation source is missing: $source"
              exit 1
            fi
          done

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
          if file sqlite3-linux-${{ matrix.arch }} | grep -q "statically linked"; then
            echo "✓ Binary is statically linked"
          else
            echo "✗ Binary is NOT statically linked"
            exit 1
          fi

      # 对于 x86_64，可直接在 runner 上运行版本检查
      - name: Smoke test (x86_64 only)
        if: matrix.arch == 'x86_64'
        run: |
          ./sqlite3-linux-x86_64 --version

      - name: Upload artifact
        uses: actions/upload-artifact@v7.0.2
        with:
          name: sqlite3-static-${{ matrix.arch }}
          path: sqlite3-linux-${{ matrix.arch }}
          if-no-files-found: error
```

### 4.3 关键设计说明

**（1）基础镜像选择**
- 所有架构统一使用官方多架构镜像 `alpine:latest`，并通过 `--platform` 选择 `linux/386`、`linux/amd64` 或 `linux/arm64`。
- `apk add --no-cache build-base` 从对应 Alpine 版本的仓库安装当前可用版本的编译工具链。
- Workflow 使用当前核对到的最新稳定版 Actions：`actions/checkout@v7.0.1`、`docker/setup-qemu-action@v4.4.0` 和 `actions/upload-artifact@v7.0.2`。

**（2）编译命令的取舍**
- `shell.c sqlite3.c`：同时编译命令行入口和 SQLite 库。
- `-Os`：优化体积，与 SQLite 官方 CLI 预编译二进制的策略一致。
- `-static`：强制静态链接，这是产物的核心要求。
- `-DSQLITE_ENABLE_FTS5`：启用全文搜索（现代应用常用）。
- `-DSQLITE_ENABLE_JSON1`：启用 JSON 函数。
- `-DSQLITE_ENABLE_RTREE`：启用 R*Tree 索引扩展。
- `-lpthread -ldl -lm`：SQLite 所需的线程、动态加载、数学库。静态链接时这些库的静态版本由 musl 提供。

**（3）静态链接验证逻辑**
使用 `file` 命令检查输出是否包含 “statically linked”。若不含，则 Workflow 失败，防止有问题的产物被上传。

**（4）非 x86_64 架构的验证策略**
GitHub 的 `ubuntu-latest` runner 是 x86_64，无法直接执行 32 位 x86 或 arm64 二进制。因此 smoke test 仅在 `x86_64` 上执行。x86 和 arm64 产物的正确性由编译成功 + `file` 静态链接检查来保证。如需运行级验证，可额外使用 QEMU 执行目标二进制，但会增加复杂度和时间。


## 5. 执行流程与产物获取

### 5.1 触发构建

- 手动：在 GitHub 仓库 Actions 页面选择该 Workflow，点击 “Run workflow”。
- 自动：推送 tag（如 `git tag v1.0.0 && git push origin v1.0.0`）。

### 5.2 并行执行

三个矩阵任务同时运行：
- `Build sqlite3 for x86_64`：在 `alpine:latest` 的 amd64 容器中编译。
- `Build sqlite3 for x86`：QEMU 模拟下在 `alpine:latest` 的 386 容器中编译。
- `Build sqlite3 for arm64`：QEMU 模拟下在 `alpine:latest` 的 arm64 容器中编译。

### 5.3 产物下载

Workflow 成功后，在 Actions 运行页面底部的 “Artifacts” 区域可下载：
- `sqlite3-static-x86.zip`
- `sqlite3-static-x86_64.zip`
- `sqlite3-static-arm64.zip`


## 6. 验收标准

| 检查项 | 方法 | 预期结果 |
|---|---|---|
| x86 为静态链接 | `file sqlite3-linux-x86` | 输出含 `statically linked` |
| x86_64 为静态链接 | `file sqlite3-linux-x86_64` | 输出含 `statically linked` |
| arm64 为静态链接 | `file sqlite3-linux-arm64` | 输出含 `statically linked` |
| x86_64 可执行 | `./sqlite3-linux-x86_64 --version` | 打印 SQLite 版本号 |
| 无 glibc 依赖 | `ldd sqlite3-linux-x86_64` | 输出 `not a dynamic executable` |
| 跨环境运行 | 将 x86_64 产物拷贝到 CentOS 7 或 Debian 10 运行 | 正常执行，无 `.so` 缺失报错 |


## 7. 已知限制与注意事项

**（1）扩展加载的兼容性**
静态链接 musl 的 SQLite 在加载动态扩展（`.so` 文件）时，若扩展本身是为 glibc 编译的，可能存在兼容性问题。本方案的目标是 SQLite CLI 本身，不涉及扩展加载场景。若后续需要支持扩展，建议扩展也以 musl 为目标编译。

**（2）QEMU 模拟的性能开销**
x86 和 arm64 构建通过 QEMU 用户态模拟执行，编译速度慢于原生。对于 SQLite 这种规模（单文件 amalgamation），耗时仍在可接受范围内。若未来需要编译更大的项目，可考虑使用 GitHub Actions 的目标架构原生 runner。

**（3）SQLite 版本升级**
当需要升级 SQLite 版本时，只需替换仓库中的 `sqlite3.c`、`sqlite3.h`、`shell.c` 三个文件，重新触发 Workflow 即可。编译选项如需调整（如增删 `SQLITE_ENABLE_*` 宏），修改 Workflow 中的 `gcc` 命令行。

**（4）滚动更新与可复现性**
按“依赖更新到最新”的要求使用 `alpine:latest` 以及 Alpine 仓库当前可用的 `build-base`。这会自动使用更新的 Alpine、musl 和编译器版本，但构建结果不再完全可复现；如需可复现构建，应将镜像和依赖版本固定到明确版本或镜像 digest。


## 8. 参考依据

- SQLite 官方推荐使用 amalgamation 源码编译，CLI 构建需要 `sqlite3.c` + `sqlite3.h` + `shell.c`。
- SQLite 官方编译选项 `-DSQLITE_ENABLE_FTS5`、`-DSQLITE_ENABLE_JSON1`、`-DSQLITE_ENABLE_RTREE` 的说明。
- 社区已有使用 Alpine + musl 静态编译 SQLite 并生成约 0.8MB 无依赖二进制的实践。
- GitHub Actions 中通过 `docker/setup-qemu-action` + 目标架构容器实现多架构构建的成熟模式。
- 使用 `file` 命令检查二进制是否静态链接的标准做法。
