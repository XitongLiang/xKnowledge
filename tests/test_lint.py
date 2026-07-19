from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / ".tools" / "lint.py"
SPEC = importlib.util.spec_from_file_location("xwiki_lint", MODULE_PATH)
assert SPEC and SPEC.loader
LINT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LINT
SPEC.loader.exec_module(LINT)


def frontmatter(page_type: str, *, status: str = "active", extra: str = "") -> str:
    return (
        "---\n"
        f"type: {page_type}\n"
        f"status: {status}\n"
        "created: 2026-07-15\n"
        "updated: 2026-07-15\n"
        "tags: []\n"
        "sources: []\n"
        f"{extra}"
        "---\n\n"
    )


class LintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "_wiki").mkdir()
        (self.root / "_raw").mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write(self, relative_path: str, content: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def issue_codes(self) -> list[str]:
        _, issues = LINT.lint_vault(self.root)
        return [issue.code for issue in issues]

    def test_valid_source_page_passes(self) -> None:
        self.write("_raw/paper.pdf", "fixture")
        self.write(
            "_wiki/sources/Paper.md",
            frontmatter("source").replace("sources: []", 'sources: ["_raw/paper.pdf"]')
            + "# Paper\n\n## Summary\n\nA supported claim. Source: `_raw/paper.pdf`.\n",
        )

        self.assertEqual([], self.issue_codes())

    def test_missing_section_citation_is_an_error(self) -> None:
        self.write("_raw/paper.pdf", "fixture")
        self.write(
            "_wiki/sources/Paper.md",
            frontmatter("source").replace("sources: []", 'sources: ["_raw/paper.pdf"]')
            + "# Paper\n\n## Summary\n\nAn unsupported claim.\n",
        )

        self.assertIn("citation_section_missing", self.issue_codes())

    def test_duplicate_ids_and_aliases_are_errors(self) -> None:
        page_a = frontmatter("concept", extra='id: duplicate\naliases: ["Shared"]\n') + "# First\n"
        page_b = frontmatter("concept", extra='id: duplicate\naliases: ["Shared"]\n') + "# Second\n"
        self.write("_wiki/concepts/First.md", page_a)
        self.write("_wiki/concepts/Second.md", page_b)

        codes = self.issue_codes()
        self.assertIn("id_duplicate", codes)
        self.assertIn("alias_ambiguous", codes)

    def test_missing_raw_file_is_an_error(self) -> None:
        self.write(
            "_wiki/sources/Paper.md",
            frontmatter("source").replace("sources: []", 'sources: ["_raw/missing.pdf"]')
            + "# Paper\n\n## Summary\n\nClaim. Source: `_raw/missing.pdf`.\n",
        )

        codes = self.issue_codes()
        self.assertIn("raw_source_missing", codes)
        self.assertIn("raw_citation_missing", codes)

    def test_code_fence_wikilink_is_ignored(self) -> None:
        self.write(
            "_wiki/concepts/Example.md",
            frontmatter("concept") + "# Example\n\n```markdown\n[[Missing Page]]\n```\n",
        )

        self.assertNotIn("wikilink_unresolved", self.issue_codes())

    def test_invalid_topic_child_level_is_an_error(self) -> None:
        self.write(
            "_wiki/topics/l0/Root.md",
            frontmatter("topic") + "# Root\n\n## Child Topics\n\n- [[Leaf]]\n",
        )
        self.write(
            "_wiki/topics/l2/domain/Leaf.md",
            frontmatter("topic") + "# Leaf\n",
        )

        self.assertIn("topic_child_level_invalid", self.issue_codes())

    def test_root_index_rejects_content_page_links(self) -> None:
        self.write(
            "_wiki/index.md",
            frontmatter("index") + "# Index\n\n- [[Concept]]\n",
        )
        self.write(
            "_wiki/concepts/Concept.md",
            frontmatter("concept") + "# Concept\n",
        )

        self.assertIn("index_target_invalid", self.issue_codes())

    def test_fix_status_only_demotes_error_pages(self) -> None:
        broken = self.write(
            "_wiki/sources/Broken.md",
            frontmatter("source").replace("sources: []", 'sources: ["_raw/missing.pdf"]')
            + "# Broken\n\n## Summary\n\nUnsupported.\n",
        )
        pages, issues = LINT.lint_vault(self.root)

        updated = LINT.mark_needs_review(pages, issues)

        self.assertEqual(["_wiki/sources/Broken.md"], updated)
        self.assertIn("status: needs-review", broken.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
