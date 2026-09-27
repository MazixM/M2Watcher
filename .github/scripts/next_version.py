"""
Wylicza wersję kolejnego release'u.

Zasada:
* bazą jest ``__version__`` z ``app/version.py`` (tu podbijasz ręcznie wersję minor/major),
* jeśli release z tą wersją już istnieje, podbijamy patch ponad najwyższy istniejący tag.

Tagi mają format ``v.X.Y.Z`` (jak dotychczasowe v.1.0.0, v.1.0.1, v.2.0.0).

    python .github/scripts/next_version.py            # -> 2.0.1
    python .github/scripts/next_version.py --tags "v.1.0.0 v.2.0.0" --base 2.0.0
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = ROOT / "app" / "version.py"
TAG_RE = re.compile(r"^v\.?(\d+)\.(\d+)\.(\d+)$")

Version = Tuple[int, int, int]


def parse_tag(tag: str) -> Optional[Version]:
    m = TAG_RE.match(tag.strip())
    return tuple(int(x) for x in m.groups()) if m else None  # type: ignore[return-value]


def parse_version(text: str) -> Version:
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if not m:
        raise ValueError(f"Nie znaleziono wersji X.Y.Z w: {text!r}")
    return tuple(int(x) for x in m.groups())  # type: ignore[return-value]


def next_version(base: Version, tags: Iterable[str]) -> Version:
    existing = [v for v in (parse_tag(t) for t in tags) if v]
    if not existing:
        return base
    latest = max(existing)
    if base > latest:
        return base
    return (latest[0], latest[1], latest[2] + 1)


def git_tags() -> list:
    out = subprocess.run(["git", "tag", "--list"], cwd=ROOT, capture_output=True, text=True, check=True)
    return out.stdout.split()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", help="wersja bazowa (domyślnie z app/version.py)")
    parser.add_argument("--tags", help="lista tagów oddzielona spacjami (domyślnie z git)")
    args = parser.parse_args()
    base = parse_version(args.base or VERSION_FILE.read_text(encoding="utf-8"))
    tags = args.tags.split() if args.tags is not None else git_tags()
    print(".".join(map(str, next_version(base, tags))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
