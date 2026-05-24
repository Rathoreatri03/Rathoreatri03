"""
generate_stats.py — writes github-stats.svg + github-langs.svg
All-time commits via REST search API. Hardened with full error handling.
"""
import os, re, requests, sys

TOKEN    = os.environ.get("GITHUB_TOKEN", "")
USERNAME = os.environ.get("USERNAME", "Rathoreatri03")

if not TOKEN:
    print("ERROR: GITHUB_TOKEN not set", file=sys.stderr)
    sys.exit(1)

GQL_HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Content-Type":  "application/json",
}
REST_HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept":        "application/vnd.github.v3+json",
}
SEARCH_HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept":        "application/vnd.github.cloak-preview+json",
}

GREEN  = "#00ff66"
DIM    = "#888888"
TEXT   = "#c9d1d9"
BG     = "#0d1117"
BORDER = "#00ff66"

# ── 1. GraphQL ─────────────────────────────────────────────────────────────────
QUERY = """
query($login: String!, $types: [RepositoryContributionType!]) {
  user(login: $login) {
    name
    followers { totalCount }
    pullRequests(states: [OPEN, MERGED, CLOSED]) { totalCount }
    issues(states: [OPEN, CLOSED]) { totalCount }
    repositoriesContributedTo(
      first: 1
      contributionTypes: $types
    ) { totalCount }
    repositories(
      first: 100
      ownerAffiliations: OWNER
      privacy: PUBLIC
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

print(f"[1/4] Fetching GraphQL data for {USERNAME}...")
r = requests.post(
    "https://api.github.com/graphql",
    json={
        "query": QUERY, 
        "variables": {
            "login": USERNAME,
            "types": ["COMMIT", "PULL_REQUEST", "REPOSITORY", "REPOSITORY_REVIEW"]
        }
    },
    headers=GQL_HEADERS,
    timeout=30,
)
r.raise_for_status()
payload = r.json()
if "errors" in payload:
    print(f"GraphQL errors: {payload['errors']}", file=sys.stderr)
    sys.exit(1)

u         = payload["data"]["user"]
repos     = u["repositories"]["nodes"]
stars     = sum(n["stargazerCount"] for n in repos)
followers = u["followers"]["totalCount"]
prs       = u["pullRequests"]["totalCount"]
issues    = u["issues"]["totalCount"]
contribs  = u["repositoriesContributedTo"]["totalCount"]
name      = u["name"] or USERNAME
print(f"    Stars:{stars}  PRs:{prs}  Issues:{issues}  Followers:{followers}")

# ── 2. All-time commits via REST search ────────────────────────────────────────
print("[2/4] Fetching all-time commit count...")
commits = 0
try:
    sr = requests.get(
        f"https://api.github.com/search/commits?q=author:{USERNAME}&per_page=1",
        headers=SEARCH_HEADERS,
        timeout=20,
    )
    if sr.status_code == 200:
        commits = sr.json().get("total_count", 0)
        print(f"    Commits (search API): {commits:,}")
    else:
        print(f"    Search API returned {sr.status_code}, falling back to repo scan")
        raise ValueError("search API unavailable")
except Exception as e:
    print(f"    Fallback: scanning repos... ({e})")
    for repo in repos[:50]:
        rname = repo.get("name", "")
        if not rname:
            continue
        try:
            rc = requests.get(
                f"https://api.github.com/repos/{USERNAME}/{rname}/commits"
                f"?author={USERNAME}&per_page=1",
                headers=REST_HEADERS,
                timeout=10,
            )
            if rc.status_code == 200:
                link = rc.headers.get("Link", "")
                m = re.search(r'page=(\d+)>; rel="last"', link)
                commits += int(m.group(1)) if m else (1 if rc.json() else 0)
        except Exception:
            pass
    print(f"    Commits (repo scan fallback): {commits:,}")

# ── 3. Languages ───────────────────────────────────────────────────────────────
print("[3/4] Aggregating languages...")
lang_bytes: dict[str, int] = {}
lang_color: dict[str, str] = {}
for repo in repos:
    for edge in repo["languages"]["edges"]:
        n = edge["node"]["name"]
        lang_bytes[n] = lang_bytes.get(n, 0) + edge["size"]
        lang_color[n] = edge["node"]["color"] or "#58a6ff"

total_bytes = sum(lang_bytes.values()) or 1
top_langs   = sorted(lang_bytes, key=lambda k: lang_bytes[k], reverse=True)[:8]
print(f"    Top: {', '.join(top_langs[:4])}")

# ── 4. SVG generation ─────────────────────────────────────────────────────────
print("[4/4] Writing SVGs...")

def make_svg(body: str, w: int, h: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">'
        f'<rect width="{w}" height="{h}" rx="8" fill="{BG}" '
        f'stroke="{BORDER}" stroke-width="0.8"/>'
        f'{body}'
        f'</svg>'
    )

def txt(x, y, content, fill=TEXT, size=10.5, weight=400, anchor="start"):
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'font-family="Fira Code,monospace" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}">{content}</text>'
    )

# github-stats.svg
W, H = 300, 180
rows = [
    ("⭐  Total Stars",       f"{stars:,}"),
    ("🔨  Total Commits",     f"{commits:,}"),
    ("🔀  Pull Requests",     f"{prs:,}"),
    ("🐛  Issues",            f"{issues:,}"),
    ("📦  Contributed Repos", f"{contribs:,}"),
    ("👥  Followers",         f"{followers:,}"),
]
b = txt(16, 26, f"⚡ {name}'s GitHub Stats", GREEN, 11, 700)
for i, (label, val) in enumerate(rows):
    yy = 48 + i * 20
    b += txt(16,   yy, label, DIM, 10.5)
    b += txt(W-16, yy, val,   TEXT, 10.5, 700, "end")
    b += f'<line x1="16" y1="{yy+5}" x2="{W-16}" y2="{yy+5}" stroke="#1a2a1a" stroke-width="0.4"/>'

with open("github-stats.svg", "w", encoding="utf-8") as f:
    f.write(make_svg(b, W, H))
print("    ✅ github-stats.svg")

# github-langs.svg
LW, LH = 300, 180
BW = LW - 32
lb = txt(16, 26, "🧠 Most Used Languages", GREEN, 11, 700)

# coloured bar strip
x_off = 16
for lang in top_langs:
    seg = max(2, int(BW * lang_bytes[lang] / total_bytes))
    c   = lang_color[lang]
    lb += f'<rect x="{x_off}" y="36" width="{seg}" height="7" fill="{c}" rx="1"/>'
    x_off += seg
lb += f'<rect x="16" y="36" width="{BW}" height="7" rx="3" fill="none" stroke="#333" stroke-width="0.4"/>'

# legend (2 columns)
cw = (LW - 32) // 2
for idx, lang in enumerate(top_langs):
    col = idx % 2
    row = idx // 2
    lx  = 16 + col * cw
    ly  = 36 + 24 + row * 22
    pct = round(lang_bytes[lang] / total_bytes * 100, 1)
    c   = lang_color[lang]
    lb += f'<circle cx="{lx+6}" cy="{ly-4}" r="4" fill="{c}"/>'
    lb += txt(lx+14,   ly, lang[:14],  TEXT, 10)
    lb += txt(lx+cw-4, ly, f"{pct}%", DIM,  10, 400, "end")

with open("github-langs.svg", "w", encoding="utf-8") as f:
    f.write(make_svg(lb, LW, LH))
print("    ✅ github-langs.svg")

print(f"\n✅ All done — Commits: {commits:,}  Stars: {stars}  Top lang: {top_langs[0] if top_langs else 'n/a'}")