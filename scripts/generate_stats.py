#!/usr/bin/env python3
"""Generate four deterministic, monochrome GitHub profile SVGs using GraphQL only."""
from __future__ import annotations
import json, os, sys
from datetime import date, datetime, time, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from xml.sax.saxutils import escape

API = "https://api.github.com/graphql"
LOGIN = os.environ.get("GH_LOGIN", "").strip()
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
RAMP = os.environ.get("ASCII_RAMP", " .`:-=+*cs#%@")
BG = "#0b0b0b"
FG = "#d4d4d4"
DIM = "#777777"
MUTED = "#333333"

if not LOGIN or not TOKEN:
    sys.exit("Set GH_LOGIN and GITHUB_TOKEN before running this script.")


def graphql(query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = Request(API, data=body, headers={
        "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
        "Accept": "application/vnd.github+json", "User-Agent": "self-generating-profile",
    })
    try:
        with urlopen(req, timeout=30) as response:
            result = json.load(response)
    except (HTTPError, URLError) as exc:
        sys.exit(f"GitHub GraphQL request failed: {exc}")
    if result.get("errors"):
        sys.exit("GitHub GraphQL errors: " + json.dumps(result["errors"]))
    return result["data"]


def svg_start(width: int, height: int, title: str) -> list[str]:
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
            f'<rect width="{width}" height="{height}" fill="{BG}"/>',
            '<g font-family="JetBrains Mono,DejaVu Sans Mono,monospace" font-size="12">']


def text(x: float, y: float, value: str, size: int = 12, fill: str = FG, weight: str = "normal") -> str:
    return f'<text x="{x:.2f}" y="{y:.2f}" fill="{fill}" font-size="{size}" font-weight="{weight}">{escape(str(value))}</text>'


def write_svg(path: str, lines: list[str]) -> None:
    lines += ["</g>", "</svg>"]
    content = "\n".join(lines) + "\n"
    try:
        old = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        old = None
    if old != content:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        print(f"updated {path}")
    else:
        print(f"unchanged {path}")


# Use UTC calendar dates, with stable full-day boundaries.
today = datetime.now(timezone.utc).date()
from_day = today - timedelta(days=364)
from_utc = datetime.combine(from_day, time.min, timezone.utc).isoformat().replace("+00:00", "Z")
to_utc = datetime.combine(today, time.max.replace(microsecond=0), timezone.utc).isoformat().replace("+00:00", "Z")

contrib_query = '''query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
  }
}'''
contrib = graphql(contrib_query, {"login": LOGIN, "from": from_utc, "to": to_utc})["user"]["contributionsCollection"]["contributionCalendar"]
days_by_date = {d["date"]: int(d["contributionCount"])
                 for w in contrib["weeks"] for d in w["contributionDays"]}
# Normalize to precisely 365 consecutive dates, even if API omits an edge bucket.
dates = [from_day + timedelta(days=i) for i in range(365)]
counts = [days_by_date.get(d.isoformat(), 0) for d in dates]
total = sum(counts)

# Streaks are computed from daily counts. Current streak includes today if active;
# otherwise it is zero (does not silently count yesterday as current).
longest_len, longest_start, longest_end = 0, None, None
run_len, run_start = 0, None
for d, count in zip(dates, counts):
    if count > 0:
        if run_len == 0: run_start = d
        run_len += 1
        if run_len > longest_len:
            longest_len, longest_start, longest_end = run_len, run_start, d
    else:
        run_len, run_start = 0, None
current_len = 0
idx = len(counts) - 1
if counts[idx] > 0:
    while idx >= 0 and counts[idx] > 0:
        current_len += 1
        idx -= 1
current_start = dates[len(dates) - current_len] if current_len else None

# Weekly totals are aggregated into columns, not a daily line chart.
weekly = []
for i in range(0, len(counts), 7):
    weekly.append(sum(counts[i:i+7]))

# Stats hero and weekly sparkline.
lines = svg_start(760, 142, "Contribution total and weekly contribution bars")
lines += [text(24, 27, "CONTRIBUTIONS / LAST 365 UTC DAYS", 11, DIM),
          text(24, 80, f"{total:,}", 42, FG, "bold"),
          text(26, 104, f"{from_day.isoformat()}  →  {today.isoformat()}", 10, DIM)]
chart_x, chart_y, chart_w, chart_h = 265, 40, 470, 66
max_week = max(weekly, default=0) or 1
bar_gap = 2
bar_w = (chart_w - (len(weekly) - 1) * bar_gap) / max(1, len(weekly))
for i, value in enumerate(weekly):
    h = max(1, chart_h * value / max_week) if value else 0
    x = chart_x + i * (bar_w + bar_gap)
    if h:
        lines.append(f'<rect x="{x:.2f}" y="{chart_y + chart_h - h:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{FG}"/>')
lines += [text(chart_x, 125, "WEEKLY TOTALS", 9, DIM), text(735, 125, str(max_week), 9, DIM)]
write_svg("stats.svg", lines)

# Streak card.
lines = svg_start(760, 158, "Current and longest contribution streaks")
lines += [text(24, 27, "STREAKS", 11, DIM),
          text(24, 75, str(current_len), 36, FG, "bold"),
          text(24, 96, "CURRENT DAYS", 10, DIM),
          text(24, 119, f"{current_start.isoformat()} → {today.isoformat()}" if current_start else "No active streak today", 10, FG),
          '<line x1="380" y1="42" x2="380" y2="132" stroke="#333"/>',
          text(410, 75, str(longest_len), 36, FG, "bold"),
          text(410, 96, "LONGEST DAYS", 10, DIM),
          text(410, 119, f"{longest_start.isoformat()} → {longest_end.isoformat()}" if longest_start else "No contribution streak in window", 10, FG)]
write_svg("streak.svg", lines)

# Public, non-fork repositories only; one query page is intentional and explicitly labeled.
repo_query = '''query($login:String!) {
  user(login:$login) {
    repositories(first:100, ownerAffiliations:OWNER, privacy:PUBLIC, isFork:false, orderBy:{field:UPDATED_AT,direction:DESC}) {
      nodes { name primaryLanguage { name } languages(first:20) { edges { size node { name } } } }
    }
  }
}'''
repos = graphql(repo_query, {"login": LOGIN})["user"]["repositories"]["nodes"]
lang_bytes: dict[str, int] = {}
lang_repos: dict[str, int] = {}
for repo in repos:
    seen = set()
    for edge in (repo.get("languages") or {}).get("edges", []):
        name = edge["node"]["name"]
        lang_bytes[name] = lang_bytes.get(name, 0) + int(edge["size"])
        seen.add(name)
    # Repo counts count each language once per repository, independent of byte count.
    for name in seen:
        lang_repos[name] = lang_repos.get(name, 0) + 1
ranked = sorted(lang_bytes, key=lambda n: (-lang_bytes[n], n))[:8]
max_bytes = max((lang_bytes[n] for n in ranked), default=1) or 1
lines = svg_start(760, 238, "Top programming languages in public non-fork repositories")
lines.append(text(24, 27, "LANGUAGES / PUBLIC NON-FORK REPOS", 11, DIM))
lines.append(text(24, 46, "BYTES OF CODE", 9, DIM))
if not ranked:
    lines.append(text(24, 78, "No language data found in the first 100 public repositories.", 12, FG))
for i, name in enumerate(ranked):
    y = 70 + i * 20
    lines += [text(24, y + 10, name, 11, FG),
              f'<rect x="170" y="{y}" width="340" height="9" fill="{MUTED}"/>',
              f'<rect x="170" y="{y}" width="{340 * lang_bytes[name] / max_bytes:.2f}" height="9" fill="{FG}"/>',
              text(525, y + 9, f"{lang_bytes[name]:,} B", 10, FG),
              text(650, y + 9, f"{lang_repos.get(name, 0)} repos", 10, DIM)]
lines.append(text(24, 230, f"Scanned {len(repos)} most recently updated public, non-fork repositories (max 100).", 9, DIM))
write_svg("langs.svg", lines)

# One character per day. Reuse the portrait ramp; no colored squares.
def ramp_char(count: int, maximum: int) -> str:
    if count <= 0: return RAMP[0]
    idx = 1 + round((len(RAMP) - 1) * count / maximum)
    return RAMP[min(len(RAMP) - 1, idx)]

max_count = max(counts, default=0) or 1
lines = svg_start(760, 112, "Yearly daily contributions as ASCII characters")
lines += [text(24, 24, f"YEAR / {today.year} · ONE CHARACTER PER DAY", 11, DIM),
          text(24, 42, f"RAMP: {RAMP}", 9, DIM)]
# Monospace grid: 53 columns by 7 weekdays; rows are weekdays, columns are weeks.
# Each date occupies one character; weeks start Sunday to align with GitHub's calendar.
calendar_start = dates[0] - timedelta(days=(dates[0].weekday() + 1) % 7)
char_map = {d: ramp_char(c, max_count) for d, c in zip(dates, counts)}
for weekday in range(7):
    row_chars = []
    cur = calendar_start + timedelta(days=weekday)
    while cur <= dates[-1]:
        row_chars.append(char_map.get(cur, " "))
        cur += timedelta(days=7)
    lines.append(f'<text x="24" y="{61 + weekday * 7}" fill="{FG}" font-size="10" xml:space="preserve">{escape("".join(row_chars))}</text>')
lines.append(text(24, 108, f"{total:,} contributions · {from_day.isoformat()} to {today.isoformat()} UTC", 9, DIM))
write_svg("year.svg", lines)
