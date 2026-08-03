#!/usr/bin/env python3
"""Generate an AltStore/SideStore/LiveContainer source for Tsumiru releases."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

UPSTREAM_REPO = "Suwayomi/Suwayomi-Tsumiru"
RELEASES_API = f"https://api.github.com/repos/{UPSTREAM_REPO}/releases?per_page=50"
RAW_PUBSPEC = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{{tag}}/pubspec.yaml"
OUTPUT = Path(__file__).resolve().parents[1] / "source.json"
SOURCE_URL = "https://raw.githubusercontent.com/DeQxJ00/CustomSourceJson/main/source.json"
REPO_URL = "https://github.com/DeQxJ00/CustomSourceJson"
ICON_URL = (
    "https://raw.githubusercontent.com/Suwayomi/Suwayomi-Tsumiru/main/"
    "ios/Runner/Assets.xcassets/AppIcon.appiconset/Icon-App-1024x1024@1x.png"
)
BUNDLE_ID = "com.suwayomi.tachideskSorayomi"


def request_bytes(url: str, *, accept: str = "application/vnd.github+json") -> bytes:
    headers = {
        "Accept": accept,
        "User-Agent": "DeQxJ00-CustomSourceJson",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token and urllib.parse.urlparse(url).hostname == "api.github.com":
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unable to fetch {url}: {exc}") from exc


def request_json(url: str) -> Any:
    return json.loads(request_bytes(url).decode("utf-8"))


def pubspec_version(tag: str) -> tuple[str, str]:
    url = RAW_PUBSPEC.format(tag=urllib.parse.quote(tag, safe=""))
    text = request_bytes(url, accept="text/plain").decode("utf-8", "replace")
    match = re.search(r"^version:\s*([^+\s]+)\+([^\s#]+)", text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"No version/build number in {tag}/pubspec.yaml")
    return match.group(1), match.group(2)


def clean_notes(body: str | None, version: str) -> str:
    if not body:
        return f"Tsumiru {version} release."

    body = body.replace("\r\n", "\n").strip()
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)

    kept: list[str] = []
    for line in body.splitlines():
        if re.match(r"^#{1,3}\s+(Install|Installation|Contributors)\b", line, re.I):
            break
        kept.append(line.rstrip())

    notes = "\n".join(kept).strip()
    notes = re.sub(r"\n{3,}", "\n\n", notes)
    return notes[:6000] or f"Tsumiru {version} release."


def make_versions(releases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    versions: list[dict[str, Any]] = []

    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue

        ipa = next(
            (
                asset
                for asset in release.get("assets", [])
                if str(asset.get("name", "")).lower().endswith("-ios.ipa")
            ),
            None,
        )
        if not ipa:
            continue

        tag = str(release.get("tag_name", "")).strip()
        if not tag:
            continue

        try:
            version, build = pubspec_version(tag)
        except RuntimeError as exc:
            print(f"warning: skipping {tag}: {exc}", file=sys.stderr)
            continue

        versions.append(
            {
                "version": version,
                "buildVersion": build,
                "date": release.get("published_at") or release.get("created_at"),
                "localizedDescription": clean_notes(release.get("body"), version),
                "downloadURL": ipa["browser_download_url"],
                "size": int(ipa.get("size", 0)),
                "minOSVersion": "14.0",
            }
        )

    versions.sort(key=lambda item: item.get("date") or "", reverse=True)
    return versions


def main() -> int:
    releases = request_json(RELEASES_API)
    if not isinstance(releases, list):
        raise RuntimeError("GitHub Releases API returned an unexpected response")

    versions = make_versions(releases)
    if not versions:
        raise RuntimeError("No published Tsumiru iOS IPA releases found")

    source = {
        "name": "自用源 Custom Source",
        "subtitle": "适用于 LiveContainer、AltStore 与 SideStore 的自定义源",
        "description": "自动跟随上游 GitHub Release 更新，目前收录 Tsumiru。",
        "identifier": "com.custom-source-json",
        "sourceURL": SOURCE_URL,
        "iconURL": ICON_URL,
        "website": REPO_URL,
        "tintColor": "#6750A4",
        "featuredApps": [BUNDLE_ID],
        "apps": [
            {
                "name": "Tsumiru",
                "bundleIdentifier": BUNDLE_ID,
                "developerName": "Suwayomi",
                "subtitle": "Suwayomi 漫画与条漫客户端",
                "localizedDescription": (
                    "Tsumiru 是 Suwayomi-Server 的原生漫画、Manhwa 与条漫阅读器，"
                    "支持离线下载、跨章节连续滚动和阅读进度同步。"
                ),
                "iconURL": ICON_URL,
                "tintColor": "#6750A4",
                "category": "entertainment",
                "appPermissions": {
                    "entitlements": [],
                    "privacy": {
                        "NSPhotoLibraryUsageDescription": "Save manga pages to your photo library.",
                        "NSPhotoLibraryAddUsageDescription": "Save manga pages to your photo library.",
                    },
                },
                "versions": versions,
            }
        ],
        "news": [],
    }

    OUTPUT.write_text(
        json.dumps(source, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT} with {len(versions)} version(s)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
