import argparse
import csv
import hashlib
import io
import re
import shutil
import urllib.request
import zipfile


DOWNLOAD_PAGE = "https://www.sqlite.org/download.html"
REQUIRED_FILES = ("shell.c", "sqlite3.c", "sqlite3.h")


def get_latest_amalgamation(version=None):
    request = urllib.request.Request(
        DOWNLOAD_PAGE,
        headers={"User-Agent": "sqlite-musl-build/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        page = response.read().decode("utf-8")

    metadata = re.search(
        r"<!-- Download product data for scripts to read\s*(.*?)\s*-->",
        page,
        re.DOTALL,
    )
    if metadata is None:
        raise SystemExit("SQLite download metadata was not found")

    rows = csv.DictReader(io.StringIO(metadata.group(1)))
    releases = [
        row for row in rows
        if re.fullmatch(
            r"\d{4}/sqlite-amalgamation-\d+\.zip",
            row.get("RELATIVE-URL", ""),
        )
    ]
    if not releases:
        raise SystemExit("No SQLite amalgamation archive was listed")

    if version is not None:
        for release in releases:
            if release["VERSION"] == version:
                return release
        raise SystemExit(f"SQLite amalgamation version {version} was not listed")

    return max(
        releases,
        key=lambda row: int(
            re.search(r"-(\d+)\.zip$", row["RELATIVE-URL"]).group(1)
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="SQLite release version to download")
    args = parser.parse_args()

    release = get_latest_amalgamation(args.version)
    archive_url = "https://www.sqlite.org/" + release["RELATIVE-URL"]
    with urllib.request.urlopen(archive_url, timeout=60) as response:
        archive_data = response.read()

    if len(archive_data) != int(release["SIZE-IN-BYTES"]):
        raise SystemExit("SQLite archive size does not match published metadata")
    archive_hash = hashlib.sha3_256(archive_data).hexdigest()
    if archive_hash.lower() != release["SHA3-HASH"].lower():
        raise SystemExit("SQLite archive SHA3-256 does not match published metadata")

    archive_name = release["RELATIVE-URL"].rsplit("/", 1)[-1]
    archive_root = archive_name.removesuffix(".zip")
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        members = set(archive.namelist())
        for filename in REQUIRED_FILES:
            member = f"{archive_root}/{filename}"
            if member not in members:
                raise SystemExit(f"SQLite archive is missing {filename}")
            with archive.open(member) as source, open(filename, "wb") as target:
                shutil.copyfileobj(source, target)

    print(f"Downloaded and verified SQLite {release['VERSION']} ({archive_name})")


if __name__ == "__main__":
    main()
