from __future__ import annotations

from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class DocumentationTests(unittest.TestCase):
    def test_local_markdown_links_exist(self) -> None:
        missing: list[str] = []
        for document in (REPO_ROOT / "docs").rglob("*.md"):
            for target in LINK.findall(document.read_text(encoding="utf-8")):
                if (
                    "://" in target
                    or target.startswith("#")
                    or target.startswith("mailto:")
                ):
                    continue
                path = target.split("#", 1)[0]
                if path and not (document.parent / path).resolve().exists():
                    missing.append(f"{document.relative_to(REPO_ROOT)} -> {target}")
        for document in (REPO_ROOT / "README.md", REPO_ROOT / "AGENTS.md"):
            for target in LINK.findall(document.read_text(encoding="utf-8")):
                if "://" not in target and not target.startswith("#"):
                    path = target.split("#", 1)[0]
                    if path and not (document.parent / path).resolve().exists():
                        missing.append(
                            f"{document.relative_to(REPO_ROOT)} -> {target}"
                        )
        self.assertEqual(missing, [])

    def test_public_guides_are_not_version_named(self) -> None:
        public = [
            REPO_ROOT / "README.md",
            REPO_ROOT / "docs/README.md",
            REPO_ROOT / "docs/guides/install.md",
            REPO_ROOT / "docs/guides/using-the-rom.md",
        ]
        version = re.compile(r"v\d+\.\d+\.\d+")
        found = [
            str(path.relative_to(REPO_ROOT))
            for path in public
            if version.search(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
