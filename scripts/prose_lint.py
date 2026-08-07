#!/usr/bin/env python3
"""Enforce the house prose style from README.md principle 9 and section 17.

Four rules: no em or en dashes, no contractions, no unfilled placeholders, and no
indefinite article errors. The fourth is here on evidence rather than principle: the grep
pass on A1 found one in a document two careful readings had called clean.

Design decisions that determine whether this survives contact with real work:

Files come from ``git ls-files`` rather than a tree walk, so vendored, generated, and
untracked content cannot trip it.

Fenced code blocks are exempt from the contraction and article rules but still checked for
placeholders. A contraction inside a shell transcript is data, not prose; a ``TODO`` inside
one is still unfinished work. Inline code spans are stripped before the prose rules run,
for the same reason.

Every violation is reported with ``file:line:column`` and the offending text. A linter that
reports a count without locating anything gets switched off the first time it is
inconvenient.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Fixtures deliberately contain violations so the linter can be tested against them.
EXCLUDED_PREFIXES = ("tests/fixtures/",)

EM_DASH = "—"
EN_DASH = "–"

# An explicit list, not an apostrophe heuristic. Possessives are legitimate prose and a
# false positive on one would discredit the whole check.
CONTRACTIONS = [
    "aren't",
    "can't",
    "couldn't",
    "didn't",
    "doesn't",
    "don't",
    "hadn't",
    "hasn't",
    "haven't",
    "he'd",
    "he'll",
    "he's",
    "here's",
    "how's",
    "i'd",
    "i'll",
    "i'm",
    "i've",
    "isn't",
    "it'd",
    "it'll",
    "it's",
    "let's",
    "mightn't",
    "mustn't",
    "shan't",
    "she'd",
    "she'll",
    "she's",
    "shouldn't",
    "that'd",
    "that's",
    "there'd",
    "there's",
    "they'd",
    "they'll",
    "they're",
    "they've",
    "wasn't",
    "we'd",
    "we'll",
    "we're",
    "we've",
    "weren't",
    "what's",
    "where's",
    "who's",
    "won't",
    "wouldn't",
    "you'd",
    "you'll",
    "you're",
    "you've",
]
CONTRACTION_RE = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in CONTRACTIONS) + r")\b",
    re.IGNORECASE,
)

PLACEHOLDER_RE = re.compile(
    r"\b(TODO|FIXME|TBD|XXX|HACK)\b|<(?:placeholder|fill[ _-]?me|your[ _-]\w+)>",
    re.IGNORECASE,
)

# Letters whose spoken name begins with a vowel sound, so an initialism starting with one
# takes "an": an SLA, an HTTP endpoint, an MRI, an RFC, an XML document.
VOWEL_SOUND_LETTERS = set("AEFHILMNORSX")

# Words spelled with an initial consonant but spoken with a vowel sound.
VOWEL_SOUND_WORDS = {"hour", "hours", "honest", "honestly", "heir", "honor", "honour"}

# Words spelled with an initial vowel but spoken with a consonant sound, so they take "a".
CONSONANT_SOUND_WORDS = {
    "one",
    "once",
    "euro",
    "european",
    "ubiquitous",
    "unanimous",
    "uniform",
    "union",
    "unique",
    "uniquely",
    "unit",
    "unite",
    "united",
    "universal",
    "universe",
    "university",
    "usable",
    "usage",
    "use",
    "used",
    "useful",
    "user",
    "users",
    "using",
    "usual",
    "usually",
    "utility",
    "utilities",
}

ARTICLE_RE = re.compile(r"\b(a|an)\s+([A-Za-z][\w'-]*)", re.IGNORECASE)

INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
# Markdown link targets and bare URLs contain hyphens and words that read as violations.
URL_RE = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    column: int
    rule: str
    text: str
    hint: str

    def render(self) -> str:
        return f"{self.path}:{self.line}:{self.column}: {self.rule}: {self.text}\n    {self.hint}"


def tracked_markdown_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        path
        for path in result.stdout.splitlines()
        if path and not path.startswith(EXCLUDED_PREFIXES)
    ]


def strip_prose_noise(line: str) -> str:
    """Blank out inline code and URLs, preserving column positions."""

    def blank(match: re.Match[str]) -> str:
        return " " * len(match.group(0))

    return URL_RE.sub(blank, INLINE_CODE_RE.sub(blank, line))


def check_articles(path: str, lineno: int, prose: str) -> list[Violation]:
    found: list[Violation] = []
    for match in ARTICLE_RE.finditer(prose):
        article = match.group(1)
        word = match.group(2)

        # Pronunciation is decided by the first component of a hyphenated compound: the
        # article in "a one-row update" agrees with "one", not with "one-row". Without this
        # the compound misses the allowlists and falls through to the spelling heuristic.
        head = word.split("-", 1)[0]
        if not head:
            continue
        lowered = head.lower()
        first = head[0]

        # Treat an all-capitals token as an initialism spoken letter by letter.
        is_initialism = head.isupper() and len(head) > 1
        if is_initialism:
            takes_an = first.upper() in VOWEL_SOUND_LETTERS
        elif lowered in VOWEL_SOUND_WORDS:
            takes_an = True
        elif lowered in CONSONANT_SOUND_WORDS:
            takes_an = False
        else:
            takes_an = first.lower() in "aeiou"

        used_an = article.lower() == "an"
        if used_an == takes_an:
            continue

        correct = "an" if takes_an else "a"
        found.append(
            Violation(
                path=path,
                line=lineno,
                column=match.start(1) + 1,
                rule="article",
                text=match.group(0),
                hint=f"read as beginning with a {'vowel' if takes_an else 'consonant'} "
                f"sound, so use '{correct}'",
            )
        )
    return found


def check_file(path: str, content: str) -> list[Violation]:
    found: list[Violation] = []
    in_fence = False

    for lineno, raw in enumerate(content.splitlines(), start=1):
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            continue

        # Placeholders are checked everywhere, including inside code.
        for match in PLACEHOLDER_RE.finditer(raw):
            found.append(
                Violation(
                    path=path,
                    line=lineno,
                    column=match.start() + 1,
                    rule="placeholder",
                    text=match.group(0),
                    hint="the definition of done forbids unfilled placeholders on main",
                )
            )

        if in_fence:
            continue

        prose = strip_prose_noise(raw)

        for index, char in enumerate(prose):
            if char in (EM_DASH, EN_DASH):
                name = "em dash" if char == EM_DASH else "en dash"
                found.append(
                    Violation(
                        path=path,
                        line=lineno,
                        column=index + 1,
                        rule="dash",
                        text=char,
                        hint=f"principle 9 forbids the {name}; use a colon, a semicolon, "
                        "parentheses, or two sentences",
                    )
                )

        for match in CONTRACTION_RE.finditer(prose):
            found.append(
                Violation(
                    path=path,
                    line=lineno,
                    column=match.start() + 1,
                    rule="contraction",
                    text=match.group(0),
                    hint="principle 9 requires full forms",
                )
            )

        found.extend(check_articles(path, lineno, prose))

    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "paths",
        nargs="*",
        help="files to check; defaults to every tracked Markdown file",
    )
    args = parser.parse_args(argv)

    paths = args.paths or tracked_markdown_files()
    if not paths:
        print("prose_lint: no Markdown files to check", file=sys.stderr)
        return 0

    violations: list[Violation] = []
    for path in paths:
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = REPO_ROOT / path
        if not resolved.exists():
            print(f"prose_lint: {path}: no such file", file=sys.stderr)
            return 2
        violations.extend(check_file(path, resolved.read_text(encoding="utf-8")))

    if not violations:
        print(f"prose_lint: {len(paths)} file(s) clean")
        return 0

    for violation in violations:
        print(violation.render())

    by_rule: dict[str, int] = {}
    for violation in violations:
        by_rule[violation.rule] = by_rule.get(violation.rule, 0) + 1
    summary = ", ".join(f"{count} {rule}" for rule, count in sorted(by_rule.items()))
    print(f"\nprose_lint: {len(violations)} violation(s) across {len(paths)} file(s): {summary}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
