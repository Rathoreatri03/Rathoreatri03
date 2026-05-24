"""
generate_stats.py
Fetches real GitHub data via GraphQL API and writes:
  - github-stats.svg   (contributions, stars, PRs, issues, commits)
  - github-langs.svg   (top languages by repo)
Both render in dark mode (#0d1117 bg, #00ff66 accents) — no external service needed.
"""

import os, json, requests

TOKEN    = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ.get("USERNAME", "Rathoreatri03")
HEADERS  = {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"}
GREEN    = "#00ff66"
DIM      = "#888888"
TEXT     = "#c9d1d9"
BG       = "#0d1117"
BORDER   = "#00ff66"

# ── GraphQL query ──────────────────────────────────────────────────────────────
QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoryContributions
    }
    followers { totalCount }
  }
}
"""

resp = requests.post(
    "https://api.github.com/graphql",
    json={"query": QUERY, "variables": {"login": USERNAME}},
    headers=HEADERS,
    timeout=20,
)
resp.raise_for_status()
data = resp.json()["data"]["user"]

# ── Aggregate stats ────────────────────────────────────────────────────────────
cc   = data["contributionsCollection"]
repos = data["repositories"]["nodes"]
stars = sum(r["stargazerCount"] for r in repos)
commits  = cc["totalCommitContributions"]
prs      = cc["totalPullRequestContributions"]
issues   = cc["totalIssueContributions"]
contrib_repos = cc["totalRepositoryContributions"]
followers = data["followers"]["totalCount"]
name      = data["name"] or USERNAME

# ── Language aggregation ───────────────────────────────────────────────────────
lang_bytes: dict[str, int]  = {}
lang_color: dict[str, str]  = {}
for repo in repos:
    for edge in repo["languages"]["edges"]:
        n = edge["node"]["name"]
        lang_bytes[n] = lang_bytes.get(n, 0) + edge["size"]
        lang_color[n] = edge["node"]["color"] or "#58a6ff"

total_bytes = sum(lang_bytes.values()) or 1
top_langs   = sorted(lang_bytes, key=lambda k: lang_bytes[k], reverse=True)[:8]

# ── SVG helpers ───────────────────────────────────────────────────────────────
def card(body: str, width=300, height=165, title="") -> str:
    t = f'<text x="16" y="28" font-family="Fira Code,monospace" font-size="13" font-weight="700" fill="{GREEN}">{title}</text>' if title else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" rx="8" fill="{BG}" stroke="{BORDER}" stroke-width="0.8"/>
  {t}
  {body}
</svg>"""

def mono(x, y, val, label, accent=GREEN):
    return (
        f'<text x="{x}" y="{y}" font-family="Fira Code,monospace" font-size="22" font-weight="700" fill="{accent}">{val}</text>'
        f'<text x="{x}" y="{y+16}" font-family="Fira Code,monospace" font-size="10" fill="{DIM}">{label}</text>'
    )

def bar(x, y, w, pct, color):
    filled = max(4, int(w * pct / 100))
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="5" rx="2" fill="#1a1a2e"/>'
        f'<rect x="{x}" y="{y}" width="{filled}" height="5" rx="2" fill="{color}"/>'
    )

# ── github-stats.svg ──────────────────────────────────────────────────────────
W, H = 300, 165
stats_body = ""
stats_body += f'<text x="16" y="28" font-family="Fira Code,monospace" font-size="11" font-weight="700" fill="{GREEN}">⚡ {name}\'s GitHub Stats</text>'

rows = [
    ("⭐ Total Stars",       f"{stars:,}"),
    ("🔨 Total Commits",     f"{commits:,}"),
    ("🔀 Pull Requests",     f"{prs:,}"),
    ("🐛 Issues Opened",     f"{issues:,}"),
    ("📦 Contributed Repos", f"{contrib_repos:,}"),
    ("👥 Followers",         f"{followers:,}"),
]
for i, (label, val) in enumerate(rows):
    yy = 50 + i * 18
    stats_body += f'<text x="16" y="{yy}" font-family="Fira Code,monospace" font-size="11" fill="{DIM}">{label}</text>'
    stats_body += f'<text x="{W-16}" y="{yy}" text-anchor="end" font-family="Fira Code,monospace" font-size="11" font-weight="700" fill="{TEXT}">{val}</text>'
    stats_body += f'<line x1="16" y1="{yy+3}" x2="{W-16}" y2="{yy+3}" stroke="#1e2a1e" stroke-width="0.4"/>'

with open("github-stats.svg", "w") as f:
    f.write(card(stats_body, W, H))

# ── github-langs.svg ──────────────────────────────────────────────────────────
LW, LH = 300, 165
langs_body = ""
langs_body += f'<text x="16" y="28" font-family="Fira Code,monospace" font-size="11" font-weight="700" fill="{GREEN}">🧠 Most Used Languages</text>'

bar_y = 44
bar_w = LW - 32
# colour bar strip across top
x_off = 16
for lang in top_langs:
    seg = int(bar_w * lang_bytes[lang] / total_bytes)
    c   = lang_color[lang]
    langs_body += f'<rect x="{x_off}" y="{bar_y}" width="{seg}" height="7" fill="{c}" rx="2"/>'
    x_off += seg
langs_body += f'<rect x="16" y="{bar_y}" width="{bar_w}" height="7" rx="3" fill="none" stroke="#333" stroke-width="0.5"/>'

# legend grid (2 columns)
col_w = (LW - 32) // 2
for idx, lang in enumerate(top_langs):
    col = idx % 2
    row = idx // 2
    lx  = 16 + col * col_w
    ly  = bar_y + 22 + row * 22
    pct = round(lang_bytes[lang] / total_bytes * 100, 1)
    c   = lang_color[lang]
    langs_body += f'<circle cx="{lx+6}" cy="{ly-4}" r="4" fill="{c}"/>'
    langs_body += f'<text x="{lx+14}" y="{ly}" font-family="Fira Code,monospace" font-size="10" fill="{TEXT}">{lang[:16]}</text>'
    langs_body += f'<text x="{lx+col_w-4}" y="{ly}" text-anchor="end" font-family="Fira Code,monospace" font-size="10" fill="{DIM}">{pct}%</text>'

with open("github-langs.svg", "w") as f:
    f.write(card(langs_body, LW, LH))

print(f"✅ Generated github-stats.svg and github-langs.svg for {USERNAME}")
print(f"   Stars: {stars} | Commits: {commits} | PRs: {prs} | Top lang: {top_langs[0] if top_langs else 'N/A'}")
