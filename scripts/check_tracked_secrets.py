"""Conservative credential scan that reports locations, never matched values."""

import re
import subprocess
from pathlib import Path
from shutil import which

PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github-token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "openai-token": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "groq-token": re.compile(r"gsk_[A-Za-z0-9_-]{20,}"),
    "sql-literal-password": re.compile(r"(?i)\bPASSWORD\s*=\s*'(?!(?:\$\(|change-me-))[^']+'"),
}


def main() -> None:
    git = which("git")
    if git is None:
        raise SystemExit("git executable is required")
    result = subprocess.run(
        [git, "ls-files", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
    )
    findings: list[str] = []
    for name in result.stdout.splitlines():
        path = Path(name)
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{label}: {name}:{line_number}")
    if findings:
        raise SystemExit("Potential tracked credentials:\n" + "\n".join(findings))
    print("No high-confidence tracked credential patterns detected.")


if __name__ == "__main__":
    main()
