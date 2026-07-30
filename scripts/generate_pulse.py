#!/usr/bin/env python3
"""Generate a self-hosted GitHub account snapshot for the profile README."""

from __future__ import annotations

import argparse
import html
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "assets"
USERNAME = "Anthony-Pan"

PALETTES = {
    "dark": {
        "bg": "#050912", "surface": "#081020", "bar": "#0B1428", "line": "#263A69",
        "text": "#EAF2FF", "muted": "#91A0BE", "cyan": "#58D6FF", "purple": "#A361EB", "green": "#C7F36B",
    },
    "light": {
        "bg": "#F4F3EC", "surface": "#FFFFFF", "bar": "#ECEDE7", "line": "#AEB8C6",
        "text": "#101827", "muted": "#556078", "cyan": "#006C8F", "purple": "#6737C7", "green": "#526B00",
    },
}


def github_json(url: str, token: str) -> object:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "anthony-pan-profile-generator"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=12) as response:
        return json.load(response)


def github_repositories(token: str) -> list[dict]:
    repositories: list[dict] = []
    page = 1
    while True:
        payload = github_json(
            f"https://api.github.com/users/{USERNAME}/repos?per_page=100&type=owner&sort=updated&page={page}", token
        )
        if not isinstance(payload, list):
            raise ValueError("unexpected GitHub repositories response")
        repositories.extend(repository for repository in payload if isinstance(repository, dict))
        if len(payload) < 100:
            return repositories
        page += 1


def esc(value: object) -> str:
    raw = str(value)
    if not all(
        character in "\t\n\r"
        or 0x20 <= ord(character) <= 0xD7FF
        or 0xE000 <= ord(character) <= 0xFFFD
        or 0x10000 <= ord(character) <= 0x10FFFF
        for character in raw
    ):
        raise ValueError("GitHub API returned XML-incompatible text")
    return html.escape(raw)


def snapshot(offline: bool) -> dict[str, object]:
    data: dict[str, object] = {"repos": 0, "stars": 0, "followers": 0, "following": 0, "languages": []}
    if offline:
        return data
    try:
        token = os.environ.get("GITHUB_TOKEN", "")
        user = github_json(f"https://api.github.com/users/{USERNAME}", token)
        repos = github_repositories(token)
        if not isinstance(user, dict):
            raise ValueError("unexpected GitHub API response")
        public_repos = user.get("public_repos", 0)
        followers = user.get("followers", 0)
        following = user.get("following", 0)
        valid_repos = [repo for repo in repos if isinstance(repo, dict)]
        languages: dict[str, int] = {}
        stars = 0
        for repo in valid_repos:
            language = repo.get("language")
            if isinstance(language, str) and language:
                languages[language] = languages.get(language, 0) + 1
            repo_stars = repo.get("stargazers_count", 0)
            if isinstance(repo_stars, int) and not isinstance(repo_stars, bool) and repo_stars >= 0:
                stars += repo_stars
        data.update(
            repos=int(public_repos) if isinstance(public_repos, int) else len(valid_repos),
            stars=stars,
            followers=int(followers) if isinstance(followers, int) else 0,
            following=int(following) if isinstance(following, int) else 0,
            languages=sorted(languages.items(), key=lambda item: (-item[1], item[0]))[:5],
        )
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, TypeError) as error:
        raise RuntimeError(f"could not refresh GitHub account snapshot: {error}") from error
    return data


def metric(label: str, value: object, x: int, palette: dict[str, str], accent: str) -> str:
    return f'''<g>
  <rect x="{x}" y="70" width="256" height="100" rx="14" fill="{palette["surface"]}" stroke="{palette["line"]}"/>
  <circle cx="{x + 22}" cy="92" r="5" fill="{accent}"/>
  <text x="{x + 38}" y="97" class="mono label" fill="{palette["muted"]}">{esc(label)}</text>
  <text x="{x + 20}" y="142" class="mono value" fill="{palette["text"]}">{esc(value)}</text>
</g>'''


def render(data: dict[str, object], theme: str) -> str:
    palette = PALETTES[theme]
    language_items = data["languages"] if isinstance(data["languages"], list) else []
    language_text = "  ·  ".join(f"{name} {count}" for name, count in language_items) or "Languages sync after the first scheduled refresh"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="230" viewBox="0 0 1180 230" role="img" aria-labelledby="title desc">
  <title id="title">Anthony Pan's GitHub snapshot</title>
  <desc id="desc">Public repositories, stars, followers, following, and primary repository languages.</desc>
  <style>
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }}
    .label {{ font-size: 12px; letter-spacing: 1.2px; }}
    .value {{ font-size: 32px; font-weight: 700; }}
    .meta {{ font-size: 12px; }}
  </style>
  <rect width="1180" height="230" fill="{palette["bg"]}"/>
  <rect x="32" y="20" width="1116" height="190" rx="16" fill="{palette["surface"]}" stroke="{palette["line"]}"/>
  <text x="56" y="49" class="mono" font-size="14" letter-spacing="2.6" fill="{palette["cyan"]}">PUBLIC.GITHUB_PULSE</text>
  <circle cx="1119" cy="43" r="5" fill="{palette["green"]}"/>
  <line x1="56" y1="59" x2="1124" y2="59" stroke="{palette["line"]}"/>
  {metric("PUBLIC REPOS", data["repos"], 56, palette, palette["cyan"])}
  {metric("TOTAL STARS", data["stars"], 326, palette, palette["purple"])}
  {metric("FOLLOWERS", data["followers"], 596, palette, palette["green"])}
  {metric("FOLLOWING", data["following"], 866, palette, palette["cyan"])}
  <text x="56" y="193" class="mono meta" fill="{palette["muted"]}">LANGUAGES  /  {esc(language_text)}</text>
</svg>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Use deterministic fallback values")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data = snapshot(args.offline)
    for theme in PALETTES:
        output = args.output_dir / f"pulse-{theme}.svg"
        output.write_text(render(data, theme), encoding="utf-8")
        print(f"wrote {output}")


if __name__ == "__main__":
    main()
