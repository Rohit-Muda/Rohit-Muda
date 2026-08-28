"""
Fetches live GitHub stats for USERNAME and writes dark_mode.svg / light_mode.svg
from the templates/ folder, replacing {{placeholders}} with real numbers.

Runs inside GitHub Actions using the built-in GITHUB_TOKEN — no manual secret needed.
"""

import os
import datetime
import requests

USERNAME = os.environ.get("GH_USERNAME", "Rohit-Muda")
TOKEN = os.environ["GH_TOKEN"]  # provided by the workflow as GITHUB_TOKEN

HEADERS = {"Authorization": f"bearer {TOKEN}"}
GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"


def rest_get(path):
    r = requests.get(f"{REST_URL}{path}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def graphql(query, variables=None):
    r = requests.post(GRAPHQL_URL, headers=HEADERS,
                       json={"query": query, "variables": variables or {}})
    r.raise_for_status()
    return r.json()["data"]


def get_profile():
    return rest_get(f"/users/{USERNAME}")


def get_total_stars():
    stars, page = 0, 1
    while True:
        repos = rest_get(f"/users/{USERNAME}/repos?per_page=100&page={page}")
        if not repos:
            break
        stars += sum(r["stargazers_count"] for r in repos)
        page += 1
    return stars


def get_total_commits(created_at):
    """Sums commit contributions year-by-year since account creation."""
    start_year = int(created_at[:4])
    current_year = datetime.datetime.now().year
    total = 0
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          restrictedContributionsCount
        }
      }
    }
    """
    for year in range(start_year, current_year + 1):
        data = graphql(query, {
            "login": USERNAME,
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year}-12-31T23:59:59Z",
        })
        cc = data["user"]["contributionsCollection"]
        total += cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
    return total


def uptime_since(created_at):
    created = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
    delta = datetime.datetime.utcnow() - created
    years = delta.days // 365
    months = (delta.days % 365) // 30
    return f"{years} years, {months} months"


def render_template(path, values):
    with open(path, "r", encoding="utf-8") as f:
        svg = f.read()
    for key, val in values.items():
        svg = svg.replace(f"{{{{{key}}}}}", str(val))
    return svg


def main():
    profile = get_profile()
    values = {
        "followers": profile["followers"],
        "public_repos": profile["public_repos"],
        "stars": get_total_stars(),
        "commits": get_total_commits(profile["created_at"]),
        "uptime": uptime_since(profile["created_at"]),
        "username": USERNAME,
        "updated": datetime.date.today().isoformat(),
    }

    for mode in ("dark_mode", "light_mode"):
        rendered = render_template(f"templates/{mode}.svg", values)
        with open(f"{mode}.svg", "w", encoding="utf-8") as f:
            f.write(rendered)

    print("Generated SVGs with:", values)


if __name__ == "__main__":
    main()
