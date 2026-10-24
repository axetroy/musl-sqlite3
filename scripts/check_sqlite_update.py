import json
import os
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request

from download_sqlite import get_latest_amalgamation
from http_utils import urlopen_with_retry


GITHUB_API = "https://api.github.com"


def github_get(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "musl-sqlite3-release-check",
    }
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(f"{GITHUB_API}{path}", headers=headers)
    try:
        with urlopen_with_retry(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise


def set_outputs(values):
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        raise SystemExit("GITHUB_OUTPUT is not available")

    with open(output_file, "a", encoding="utf-8") as output:
        for name, value in values.items():
            output.write(f"{name}={value}\n")


def main():
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not repository or "/" not in repository:
        raise SystemExit("GITHUB_REPOSITORY is not set to owner/repository")

    release = get_latest_amalgamation()
    version = release["VERSION"]
    tag = f"sqlite3-v{version}"
    encoded_tag = quote(tag, safe="")
    existing_release = github_get(
        f"/repos/{repository}/releases/tags/{encoded_tag}"
    )
    if existing_release is not None:
        if existing_release.get("draft") or existing_release.get("prerelease"):
            raise SystemExit(
                f"Release {tag} is a draft or prerelease; resolve it manually"
            )
        print(f"SQLite {version} is already published as {tag}")
        set_outputs(
            {
                "sqlite_version": version,
                "release_tag": tag,
                "should_release": "false",
            }
        )
        return

    existing_tag = github_get(
        f"/repos/{repository}/git/ref/tags/{encoded_tag}"
    )
    if existing_tag is not None:
        raise SystemExit(
            f"Git tag {tag} exists without a GitHub Release; resolve it manually"
        )

    print(f"SQLite {version} is not published; a release build is needed")
    set_outputs(
        {
            "sqlite_version": version,
            "release_tag": tag,
            "should_release": "true",
        }
    )


if __name__ == "__main__":
    main()
