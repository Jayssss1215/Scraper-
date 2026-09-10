import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class Finding:
    severity: str
    check: str
    file: str
    detail: str


@dataclass
class ScanReport:
    revision: str
    files_scanned: int
    bytes_scanned: int
    license_status: str
    findings: List[Finding]

    @property
    def counts(self) -> Dict[str, int]:
        return {level: sum(f.severity == level for f in self.findings) for level in ("critical", "high", "medium", "info")}

    @property
    def verdict(self) -> str:
        if self.counts["critical"]:
            return "Blocked"
        if self.counts["high"]:
            return "Manual review required"
        return "Eligible for adaptation"

    def as_dict(self):
        return {
            "revision": self.revision,
            "files_scanned": self.files_scanned,
            "bytes_scanned": self.bytes_scanned,
            "license_status": self.license_status,
            "verdict": self.verdict,
            "counts": self.counts,
            "findings": [asdict(item) for item in self.findings],
        }


TEXT_SUFFIXES = {".py", ".js", ".ts", ".sh", ".toml", ".yaml", ".yml", ".json", ".txt", ".md", ".cfg", ".ini"}
MAX_FILES = 1500
MAX_BYTES = 8_000_000
MAX_FILE_BYTES = 750_000

RULES = [
    ("critical", "Destructive command", re.compile(r"rm\s+-rf|shutil\.rmtree\s*\(|os\.remove\s*\(|\.unlink\s*\("), "Can delete local data."),
    ("critical", "Credential access", re.compile(r"(?:\.ssh|\.aws/credentials|keychain|security\s+find-(?:generic|internet)-password|browser.*cookie)", re.I), "References sensitive credentials or browser data."),
    ("critical", "Obfuscated execution", re.compile(r"(?:base64\.b64decode|marshal\.loads).{0,160}(?:exec|eval)\s*\(", re.S), "Decodes data and executes it dynamically."),
    ("high", "Shell execution", re.compile(r"(?:os\.system|subprocess\.(?:run|Popen|call|check_output)|shell\s*=\s*True)"), "Can start local commands; inspect every call before adaptation."),
    ("high", "Dynamic code", re.compile(r"(?<![A-Za-z])(eval|exec)\s*\("), "Executes dynamically supplied code."),
    ("high", "Unsafe deserialization", re.compile(r"pickle\.loads?\s*\(|yaml\.load\s*\("), "May execute code when reading untrusted input."),
    ("medium", "Network access", re.compile(r"(?:requests\.|httpx\.|aiohttp\.|urllib\.request|socket\.)"), "Makes network requests; destinations and data flow need review."),
    ("medium", "Browser automation", re.compile(r"(?:selenium|playwright|pyppeteer|chromedriver)", re.I), "Automates a browser and may encounter access or terms restrictions."),
    ("medium", "Environment access", re.compile(r"(?:os\.environ|os\.getenv|dotenv)"), "Reads environment values; confirm it accesses only approved keys."),
]

SECRET_RULE = re.compile(r"(?:AIza[0-9A-Za-z_-]{25,}|gh[pousr]_[0-9A-Za-z]{30,}|sk-[0-9A-Za-z_-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", f"--git-dir={repo}", *args], capture_output=True, text=True,
        errors="replace", timeout=10, check=True,
    ).stdout


def scan_repository(repo: Path, revision: str = "HEAD") -> ScanReport:
    revision = _git(repo, "rev-parse", revision).strip()
    entries = []
    for line in _git(repo, "ls-tree", "-r", "-l", revision).splitlines():
        metadata, path = line.split("\t", 1)
        parts = metadata.split()
        size = int(parts[3]) if parts[3].isdigit() else 0
        entries.append((path, size, parts[0]))
    findings: List[Finding] = []
    if len(entries) > MAX_FILES:
        findings.append(Finding("critical", "Repository size", "repository", f"Contains {len(entries)} files; safety cap is {MAX_FILES}."))
    declared_license = next((path for path, _, _ in entries if Path(path).name.lower().startswith(("license", "copying"))), None)
    license_status = f"Declared in {declared_license}" if declared_license else "No license file found"
    if not declared_license:
        findings.append(Finding("high", "License", "repository", "No licence file was found; do not reuse code until usage rights are confirmed."))
    total = 0
    scanned = 0
    for path, size, mode in entries[:MAX_FILES]:
        if mode == "120000":
            findings.append(Finding("high", "Symbolic link", path, "Symlink requires a manual destination review."))
            continue
        if size > MAX_FILE_BYTES:
            findings.append(Finding("medium", "Large file", path, f"Skipped {size:,}-byte file."))
            continue
        if Path(path).suffix.lower() not in TEXT_SUFFIXES and Path(path).name not in {"Dockerfile", "Makefile"}:
            continue
        if total + size > MAX_BYTES:
            findings.append(Finding("critical", "Scan budget", "repository", "Text content exceeds the 8 MB safety scan cap."))
            break
        content = _git(repo, "show", f"{revision}:{path}")
        total += len(content.encode("utf-8", errors="ignore"))
        scanned += 1
        if SECRET_RULE.search(content):
            findings.append(Finding("critical", "Possible embedded secret", path, "A credential-shaped value was detected; its value is intentionally hidden."))
        if path == "package.json" and re.search(r'"(?:preinstall|install|postinstall)"\s*:', content):
            findings.append(Finding("high", "Install hook", path, "Defines a script that can run automatically during installation."))
        if Path(path).name == "requirements.txt":
            dependency_lines = [line.strip() for line in content.splitlines() if line.strip() and not line.lstrip().startswith(("#", "-"))]
            if any("==" not in line for line in dependency_lines):
                findings.append(Finding("medium", "Unpinned dependency", path, "At least one dependency can change between installs."))
        for severity, name, pattern, detail in RULES:
            if pattern.search(content):
                findings.append(Finding(severity, name, path, detail))
    return ScanReport(revision, scanned, total, license_status, findings)
