import re
import subprocess
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

import httpx


GITHUB_REPO = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


class ForgeError(RuntimeError):
    pass


def validate_github_url(url: str) -> Tuple[str, str, str]:
    match = GITHUB_REPO.fullmatch(url.strip())
    if not match:
        raise ForgeError("Use a public repository URL in the form https://github.com/owner/repository")
    owner, repo = match.groups()
    return owner, repo, f"https://github.com/{owner}/{repo}.git"


def search_repositories(query: str, limit: int = 6) -> List[Dict]:
    if not query.strip():
        raise ForgeError("Enter what you want the skill to do.")
    try:
        response = httpx.get(
            "https://api.github.com/search/repositories",
            params={"q": f"{query.strip()} language:Python archived:false", "sort": "stars", "per_page": min(limit, 10)},
            headers={"Accept": "application/vnd.github+json", "User-Agent": "Jays-AI-Control-Room"},
            timeout=15,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 403:
            raise ForgeError("GitHub's public search limit was reached. Wait a few minutes and try again.") from exc
        raise ForgeError(f"GitHub search returned an error ({exc.response.status_code}).") from exc
    except httpx.RequestError as exc:
        raise ForgeError("GitHub could not be reached. Check your connection and try again.") from exc
    return [
        {
            "name": item["full_name"],
            "url": item["html_url"],
            "description": item.get("description") or "No description supplied.",
            "stars": item.get("stargazers_count", 0),
            "updated": item.get("updated_at", "Unknown"),
            "license": (item.get("license") or {}).get("spdx_id") or "Not declared",
        }
        for item in response.json().get("items", [])
    ]


def clone_to_quarantine(url: str, root: Path = Path("data/quarantine")) -> Tuple[Path, str]:
    owner, repo, clone_url = validate_github_url(url)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{owner}-{repo}-{uuid.uuid4().hex[:8]}"
    command = [
        "git", "-c", "core.hooksPath=/dev/null", "-c", "protocol.file.allow=never",
        "clone", "--bare", "--depth", "1", "--filter=blob:limit=1048576", "--no-tags",
        clone_url, str(destination),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ForgeError("The repository could not be quarantined safely.") from exc
    if result.returncode != 0:
        raise ForgeError("The public repository could not be downloaded. Check the URL and repository visibility.")
    revision = subprocess.run(
        ["git", f"--git-dir={destination}", "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=5, check=True,
    ).stdout.strip()
    return destination, revision

