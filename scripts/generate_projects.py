#!/usr/bin/env python3
"""Generate theme-aware project panels from curated project metadata."""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import textwrap
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECTS_PATH = ROOT / "projects.json"
DEFAULT_OUTPUT = ROOT / "assets"

PALETTES = {
    "dark": {
        "bg": "#050912",
        "surface": "#081020",
        "bar": "#0B1428",
        "line": "#263A69",
        "text": "#EAF2FF",
        "muted": "#91A0BE",
        "cyan": "#58D6FF",
        "purple": "#A361EB",
        "green": "#C7F36B",
        "chip": "#1C1A3B",
    },
    "light": {
        "bg": "#F4F3EC",
        "surface": "#FFFFFF",
        "bar": "#ECEDE7",
        "line": "#AEB8C6",
        "text": "#101827",
        "muted": "#556078",
        "cyan": "#006C8F",
        "purple": "#6737C7",
        "green": "#526B00",
        "chip": "#F0EBFF",
    },
}
LANGUAGE_COLORS = ["#58D6FF", "#A361EB", "#C7F36B", "#6783D2", "#91A0BE"]
GITHUB_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
GITHUB_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def is_xml_text(value: str) -> bool:
    return all(
        character in "\t\n\r"
        or 0x20 <= ord(character) <= 0xD7FF
        or 0xE000 <= ord(character) <= 0xFFFD
        or 0x10000 <= ord(character) <= 0x10FFFF
        for character in value
    )


def load_projects() -> list[dict]:
    with PROJECTS_PATH.open(encoding="utf-8") as handle:
        projects = json.load(handle)
    if not isinstance(projects, list) or not projects:
        raise ValueError("projects.json must contain a non-empty array")
    normalized = []
    for index, project in enumerate(projects):
        if not isinstance(project, dict):
            raise ValueError(f"projects.json item {index} must be an object")
        for key in ("name", "repo", "description"):
            value = project.get(key)
            if not isinstance(value, str) or not value.strip() or not is_xml_text(value):
                raise ValueError(f"projects.json item {index} field '{key}' must be a non-empty string")
        repo_parts = project["repo"].strip().split("/")
        if (
            len(repo_parts) != 2
            or not GITHUB_OWNER_RE.fullmatch(repo_parts[0])
            or not GITHUB_REPOSITORY_RE.fullmatch(repo_parts[1])
        ):
            raise ValueError(f"projects.json item {index} field 'repo' must use a valid owner/repository format")
        tags = project.get("tags")
        if not isinstance(tags, list) or not all(
            isinstance(tag, str) and tag.strip() and is_xml_text(tag) for tag in tags
        ):
            raise ValueError(f"projects.json item {index} field 'tags' must be a list of strings")
        stars = project.get("fallback_stars", 0)
        if isinstance(stars, bool) or not isinstance(stars, int) or stars < 0:
            raise ValueError(f"projects.json item {index} field 'fallback_stars' must be a non-negative integer")
        languages = project.get("fallback_languages", {})
        if not isinstance(languages, dict) or any(
            not isinstance(name, str)
            or not name.strip()
            or isinstance(size, bool)
            or not isinstance(size, (int, float))
            or not math.isfinite(size)
            or size < 0
            for name, size in languages.items()
        ):
            raise ValueError(f"projects.json item {index} field 'fallback_languages' must map names to non-negative numbers")
        normalized.append(
            {
                **project,
                "name": project["name"].strip(),
                "repo": project["repo"].strip(),
                "description": project["description"].strip(),
                "tags": [tag.strip() for tag in tags],
                "fallback_languages": {name.strip(): size for name, size in languages.items()},
            }
        )
    return normalized


def github_json(url: str, token: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "anthony-pan-profile-generator",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"GitHub API returned {type(payload).__name__}, expected object")
    return payload


def enrich(project: dict, offline: bool) -> dict:
    result = dict(project)
    result["stars"] = int(project.get("fallback_stars", 0))
    result["languages"] = dict(project.get("fallback_languages", {}))
    result["updated"] = "curated"

    if offline:
        return result

    token = os.environ.get("GITHUB_TOKEN", "")
    repo = project.get("repo", "").strip().replace("https://github.com/", "").strip("/")
    if not repo or "/" not in repo:
        return result

    try:
        info = github_json(f"https://api.github.com/repos/{repo}", token)
        languages = github_json(f"https://api.github.com/repos/{repo}/languages", token)
        if not isinstance(info, dict) or not isinstance(languages, dict):
            raise ValueError("GitHub API payload must be an object")
        result["stars"] = int(info.get("stargazers_count", result["stars"]))
        if isinstance(languages, dict) and all(
            isinstance(name, str)
            and isinstance(size, (int, float))
            and not isinstance(size, bool)
            and math.isfinite(size)
            and size >= 0
            for name, size in languages.items()
        ):
            result["languages"] = languages or result["languages"]
        pushed_at = info.get("pushed_at")
        if pushed_at:
            result["updated"] = datetime.fromisoformat(pushed_at.replace("Z", "+00:00")).date().isoformat()
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError) as error:
        print(f"warning: could not refresh {repo}: {error}")
    return result


def language_bar(languages: dict, x: int, y: int, width: int, palette: dict) -> str:
    entries = sorted(languages.items(), key=lambda item: item[1], reverse=True)[:4]
    total = sum(value for _, value in entries) or 1
    chunks = [f'<rect x="{x}" y="{y}" width="{width}" height="5" rx="2.5" fill="{palette["line"]}"/>']
    cursor = x
    for index, (_, value) in enumerate(entries):
        part = max(3, round(width * value / total))
        if index == len(entries) - 1:
            part = x + width - cursor
        chunks.append(
            f'<rect x="{cursor}" y="{y}" width="{part}" height="5" fill="{LANGUAGE_COLORS[index]}"/>'
        )
        cursor += part
    return "".join(chunks)


def card(project: dict, x: int, y: int, index: int, palette: dict) -> str:
    width, height = 548, 196
    repo = esc(project.get("repo", "unknown/repository"))
    name = esc(project.get("name", "Untitled"))
    description = textwrap.wrap(str(project.get("description", "")), width=54)[:2]
    tags = project.get("tags", [])[:3]
    language_items = sorted(project.get("languages", {}).items(), key=lambda item: item[1], reverse=True)[:2]
    language_text = " · ".join(name for name, _ in language_items) or "source pending"
    delay = 0.14 + index * 0.1
    parts = [
        f'<g class="card card-{index}">',
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="14" fill="{palette["surface"]}" stroke="{palette["line"]}"/>',
        f'<rect x="{x}" y="{y}" width="{width}" height="34" rx="14" fill="{palette["bar"]}"/>',
        f'<rect x="{x}" y="{y + 18}" width="{width}" height="16" fill="{palette["bar"]}"/>',
        f'<line x1="{x}" y1="{y + 34}" x2="{x + width}" y2="{y + 34}" stroke="{palette["line"]}"/>',
        f'<circle cx="{x + 20}" cy="{y + 17}" r="4" fill="{palette["purple"]}"/>',
        f'<circle cx="{x + 34}" cy="{y + 17}" r="4" fill="{palette["cyan"]}"/>',
        f'<text x="{x + 52}" y="{y + 21}" class="mono meta" fill="{palette["muted"]}">{repo}</text>',
        f'<circle cx="{x + width - 19}" cy="{y + 17}" r="4" fill="{palette["green"]}" class="pulse"/>',
        f'<text x="{x + 20}" y="{y + 70}" class="mono" font-size="18" font-weight="700" fill="{palette["text"]}">{name}</text>',
    ]
    for line_index, line in enumerate(description):
        parts.append(
            f'<text x="{x + 20}" y="{y + 91 + line_index * 15}" class="mono desc" fill="{palette["muted"]}">{esc(line)}</text>'
        )

    chip_x = x + 20
    for tag in tags:
        label = str(tag)
        chip_width = max(50, min(122, 17 + len(label) * 6.6))
        parts.extend(
            [
                f'<rect x="{chip_x}" y="{y + 125}" width="{chip_width:.0f}" height="20" rx="10" fill="{palette["chip"]}" stroke="{palette["line"]}"/>',
                f'<text x="{chip_x + chip_width / 2:.0f}" y="{y + 139}" class="mono chip" fill="{palette["purple"]}" text-anchor="middle">{esc(label)}</text>',
            ]
        )
        chip_x += chip_width + 7

    parts.extend(
        [
            language_bar(project.get("languages", {}), x + 20, y + 164, width - 40, palette),
            f'<text x="{x + 20}" y="{y + 185}" class="mono meta" fill="{palette["muted"]}">★ {project.get("stars", 0)}  ·  {esc(language_text)}  ·  refreshed {esc(project.get("updated", "curated"))}</text>',
            f'<animate attributeName="opacity" from="0" to="1" dur=".45s" begin="{delay}s" fill="freeze"/>',
            f'<animateTransform attributeName="transform" type="translate" from="0 8" to="0 0" dur=".45s" begin="{delay}s" fill="freeze"/>',
            "</g>",
        ]
    )
    return "".join(parts)


def render_card(project: dict, theme: str) -> str:
    """Render one self-contained project card for an outer README link."""
    palette = PALETTES[theme]
    name = esc(project["name"])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="548" height="196" viewBox="0 0 548 196" role="img" aria-labelledby="title desc">
  <title id="title">Open {name} on GitHub</title>
  <desc id="desc">A terminal-style project card that links to the {name} repository.</desc>
  <style>
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }}
    .meta {{ font-size: 11px; }}
    .desc {{ font-size: 11px; }}
    .chip {{ font-size: 9px; }}
    .pulse {{ animation: pulse 1.8s ease-in-out infinite; }}
    @keyframes pulse {{ 50% {{ opacity: .28; }} }}
    @media (prefers-reduced-motion: reduce) {{ .pulse {{ animation: none; }} }}
  </style>
  {card(project, 0, 0, 0, palette)}
</svg>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Use only curated fallback metadata")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    projects = [enrich(project, args.offline) for project in load_projects()]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[Path, str] = {}
    seen_slugs: set[str] = set()
    for project in projects:
        slug = re.sub(r"[^a-z0-9]+", "-", project["name"].lower()).strip("-")
        if not slug or slug in seen_slugs:
            raise ValueError(f"project name produces a duplicate or empty asset slug: {project['name']}")
        seen_slugs.add(slug)
        for theme in PALETTES:
            output = args.output_dir / f"project-{slug}-{theme}.svg"
            outputs[output] = render_card(project, theme)

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

    for stale_output in args.output_dir.glob("project-*.svg"):
        if stale_output not in outputs:
            stale_output.unlink()
            print(f"removed {stale_output}")


if __name__ == "__main__":
    main()
