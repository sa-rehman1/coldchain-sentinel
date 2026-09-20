"""Reject accidentally tracked environment files without printing their contents."""

import subprocess
from shutil import which


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
    prohibited = [
        path
        for path in result.stdout.splitlines()
        if (path == ".env" or path.startswith(".env.")) and path != ".env.example"
    ]
    if prohibited:
        locations = ", ".join(prohibited)
        raise SystemExit(f"tracked environment files detected: {locations}")
    print("No prohibited environment files are tracked.")


if __name__ == "__main__":
    main()
