"""
generate_stats.py
Fetches REAL all-time GitHub data and writes:
  - github-stats.svg
  - github-langs.svg
Commit count uses REST search API (all-time, not just current year).
"""

import os, json, requests

TOKEN    = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ.get("USERNAME", "Rathoreatri03")
HEADERS  = {
    "Authorization": f"bearer {TOKEN}",
    "Content-Type": "application/json"
}
REST_HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

GREEN  = "#00ff66"
DIM    = "#888888"
TEXT   = "#c9d1d9"
BG     = "#0d1117"
BORDER = "#00ff66"

# ── 1. GraphQL — stars, PRs, issues, repos, followers, languages ──────────────
QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    pullRequests(states: [OPEN, MERGED, CLOSED]) { totalCount }
    issues(states: [OPEN, CLOSED]) { totalCount }
    repositoriesContributedTo(
      first: 1
      contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY, REVIEW]
    ) { totalCount }
  }
}
"""

gql = requests.post(
    "https://api.github.com/graphql",
    json={"query": QUERY, "variables": {"login": USERNAME}},
    headers=HEADERS,
    timeout=20,
)
gql.raise_for_status()
u = gql.json()["data"]["user"]

repos     = u["repositories"]["nodes"]
stars     = sum(r["stargazerCount"] for r in repos)
followers = u["followers"]["totalCount"]
prs       = u["pullRequests"]["totalCount"]
issues    = u["issues"]["totalCount"]
contrib_repos = u["repositoriesContributedTo"]["totalCount"]
name      = u["name"] or USERNAME

# ── 2. REST search API — ALL-TIME commit count ────────────────────────────────
# GitHub search: author:USERNAME type:commit — returns total_count across ALL repos
search = requests.get(
    f"https://api.github.com/search/commits?q=author:{USERNAME}&per_page=1",
    headers={**REST_HEADERS, "Accept": "application/vnd.github.cloak-preview+json"},
    timeout=20,
)
if search.status_code == 200:
    commits = search.json().get("total_count", 0)
else:
    # fallback: sum commits from each repo via REST
    commits = 0
    for repo in repos[:30]:   # cap at 30 to stay within rate limit
        r2 = requests.get(
            f"https://api.github.com/repos/{USERNAME}/{repo.get('name','')}/commits?author={USERNAME}&per_page=1",
            headers=REST_HEADERS, timeout=10
        )
        if r2.status_code == 200:
            link = r2.headers.get("Link", "")
            if 'rel="last"' in link:
                import re
                m = re.search(r'page=(\d+)>; rel="last"', link)
                commits += int(m.group(1)) if m else 1
            else:
                commits += len(r2.json())

# ── 3. Language aggregation ───────────────────────────────────────────────────
lang_bytes: dict = {}
lang_color: dict = {}
for repo in repos:
    for edge in repo["languages"]["edges"]:
        n = edge["node"]["name"]
        lang_bytes[n] = lang_bytes.get(n, 0) + edge["size"]
        lang_color[n] = edge["node"]["color"] or "#58a6ff"

total_bytes = sum(lang_bytes.values()) or 1
top_langs   = sorted(lang_bytes, key=lambda k: lang_bytes[k], reverse=True)[:8]

# ── SVG helpers ───────────────────────────────────────────────────────────────
def card(body: str, width=300, height=165) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" rx="8" fill="{BG}" '
        f'stroke="{BORDER}" stroke-width="0.8"/>'
        f'{body}'
        f'</svg>'
    )

# ── github-stats.svg ──────────────────────────────────────────────────────────
W, H = 300, 175
body = ""
body += (
    f'<text x="16" y="26" font-family="Fira Code,monospace" '
    f'font-size="11" font-weight="700" fill="{GREEN}">⚡ {name}\'s GitHub Stats</text>'
)

rows = [
    ("⭐  Total Stars",        f"{stars:,}"),
    ("🔨  Total Commits",      f"{commits:,}"),
    ("🔀  Pull Requests",      f"{prs:,}"),
    ("🐛  Issues",             f"{issues:,}"),
    ("📦  Contributed Repos",  f"{contrib_repos:,}"),
    ("👥  Followers",          f"{followers:,}"),
]

for i, (label, val) in enumerate(rows):
    yy = 48 + i * 19
    body += (
        f'<text x="16" y="{yy}" font-family="Fira Code,monospace" '
        f'font-size="10.5" fill="{DIM}">{label}</text>'
        f'<text x="{W-16}" y="{yy}" text-anchor="end" font-family="Fira Code,monospace" '
        f'font-size="10.5" font-weight="700" fill="{TEXT}">{val}</text>'
        f'<line x1="16" y1="{yy+4}" x2="{W-16}" y2="{yy+4}" '
        f'stroke="#1a2a1a" stroke-width="0.4"/>'
    )

with open("github-stats.svg", "w") as f:
    f.write(card(body, W, H))

# ── github-langs.svg ──────────────────────────────────────────────────────────
LW, LH = 300, 175
lbody = ""
lbody += (
    f'<text x="16" y="26" font-family="Fira Code,monospace" '
    f'font-size="11" font-weight="700" fill="{GREEN}">🧠 Most Used Languages</text>'
)

bar_y = 38
bar_w = LW - 32
x_off = 16
for lang in top_langs:
    seg = max(2, int(bar_w * lang_bytes[lang] / total_bytes))
    c   = lang_color[lang]
    lbody += f'<rect x="{x_off}" y="{bar_y}" width="{seg}" height="7" fill="{c}" rx="1"/>'
    x_off += seg
lbody += (
    f'<rect x="16" y="{bar_y}" width="{bar_w}" height="7" rx="3" '
    f'fill="none" stroke="#333" stroke-width="0.5"/>'
)

col_w = (LW - 32) // 2
for idx, lang in enumerate(top_langs):
    col = idx % 2
    row = idx // 2
    lx  = 16 + col * col_w
    ly  = bar_y + 24 + row * 22
    pct = round(lang_bytes[lang] / total_bytes * 100, 1)
    c   = lang_color[lang]
    lbody += (
        f'<circle cx="{lx+6}" cy="{ly-4}" r="4" fill="{c}"/>'
        f'<text x="{lx+14}" y="{ly}" font-family="Fira Code,monospace" '
        f'font-size="10" fill="{TEXT}">{lang[:14]}</text>'
        f'<text x="{lx+col_w-4}" y="{ly}" text-anchor="end" '
        f'font-family="Fira Code,monospace" font-size="10" fill="{DIM}">{pct}%</text>'
    )

with open("github-langs.svg", "w") as f:
    f.write(card(lbody, LW, LH))

print(f"✅ Done — {USERNAME}")
print(f"   Stars:{stars}  Commits:{commits:,}  PRs:{prs}  Top:{top_langs[0] if top_langs else 'n/a'}")
