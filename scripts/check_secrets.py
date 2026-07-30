#!/usr/bin/env python3
"""Fail CI when source files appear to contain committed credentials."""

import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "node_modules", ".next", "dist", "build", "__pycache__"}
SKIP_NAMES = {".env"}
SKIP_SUFFIXES = {
    ".avif",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".lock",
    ".pdf",
    ".png",
    ".pyc",
    ".svg",
    ".webp",
    ".woff",
    ".woff2",
}
SUSPICIOUS_FILE_SUFFIXES = {".key", ".p12", ".pfx", ".pem"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "known token prefix": re.compile(
        r"\b(?:AKIA[0-9A-Z]{16}|gh[oprsu]_[A-Za-z0-9_]{30,}|"
        r"xox[baprs]-[A-Za-z0-9-]{20,}|sk-[A-Za-z0-9_-]{24,})\b"
    ),
    "credential assignment": re.compile(
        r"""(?ix)
        \b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|
        private[_-]?key|secret[_-]?key|password)\b
        \s*[:=]\s*["']?([A-Za-z0-9_./+=-]{24,})
        """
    ),
    "bearer token": re.compile(r"(?i)\bBearer\s+([A-Za-z0-9_./+=-]{32,})"),
}


def entropy(value: str) -> float:
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def iter_source_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.name in SKIP_NAMES or (
            path.name.startswith(".env.") and path.name != ".env.example"
        ):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        yield path


def main() -> int:
    findings: list[tuple[Path, int, str]] = []
    for path in iter_source_files():
        relative = path.relative_to(ROOT)
        if path.suffix.lower() in SUSPICIOUS_FILE_SUFFIXES:
            findings.append((relative, 1, "credential-like file"))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS.items():
                match = pattern.search(line)
                if match is None:
                    continue
                candidate = match.group(1) if match.lastindex else match.group(0)
                if label in {"credential assignment", "bearer token"} and entropy(candidate) < 3:
                    continue
                findings.append((relative, line_number, label))

    if not findings:
        print("Secret scan passed.")
        return 0
    print("Potential committed credentials found (values intentionally redacted):")
    for path, line_number, label in findings:
        print(f"- {path}:{line_number}: {label}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
