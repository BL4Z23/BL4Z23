#!/usr/bin/env python3
"""
Generates a custom "Most Used Languages" donut chart SVG from real GitHub
language data (including private repos, via a token with repo scope).

Env vars required:
  GH_TOKEN     - a GitHub personal access token (classic) with repo + read:user scopes
  GH_USERNAME  - the GitHub username to fetch stats for

Output:
  dist/languages.svg
"""

import json
import math
import os
import urllib.request

GH_TOKEN = os.environ["GH_TOKEN"]
GH_USERNAME = os.environ["GH_USERNAME"]

GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 50, after: $after, ownerAffiliation: OWNER, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node { name color }
          }
        }
      }
    }
  }
}
"""

# ---- Colors / theme (matches the fire-orange README theme) ----
BG_COLOR = "#0D1117"
TITLE_COLOR = "#FFFFFF"
TEXT_COLOR = "#C9D1D9"
BORDER_RADIUS = 20
MAX_LANGS_SHOWN = 8  # remaining languages get grouped into "Other"


def fetch_language_bytes():
    lang_bytes = {}
    lang_colors = {}
    after = None

    while True:
        payload = json.dumps(
            {"query": QUERY, "variables": {"login": GH_USERNAME, "after": after}}
        ).encode()
        req = urllib.request.Request(
            GRAPHQL_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {GH_TOKEN}",
                "Content-Type": "application/json",
                "User-Agent": GH_USERNAME,
            },
        )
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)

        if "errors" in data:
            raise RuntimeError(data["errors"])

        repos = data["data"]["user"]["repositories"]
        for repo in repos["nodes"]:
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                lang_bytes[name] = lang_bytes.get(name, 0) + edge["size"]
                lang_colors[name] = edge["node"]["color"] or "#888888"

        if repos["pageInfo"]["hasNextPage"]:
            after = repos["pageInfo"]["endCursor"]
        else:
            break

    return lang_bytes, lang_colors


def build_slices(lang_bytes, lang_colors):
    total = sum(lang_bytes.values()) or 1
    sorted_langs = sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)

    shown = sorted_langs[:MAX_LANGS_SHOWN]
    rest = sorted_langs[MAX_LANGS_SHOWN:]

    slices = [
        {"name": name, "pct": size / total * 100, "color": lang_colors[name]}
        for name, size in shown
    ]

    if rest:
        rest_total = sum(size for _, size in rest)
        slices.append({"name": "Other", "pct": rest_total / total * 100, "color": "#8B949E"})

    return slices, len(lang_bytes)


def render_svg(slices, lang_count):
    width, height = 640, 460
    cx, cy, r, stroke_w = 320, 195, 130, 46
    circumference = 2 * math.pi * r

    # Donut arcs
    arcs = []
    offset = 0.0
    # rotate so the first slice starts at 12 o'clock: SVG circles start at 3 o'clock,
    # so we rotate -90deg on the group.
    for s in slices:
        dash = (s["pct"] / 100) * circumference
        gap = circumference - dash
        arcs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="{s["color"]}" stroke-width="{stroke_w}" '
            f'stroke-dasharray="{dash:.2f} {gap:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {cx} {cy})">'
            f'<title>{s["name"]}: {s["pct"]:.1f}%</title>'
            f"</circle>"
        )
        offset += dash

    # Legend: wrap into 2 rows
    n = len(slices)
    per_row = math.ceil(n / 2)
    col_w = (width - 60) / per_row
    legend_items = []
    for i, s in enumerate(slices):
        row = i // per_row
        col = i % per_row
        lx = 30 + col * col_w
        ly = 400 + row * 30
        legend_items.append(
            f'<rect x="{lx:.1f}" y="{ly - 12:.1f}" width="14" height="14" rx="3" fill="{s["color"]}" />'
            f'<text x="{lx + 20:.1f}" y="{ly:.1f}" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
            f'font-size="13" fill="{TEXT_COLOR}">{s["name"]} {s["pct"]:.1f}%</text>'
        )

    svg = f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="{BORDER_RADIUS}"
        fill="{BG_COLOR}" stroke="none" />

  <text x="30" y="40" font-family="Segoe UI, Helvetica, Arial, sans-serif"
        font-size="22" font-weight="bold" fill="{TITLE_COLOR}">Most Used Languages</text>

  {''.join(arcs)}

  <text x="{cx}" y="{cy - 6}" text-anchor="middle" font-family="Segoe UI, Helvetica, Arial, sans-serif"
        font-size="42" font-weight="bold" fill="{TITLE_COLOR}">{lang_count}</text>
  <text x="{cx}" y="{cy + 22}" text-anchor="middle" font-family="Segoe UI, Helvetica, Arial, sans-serif"
        font-size="14" fill="{TEXT_COLOR}">Languages</text>

  {''.join(legend_items)}
</svg>"""
    return svg


def main():
    lang_bytes, lang_colors = fetch_language_bytes()
    if not lang_bytes:
        raise RuntimeError("No language data found — check GH_TOKEN scopes and username.")

    slices, lang_count = build_slices(lang_bytes, lang_colors)
    svg = render_svg(slices, lang_count)

    os.makedirs("dist", exist_ok=True)
    with open("dist/languages.svg", "w") as f:
        f.write(svg)

    print(f"Wrote dist/languages.svg with {lang_count} languages ({len(slices)} slices shown).")


if __name__ == "__main__":
    main()
