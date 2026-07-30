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


def snapshot(offline: bool) -> dict[str, int]:
    data = {"repos": 0, "stars": 0, "followers": 0, "following": 0}
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
        stars = 0
        for repo in valid_repos:
            repo_stars = repo.get("stargazers_count", 0)
            if isinstance(repo_stars, int) and not isinstance(repo_stars, bool) and repo_stars >= 0:
                stars += repo_stars
        data.update(
            repos=int(public_repos) if isinstance(public_repos, int) else len(valid_repos),
            stars=stars,
            followers=int(followers) if isinstance(followers, int) else 0,
            following=int(following) if isinstance(following, int) else 0,
        )
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, TypeError) as error:
        raise RuntimeError(f"could not refresh GitHub account snapshot: {error}") from error
    return data


def render_metric(label: str, value: int, theme: str, accent: str) -> str:
    palette = PALETTES[theme]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="134" viewBox="0 0 256 134" role="img" aria-labelledby="title desc">
  <title id="title">{esc(label)}: {esc(value)}</title>
  <desc id="desc">Open Anthony Pan's GitHub {esc(label).lower()} page.</desc>
  <style>
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }}
    .label {{ font-size: 12px; letter-spacing: 1.2px; }}
    .value {{ font-size: 32px; font-weight: 700; }}
  </style>
  <rect x="1" y="1" width="254" height="132" rx="14" fill="{palette["surface"]}" stroke="{palette["line"]}"/>
  <circle cx="23" cy="29" r="5" fill="{accent}"/>
  <text x="39" y="34" class="mono label" fill="{palette["muted"]}">{esc(label)}</text>
  <text x="20" y="83" class="mono value" fill="{palette["text"]}">{esc(value)}</text>
  <line x1="20" y1="102" x2="236" y2="102" stroke="{palette["line"]}"/>
  <text x="20" y="119" class="mono" font-size="10" letter-spacing="1" fill="{accent}">OPEN ON GITHUB  ↗</text>
</svg>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Use deterministic fallback values")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data = snapshot(args.offline)
    metrics = (
        ("repositories", "PUBLIC REPOS", "repos", "cyan"),
        ("stars", "TOTAL STARS", "stars", "purple"),
        ("followers", "FOLLOWERS", "followers", "green"),
        ("following", "FOLLOWING", "following", "cyan"),
    )
    outputs: dict[Path, str] = {}
    for slug, label, key, accent_name in metrics:
        for theme, palette in PALETTES.items():
            output = args.output_dir / f"pulse-{slug}-{theme}.svg"
            outputs[output] = render_metric(label, data[key], theme, palette[accent_name])

    temporary_outputs: list[tuple[Path, Path]] = []
    try:
        for output, content in outputs.items():
            temporary = output.with_name(f".{output.name}.tmp")
            temporary.write_text(content, encoding="utf-8")
            temporary_outputs.append((temporary, output))
        for temporary, output in temporary_outputs:
            temporary.replace(output)
            print(f"wrote {output}")
    except OSError:
        for temporary, _ in temporary_outputs:
            temporary.unlink(missing_ok=True)
        raise

    for stale_output in args.output_dir.glob("pulse-*.svg"):
        if stale_output not in outputs:
            stale_output.unlink()
            print(f"removed {stale_output}")


if __name__ == "__main__":
    main()
