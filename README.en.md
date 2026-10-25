# sqlite3-static-link-prebuilt

[简体中文](README.md) | English

Standalone SQLite command-line binaries for Linux, macOS, and Windows.

| Platform | Architectures | Dependencies |
| --- | --- | --- |
| Linux | x86, x86_64, ARM (ARMv7), arm64, mips64el, loong64 | Statically linked with musl |
| macOS | universal2 (x86_64, arm64) | SQLite is bundled; depends on macOS system libraries |
| Windows | x86, x86_64, arm64 | MSVC runtime is statically linked (`/MT`); depends on Windows system DLLs |

## How this differs from SQLite's official prebuilt binaries

The [official SQLite download page](https://sqlite.org/download.html) offers prebuilt packages published by the SQLite project. This repository does not mirror those binaries. It downloads the official SQLite amalgamation source, verifies its published file size and SHA3-256 hash, then builds and tests binaries using this project's configuration.

| Aspect | SQLite official prebuilt packages | This project |
| --- | --- | --- |
| Linux architectures and linking | Packages are provided for the systems and architectures listed on the official download page; the current Linux CLI package targets x64 | Provides x86, x86_64, ARMv7, arm64, mips64el, and loong64; all are statically linked with musl and do not depend on glibc |
| Included tools | In addition to `sqlite3`, the official Linux/macOS CLI packages include `sqldiff`, `sqlite3_analyzer`, and `sqlite3_rsync` | Provides only the `sqlite3` command-line shell |
| Build configuration | Built and published by the SQLite project | Built by this project's CI from official source with FTS5, JSON1, and R*Tree enabled |
| Other platforms | See the official page for its current platform and architecture list | Provides macOS universal2 and Windows x86, x86_64, and arm64; these still depend on system libraries or DLLs provided by their operating systems |

Use the [official prebuilt packages](https://sqlite.org/download.html) if you need SQLite's complete bundled toolset. Use this project if you need statically linked Linux/musl binaries or architectures not listed in the official Linux packages. Build options may differ, so enabled features and runtime dependencies are not necessarily identical.

This project's release binaries and `SHA256SUMS` are available from [GitHub Releases](https://github.com/axetroy/sqlite3-static-link-prebuilt/releases).

## Build and verify manually

You can build and verify all supported platforms without waiting for the scheduled release check or creating a release:

1. Open the repository's [Actions](https://github.com/axetroy/sqlite3-static-link-prebuilt/actions) page and select **SQLite CI**.
2. Click **Run workflow** and choose the branch to build.
3. Leave `sqlite_version` blank to use the latest stable SQLite release, or enter a specific version.
4. Click **Run workflow**. When it succeeds, download the build artifacts from the **Artifacts** section at the bottom of the workflow run page.

This workflow builds and smoke-tests Linux, macOS, and Windows binaries. It uploads Actions artifacts only and does not publish a GitHub Release.

## Check for updates and publish manually

To check whether SQLite has a new stable release and publish it if needed:

1. On the repository's [Actions](https://github.com/axetroy/sqlite3-static-link-prebuilt/actions) page, select **SQLite Release** and click **Run workflow**.
2. Choose the repository's default branch (currently `main`).
3. Keep `dry_run` enabled for an initial check. This only checks the version; it does not build or publish.
4. To publish, run the workflow again with `dry_run` disabled.

A real run checks the latest stable SQLite version. If that version has not already been released, the workflow builds and verifies all platforms, generates `SHA256SUMS`, and creates a GitHub Release. If the latest version already has a release, the workflow skips the build and does not overwrite it. Manual publishing must be run from the default branch.

**Note:** `dry_run` is enabled by default. To publish, explicitly disable it; merely clicking **Run workflow** will not publish a release.

## Automated releases

The **SQLite Release** workflow checks for a new stable SQLite release every Monday at 02:17 UTC (10:17 China Standard Time). If a new version is available, it builds, verifies, and publishes it. Pushes that only change related workflow files or scripts perform a version check and do not create a release.

For more architecture, build, and release details, see [design.md](./design.md).

## License

This project is licensed under the [MIT License](./LICENSE).
