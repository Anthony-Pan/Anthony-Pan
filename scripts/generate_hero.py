#!/usr/bin/env python3
"""Generate self-contained, GitHub-safe light and dark profile hero SVGs."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "profile.json"
PORTRAIT_PATH = ROOT / "assets" / "profile.png"
ASSET_DIR = ROOT / "assets"

PALETTES = {
    "dark": {
        "bg": "#050912",
        "surface": "#081020",
        "surface_2": "#0B1428",
        "line": "#263A69",
        "text": "#EAF2FF",
        "muted": "#91A0BE",
        "cyan": "#58D6FF",
        "purple": "#A361EB",
        "green": "#C7F36B",
        "scan": "#58D6FF",
        "grid": "#14213D",
    },
    "light": {
        "bg": "#F4F3EC",
        "surface": "#ECEDE7",
        "surface_2": "#E4E8E7",
        "line": "#AEB8C6",
        "text": "#101827",
        "muted": "#556078",
        "cyan": "#006C8F",
        "purple": "#6737C7",
        "green": "#526B00",
        "scan": "#006C8F",
        "grid": "#D9DEE2",
    },
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def is_xml_text(value: str) -> bool:
    return all(
        character in "\t\n\r"
        or (ord(character) >= 0x20 and not 0xD800 <= ord(character) <= 0xDFFF)
        for character in value
    )


def cut_panel(x: int, y: int, width: int, height: int, cut: int = 16) -> str:
    right = x + width
    bottom = y + height
    return (
        f"M{x + cut} {y} H{right - cut} L{right} {y + cut} "
        f"V{bottom - cut} L{right - cut} {bottom} H{x + cut} "
        f"L{x} {bottom - cut} V{y + cut} Z"
    )


def load_profile() -> dict:
    with PROFILE_PATH.open(encoding="utf-8") as handle:
        profile = json.load(handle)
    if not isinstance(profile, dict):
        raise ValueError("profile.json must contain an object")
    required = {
        "name",
        "username",
        "role",
        "studio",
        "focus",
        "building",
        "public_projects",
        "stack",
        "github_url",
        "website_url",
        "tagline",
    }
    missing = sorted(required.difference(profile))
    if missing:
        raise ValueError(f"profile.json is missing: {', '.join(missing)}")

    for key in ("name", "username", "role", "studio", "focus", "github_url", "website_url", "tagline"):
        value = profile[key]
        if not isinstance(value, str) or not value.strip() or not is_xml_text(value):
            raise ValueError(f"profile.json field '{key}' must be a non-empty string")
        profile[key] = value.strip()

    for key in ("building", "public_projects"):
        value = profile[key]
        if not isinstance(value, list) or not value or not all(
            isinstance(item, str) and item.strip() and is_xml_text(item) for item in value
        ):
            raise ValueError(f"profile.json field '{key}' must be a non-empty list of strings")
        profile[key] = [item.strip() for item in value]

    stack = profile["stack"]
    if not isinstance(stack, list) or not stack:
        raise ValueError("profile.json field 'stack' must be a non-empty list")
    normalized_stack = []
    for index, item in enumerate(stack):
        if not isinstance(item, dict):
            raise ValueError(f"profile.json stack item {index} must be an object")
        label, value = item.get("label"), item.get("value")
        if (
            not isinstance(label, str)
            or not label.strip()
            or not is_xml_text(label)
            or not isinstance(value, str)
            or not value.strip()
            or not is_xml_text(value)
        ):
            raise ValueError(f"profile.json stack item {index} needs non-empty string label and value")
        normalized_stack.append({"label": label.strip(), "value": value.strip()})
    profile["stack"] = normalized_stack
    return profile


def portrait_data_uri() -> str:
    encoded = base64.b64encode(PORTRAIT_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def stack_rows(profile: dict, palette: dict) -> str:
    rows = []
    for index, item in enumerate(profile["stack"][:4]):
        y = 390 + index * 28
        rows.append(
            f'<text x="58" y="{y}" class="mono small" fill="{palette["cyan"]}">'
            f'{esc(item["label"])}</text>'
        )
        rows.append(
            f'<line x1="184" y1="{y - 5}" x2="383" y2="{y - 5}" '
            f'stroke="{palette["line"]}" stroke-dasharray="2 6"/>'
        )
        rows.append(
            f'<text x="397" y="{y}" class="mono small" fill="{palette["text"]}">'
            f'{esc(item["value"])}</text>'
        )
    return "".join(rows)


def render(profile: dict, portrait_uri: str, theme: str) -> str:
    p = PALETTES[theme]
    photo_clip = cut_panel(764, 108, 360, 368, 18)
    outer = cut_panel(12, 12, 1156, 596, 18)
    building = " / ".join(str(item).upper() for item in profile["building"])
    projects = "  ·  ".join(profile["public_projects"])
    stack = stack_rows(profile, p)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="620" viewBox="0 0 1180 620" role="img" aria-labelledby="title desc">
  <title id="title">Anthony Pan — ONYX Builder Console</title>
  <desc id="desc">Anthony Pan is the founder and product engineer at ONYX Lab, building Feedii and FillMate with Swift, Flutter, Supabase, and applied AI.</desc>
  <style>
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }}
    .small {{ font-size: 13px; }}
    .label {{ font-size: 12px; letter-spacing: 2.4px; }}
    .reveal-a {{ animation: rise .55s ease-out both; }}
    .reveal-b {{ animation: rise .55s .12s ease-out both; }}
    .reveal-c {{ animation: rise .55s .24s ease-out both; }}
    .trace {{ stroke-dasharray: 390; animation: trace 1.1s .2s ease-out both; }}
    .scan {{ animation: scan 7s linear infinite; transform-box: fill-box; transform-origin: center; }}
    .pulse {{ animation: pulse 1.8s ease-in-out infinite; }}
    .cursor {{ animation: cursor 1s steps(1, end) infinite; }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(8px); }} }}
    @keyframes trace {{ from {{ stroke-dashoffset: 390; }} }}
    @keyframes scan {{ 0%, 10% {{ transform: translateY(-48px); }} 80%, 100% {{ transform: translateY(370px); }} }}
    @keyframes pulse {{ 50% {{ opacity: .28; }} }}
    @keyframes cursor {{ 50% {{ opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .reveal-a, .reveal-b, .reveal-c, .trace, .scan, .pulse, .cursor {{ animation: none; }}
    }}
  </style>
  <defs>
    <linearGradient id="frame" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{p["purple"]}"/>
      <stop offset=".52" stop-color="{p["line"]}"/>
      <stop offset="1" stop-color="{p["cyan"]}"/>
    </linearGradient>
    <linearGradient id="scanFade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{p["scan"]}" stop-opacity="0"/>
      <stop offset=".5" stop-color="{p["scan"]}" stop-opacity=".18"/>
      <stop offset="1" stop-color="{p["scan"]}" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="photoClip"><path d="{photo_clip}"/></clipPath>
    <pattern id="scanlines" width="4" height="4" patternUnits="userSpaceOnUse">
      <path d="M0 1H4" stroke="{p["scan"]}" stroke-opacity=".08"/>
    </pattern>
    <pattern id="microgrid" width="24" height="24" patternUnits="userSpaceOnUse">
      <path d="M24 0H0V24" fill="none" stroke="{p["grid"]}" stroke-width=".5"/>
    </pattern>
  </defs>

  <rect width="1180" height="620" fill="{p["bg"]}"/>
  <path d="{outer}" fill="{p["surface"]}" stroke="url(#frame)" stroke-width="2"/>
  <path d="M30 30H1150V590H30Z" fill="url(#microgrid)" opacity=".34"/>

  <g class="reveal-a">
    <text x="56" y="47" class="mono label" fill="{p["muted"]}">~/ANTHONY-PAN/MANIFEST</text>
    <text x="1124" y="47" class="mono label" fill="{p["cyan"]}" text-anchor="end">PROFILE NODE 00A7</text>
    <circle cx="1140" cy="43" r="5" fill="{p["green"]}" class="pulse"/>
    <line x1="36" y1="72" x2="1144" y2="72" stroke="{p["line"]}"/>
  </g>

  <g class="reveal-b">
    <text x="56" y="119" class="mono label" fill="{p["cyan"]}">00 / IDENTITY</text>
    <text x="56" y="157" class="mono small" fill="{p["muted"]}">$ whoami</text>
    <text x="56" y="218" class="mono" font-size="55" font-weight="700" letter-spacing="-2" fill="{p["text"]}">{esc(str(profile["name"]).upper())}</text>
    <rect x="56" y="237" width="12" height="22" fill="{p["cyan"]}" class="cursor"/>
    <text x="78" y="254" class="mono" font-size="21" fill="{p["text"]}">{esc(profile["role"])}</text>
    <text x="56" y="284" class="mono" font-size="16" fill="{p["purple"]}">{esc(profile["studio"])}</text>
    <text x="172" y="284" class="mono" font-size="16" fill="{p["muted"]}">/ {esc(profile["focus"])}</text>

    <text x="56" y="326" class="mono small" fill="{p["muted"]}">$ now --building</text>
    <text x="218" y="326" class="mono" font-size="15" font-weight="700" fill="{p["green"]}">{esc(building)}</text>
    <text x="56" y="356" class="mono small" fill="{p["muted"]}">$ ls public/</text>
    <text x="184" y="356" class="mono small" fill="{p["text"]}">{esc(projects)}</text>
    {stack}
  </g>

  <g class="reveal-c">
    <line x1="724" y1="116" x2="724" y2="506" stroke="{p["line"]}" stroke-width="2" class="trace"/>
    <circle cx="724" cy="154" r="6" fill="{p["cyan"]}"/>
    <circle cx="724" cy="268" r="8" fill="{p["green"]}" class="pulse"/>
    <circle cx="724" cy="382" r="6" fill="{p["cyan"]}"/>
    <circle cx="724" cy="496" r="6" fill="{p["purple"]}"/>
    <text x="708" y="158" class="mono" font-size="10" fill="{p["muted"]}" text-anchor="end">ID</text>
    <text x="708" y="272" class="mono" font-size="10" fill="{p["green"]}" text-anchor="end">BUILD</text>
    <text x="708" y="386" class="mono" font-size="10" fill="{p["muted"]}" text-anchor="end">PUBLIC</text>
    <text x="708" y="500" class="mono" font-size="10" fill="{p["muted"]}" text-anchor="end">LINK</text>

    <path d="{photo_clip}" fill="{p["surface_2"]}" stroke="{p["cyan"]}" stroke-width="1.5"/>
    <image x="764" y="108" width="360" height="368" href="{portrait_uri}" preserveAspectRatio="xMidYMid slice" clip-path="url(#photoClip)"/>
    <rect x="764" y="108" width="360" height="368" fill="url(#scanlines)" clip-path="url(#photoClip)"/>
    <rect x="764" y="108" width="360" height="48" fill="url(#scanFade)" clip-path="url(#photoClip)" class="scan"/>
    <path d="M764 136V108H792 M1096 108H1124V136 M764 448V476H792 M1096 476H1124V448" fill="none" stroke="{p["cyan"]}" stroke-width="3"/>
    <rect x="786" y="442" width="190" height="22" fill="{p["bg"]}" opacity=".82"/>
    <text x="796" y="457" class="mono" font-size="11" fill="{p["cyan"]}">PORTRAIT.BMP / 1254² / RGB</text>
  </g>

  <g class="reveal-c">
    <line x1="36" y1="530" x2="1144" y2="530" stroke="{p["line"]}"/>
    <text x="56" y="560" class="mono small" fill="{p["cyan"]}">{esc(profile["github_url"].replace("https://", ""))}</text>
    <text x="56" y="583" class="mono small" fill="{p["muted"]}">{esc(profile["website_url"].replace("https://www.", ""))}</text>
    <text x="1124" y="560" class="mono label" text-anchor="end" fill="{p["green"]}">BUILD // CONTINUES</text>
    <text x="1124" y="583" class="mono small" text-anchor="end" fill="{p["muted"]}">{esc(profile["tagline"])}</text>
  </g>
</svg>'''


def main() -> None:
    profile = load_profile()
    portrait_uri = portrait_data_uri()
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    for theme in PALETTES:
        output = ASSET_DIR / f"hero-{theme}.svg"
        output.write_text(render(profile, portrait_uri, theme), encoding="utf-8")
        print(f"wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
