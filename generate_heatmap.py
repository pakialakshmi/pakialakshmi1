#!/usr/bin/env python3
"""Render a burgundy contribution heatmap from real GitHub data.

Usage:
  GH_LOGIN=<user> GITHUB_TOKEN=<token> python3 scripts/generate_heatmap.py
  python3 scripts/generate_heatmap.py --demo     # clearly labelled placeholder

In GitHub Actions the built-in GITHUB_TOKEN is used. No secrets are written
to the output file.
"""
import datetime as dt
import json
import os
import random
import sys
from urllib import request

OUT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "assets", "contribution-heatmap.svg"))

QUERY = ("query($login:String!){user(login:$login){contributionsCollection{"
         "contributionCalendar{totalContributions weeks{contributionDays{"
         "date contributionCount contributionLevel weekday}}}}}}")
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
COLORS = ["#24101A", "#431126", "#701A3D", "#C77B9B", "#E5B5C7"]
MONO = "'SFMono-Regular', Consolas, 'Courier New', monospace"


def fetch(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "profile-heatmap"})
    with request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    user = (data.get("data") or {}).get("user")
    if data.get("errors") or not user:
        raise SystemExit(f"GitHub API error: {data.get('errors') or 'user not found'}")
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [[(d["date"], d["contributionCount"],
               LEVELS.get(d["contributionLevel"], 0), d["weekday"])
              for d in w["contributionDays"]] for w in cal["weeks"]]
    return weeks, cal["totalContributions"]


def demo():
    rnd = random.Random(7)
    start = dt.date(2025, 10, 19)  # a Sunday
    weeks = []
    for w in range(53):
        days = []
        for i in range(7):
            d = start + dt.timedelta(days=7 * w + i)
            lvl = rnd.choices([0, 1, 2, 3, 4], [40, 25, 18, 11, 6])[0]
            days.append((d.isoformat(), 0, lvl, i))
        weeks.append(days)
    return weeks, None


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(weeks, total, is_demo):
    cell, pitch = 12, 15
    x0, y0 = 62, 84
    width, height = 900, 226
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="sd-heat-title">',
        '<title id="sd-heat-title">GitHub contribution heatmap for the last 12 months'
        + (' (demo data)' if is_demo else '') + '</title>',
        '<defs><linearGradient id="sd-heat-bg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#10070C"/><stop offset="0.6" stop-color="#1B0B12"/>'
        '<stop offset="1" stop-color="#431126"/></linearGradient></defs>',
        f'<rect width="{width}" height="{height}" rx="16" fill="url(#sd-heat-bg)"/>',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="16" '
        'fill="none" stroke="#C77B9B" stroke-opacity="0.2"/>',
        '<text x="24" y="38" font-family="Georgia, \'Times New Roman\', serif" '
        'font-size="20" font-weight="700" fill="#F8F0F3">Contribution activity</text>',
        f'<text x="24" y="57" font-family="{MONO}" font-size="10" letter-spacing="2" '
        'fill="#C77B9B">LAST 12 MONTHS · REFRESHED DAILY BY GITHUB ACTIONS</text>',
    ]
    if is_demo:
        right = "DEMO DATA · LIVE DATA REPLACES THIS AFTER THE FIRST WORKFLOW RUN"
    else:
        right = f"{total:,} contributions in the last year"
    out.append(f'<text x="{width - 24}" y="38" text-anchor="end" font-family="{MONO}" '
               f'font-size="11" fill="#E5B5C7">{esc(right)}</text>')

    # month labels
    labels, last_month = [], None
    for ci, week in enumerate(weeks):
        d = dt.date.fromisoformat(week[0][0])
        if d.month != last_month:
            last_month = d.month
            if labels and ci - labels[-1][0] < 3:
                labels.pop()  # earlier label is a partial month; keep the newer one
            if ci <= len(weeks) - 2:
                labels.append((ci, d.strftime("%b")))
    for ci, text in labels:
        out.append(f'<text x="{x0 + ci * pitch}" y="{y0 - 9}" font-family="{MONO}" '
                   f'font-size="10" fill="#C77B9B">{text}</text>')

    # weekday labels
    for wd, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="{x0 - 10}" y="{y0 + wd * pitch + 10}" text-anchor="end" '
                   f'font-family="{MONO}" font-size="10" fill="#C77B9B">{label}</text>')

    # cells, one fading group per week
    for ci, week in enumerate(weeks):
        dur = len(weeks) * 0.03 + 0.6
        delay = ci * 0.03
        out.append('<g>')
        out.append(f'<animate attributeName="opacity" values="0;0;1" '
                   f'keyTimes="0;{delay / dur:.4f};1" dur="{dur:.2f}s" fill="freeze"/>')
        for date, count, lvl, wd in week:
            out.append(f'<rect x="{x0 + ci * pitch}" y="{y0 + wd * pitch}" width="{cell}" '
                       f'height="{cell}" rx="3" fill="{COLORS[lvl]}"/>')
        out.append('</g>')

    # legend
    ly = y0 + 7 * pitch + 22
    out.append(f'<text x="{width - 24}" y="{ly + 10}" text-anchor="end" font-family="{MONO}" '
               'font-size="10" fill="#C77B9B">More</text>')
    for i, c in enumerate(COLORS):
        out.append(f'<rect x="{width - 24 - 34 - (5 - i) * pitch}" y="{ly}" width="{cell}" '
                   f'height="{cell}" rx="3" fill="{c}"/>')
    out.append(f'<text x="{width - 24 - 34 - 5 * pitch - 8}" y="{ly + 10}" text-anchor="end" '
               f'font-family="{MONO}" font-size="10" fill="#C77B9B">Less</text>')
    out.append('</svg>')
    return "\n".join(out) + "\n"


def main():
    is_demo = "--demo" in sys.argv
    if is_demo:
        weeks, total = demo()
    else:
        login, token = os.environ.get("GH_LOGIN"), os.environ.get("GITHUB_TOKEN")
        if not login or not token:
            raise SystemExit("Set GH_LOGIN and GITHUB_TOKEN, or run with --demo.")
        weeks, total = fetch(login, token)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(weeks, total, is_demo))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
