import subprocess

from src.security.github import ForgeError, validate_github_url
from src.security.scanner import scan_repository


def make_repo(tmp_path, files):
    repo = tmp_path / "candidate"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    for name, content in files.items():
        (repo / name).write_text(content)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
    return repo / ".git"


def test_github_url_allowlist():
    assert validate_github_url("https://github.com/acme/skill")[:2] == ("acme", "skill")
    try:
        validate_github_url("https://evil.example/repo")
        assert False
    except ForgeError:
        pass


def test_scanner_blocks_secret_and_destructive_code(tmp_path):
    repo = make_repo(tmp_path, {"LICENSE": "MIT", "skill.py": "token='ghp_abcdefghijklmnopqrstuvwxyz1234567890'\nimport os\nos.system('rm -rf /tmp/example')"})
    report = scan_repository(repo)
    assert report.verdict == "Blocked"
    assert report.counts["critical"] >= 2


def test_clean_candidate_is_eligible(tmp_path):
    repo = make_repo(tmp_path, {"LICENSE": "MIT", "skill.py": "def clean(value):\n    return value.strip()\n"})
    report = scan_repository(repo)
    assert report.verdict == "Eligible for adaptation"

