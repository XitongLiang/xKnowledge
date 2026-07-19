#!/usr/bin/env python3
"""Deterministic schema and content lint checks for xWiki."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

try:
    import yaml
    from markdown_it import MarkdownIt
except ImportError as exc:  # pragma: no cover - exercised only in incomplete environments.
    raise SystemExit(
        "xWiki lint dependencies are missing. Install them with: "
        "python3 -m pip install -r requirements.txt"
    ) from exc


VALID_TYPES = {
    "topic",
    "concept",
    "entity",
    "source",
    "synthesis",
    "question",
    "timeline",
    "index",
    "log",
}
VALID_STATUSES = {"draft", "active", "needs-review"}
REQUIRED_FIELDS = ("type", "status", "created", "updated", "tags", "sources")
REPORT_NAMES = {"health-report.md", "lint-report.md", "graph-report.md"}
CITATION_REQUIRED_SECTIONS = {
    "summary",
    "key claims",
    "research problem",
    "method",
    "method structure",
    "mechanism analysis",
    "experiments",
    "key results",
    "key figures or tables",
    "novelty",
}
TYPE_DIRECTORIES = {
    "topic": "topics",
    "concept": "concepts",
    "entity": "entities",
    "source": "sources",
    "synthesis": "syntheses",
    "question": "questions",
    "timeline": "timelines",
}
INDEX_ALLOWED_NON_TOPIC = {"overview.md"}
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    message: str
    line: int | None = None


@dataclass(frozen=True)
class LinkRef:
    target: str
    line: int
    section: str


@dataclass
class Section:
    name: str
    line: int
    has_content: bool = False
    raw_paths: set[str] = field(default_factory=set)
    links: list[LinkRef] = field(default_factory=list)


@dataclass
class Page:
    path: Path
    relative_path: str
    content: str
    body: str
    body_line_offset: int
    metadata: dict[str, Any]
    frontmatter_valid: bool
    title: str
    page_type: str
    status: str
    aliases: list[str]
    page_id: str
    sections: dict[str, Section]
    links: list[LinkRef]
    body_raw_paths: dict[str, int]


def normalize_name(value: str) -> str:
    value = value.strip().split("|", 1)[0].split("#", 1)[0]
    value = value.removesuffix(".md")
    return re.sub(r"\s+", " ", value).casefold()


def normalize_heading(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def line_for_text(content: str, value: str) -> int | None:
    for line_number, line in enumerate(content.splitlines(), start=1):
        if value in line:
            return line_number
    return None


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str, int, bool, str | None, int | None]:
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, content, 0, False, "YAML frontmatter is missing.", 1

    closing_index = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if closing_index is None:
        return {}, content, 0, False, "YAML frontmatter is not closed.", 1

    raw_frontmatter = "".join(lines[1:closing_index])
    try:
        parsed = yaml.safe_load(raw_frontmatter)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        error_line = mark.line + 2 if mark is not None else 2
        return {}, "".join(lines[closing_index + 1 :]), closing_index + 1, False, str(exc), error_line

    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        return {}, "".join(lines[closing_index + 1 :]), closing_index + 1, False, (
            "YAML frontmatter must be a mapping."
        ), 2

    return parsed, "".join(lines[closing_index + 1 :]), closing_index + 1, True, None, None


def inline_text(token: Any) -> str:
    children = token.children or []
    return "".join(child.content for child in children if child.type not in {"code_inline", "html_inline"})


def inline_raw_paths(token: Any) -> set[str]:
    paths: set[str] = set()
    for child in token.children or []:
        if child.type != "code_inline":
            continue
        value = child.content.strip()
        if value.startswith("_raw/"):
            paths.add(value)
    return paths


def parse_markdown(body: str, body_line_offset: int) -> tuple[str, dict[str, Section], list[LinkRef], dict[str, int]]:
    tokens = MarkdownIt("commonmark").parse(body)
    sections: dict[str, Section] = {}
    links: list[LinkRef] = []
    body_raw_paths: dict[str, int] = {}
    current_section = ""
    first_h1 = ""

    for index, token in enumerate(tokens):
        if token.type == "heading_open" and index + 1 < len(tokens):
            heading_token = tokens[index + 1]
            heading = heading_token.content.strip()
            line = body_line_offset + (token.map[0] if token.map else 0) + 1
            if token.tag == "h1" and not first_h1:
                first_h1 = heading
            if token.tag == "h2":
                current_section = normalize_heading(heading)
                sections[current_section] = Section(name=heading, line=line)
            continue

        if token.type != "inline" or (index > 0 and tokens[index - 1].type == "heading_open"):
            continue

        line = body_line_offset + (token.map[0] if token.map else 0) + 1
        raw_paths = inline_raw_paths(token)
        for raw_path in raw_paths:
            body_raw_paths.setdefault(raw_path, line)

        text = inline_text(token)
        token_links = [
            LinkRef(target=match, line=line, section=current_section)
            for match in WIKILINK_RE.findall(text)
        ]
        links.extend(token_links)

        if current_section:
            section = sections[current_section]
            section.has_content = section.has_content or bool(token.content.strip())
            section.raw_paths.update(raw_paths)
            section.links.extend(token_links)

    return first_h1, sections, links, body_raw_paths


def parse_page(root: Path, path: Path, issues: list[Issue]) -> Page:
    content = path.read_text(encoding="utf-8")
    relative_path = path.relative_to(root).as_posix()
    metadata, body, offset, valid, error, error_line = parse_frontmatter(content)
    if error:
        issues.append(Issue("error", "frontmatter_invalid", relative_path, error, error_line))

    first_h1, sections, links, body_raw_paths = parse_markdown(body, offset)
    metadata_title = metadata.get("title") if isinstance(metadata.get("title"), str) else ""
    title = metadata_title.strip() or first_h1 or path.stem

    raw_aliases = metadata.get("aliases", [])
    aliases: list[str] = []
    if isinstance(raw_aliases, list) and all(isinstance(alias, str) for alias in raw_aliases):
        aliases = [alias.strip() for alias in raw_aliases if alias.strip()]
    elif "aliases" in metadata:
        issues.append(
            Issue(
                "error",
                "aliases_invalid",
                relative_path,
                "`aliases` must be a list of strings.",
                line_for_text(content, "aliases:"),
            )
        )

    page_id = metadata.get("id", "")
    if page_id and not isinstance(page_id, str):
        issues.append(
            Issue(
                "error",
                "id_invalid",
                relative_path,
                "`id` must be a string.",
                line_for_text(content, "id:"),
            )
        )
        page_id = ""

    page = Page(
        path=path,
        relative_path=relative_path,
        content=content,
        body=body,
        body_line_offset=offset,
        metadata=metadata,
        frontmatter_valid=valid,
        title=title,
        page_type=metadata.get("type", "") if isinstance(metadata.get("type"), str) else "",
        status=metadata.get("status", "") if isinstance(metadata.get("status"), str) else "",
        aliases=aliases,
        page_id=page_id.strip() if isinstance(page_id, str) else "",
        sections=sections,
        links=links,
        body_raw_paths=body_raw_paths,
    )
    validate_page_schema(root, page, issues, first_h1)
    validate_raw_paths(root, page, issues)
    validate_citation_sections(page, issues)
    return page


def valid_iso_date(value: Any) -> bool:
    if isinstance(value, date):
        return True
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))


def validate_page_schema(root: Path, page: Page, issues: list[Issue], first_h1: str) -> None:
    if not page.frontmatter_valid:
        return

    for field_name in REQUIRED_FIELDS:
        if field_name not in page.metadata:
            issues.append(
                Issue(
                    "error",
                    "field_missing",
                    page.relative_path,
                    f"Required field `{field_name}` is missing.",
                )
            )

    if page.page_type not in VALID_TYPES:
        issues.append(
            Issue(
                "error",
                "type_invalid",
                page.relative_path,
                f"Unknown page type `{page.metadata.get('type', '')}`.",
                line_for_text(page.content, "type:"),
            )
        )
    if page.status not in VALID_STATUSES:
        issues.append(
            Issue(
                "error",
                "status_invalid",
                page.relative_path,
                f"Unknown page status `{page.metadata.get('status', '')}`.",
                line_for_text(page.content, "status:"),
            )
        )

    for field_name in ("created", "updated"):
        if field_name in page.metadata and not valid_iso_date(page.metadata[field_name]):
            issues.append(
                Issue(
                    "error",
                    "date_invalid",
                    page.relative_path,
                    f"`{field_name}` must use YYYY-MM-DD.",
                    line_for_text(page.content, f"{field_name}:"),
                )
            )

    created = page.metadata.get("created")
    updated = page.metadata.get("updated")
    if valid_iso_date(created) and valid_iso_date(updated):
        created_date = created if isinstance(created, date) else date.fromisoformat(created)
        updated_date = updated if isinstance(updated, date) else date.fromisoformat(updated)
        if updated_date < created_date:
            issues.append(
                Issue(
                    "error",
                    "date_order_invalid",
                    page.relative_path,
                    "`updated` is earlier than `created`.",
                )
            )

    for field_name in ("tags", "sources"):
        value = page.metadata.get(field_name)
        if field_name in page.metadata and (
            not isinstance(value, list) or not all(isinstance(item, str) for item in value)
        ):
            issues.append(
                Issue(
                    "error",
                    f"{field_name}_invalid",
                    page.relative_path,
                    f"`{field_name}` must be a list of strings.",
                    line_for_text(page.content, f"{field_name}:"),
                )
            )

    if not first_h1:
        issues.append(Issue("error", "title_missing", page.relative_path, "Page must contain an H1 title."))

    relative_to_wiki = page.path.relative_to(root / "_wiki")
    expected_directory = TYPE_DIRECTORIES.get(page.page_type)
    if expected_directory and (
        not relative_to_wiki.parts or relative_to_wiki.parts[0] != expected_directory
    ):
        if not (page.page_type == "synthesis" and relative_to_wiki.as_posix() == "overview.md"):
            issues.append(
                Issue(
                    "error",
                    "type_location_invalid",
                    page.relative_path,
                    f"Pages of type `{page.page_type}` belong under `_wiki/{expected_directory}/`.",
                )
            )


def safe_raw_path(root: Path, raw_path: str) -> Path | None:
    candidate = (root / raw_path).resolve()
    raw_root = (root / "_raw").resolve()
    if not candidate.is_relative_to(raw_root):
        return None
    return candidate


def validate_raw_paths(root: Path, page: Page, issues: list[Issue]) -> None:
    sources = page.metadata.get("sources", [])
    frontmatter_raw_paths = [source for source in sources if isinstance(source, str) and source.startswith("_raw/")]

    if page.page_type == "source" and not frontmatter_raw_paths:
        issues.append(
            Issue(
                "error",
                "source_provenance_missing",
                page.relative_path,
                "Source page frontmatter must list at least one `_raw/` file.",
            )
        )

    for raw_path in frontmatter_raw_paths:
        candidate = safe_raw_path(root, raw_path)
        line = line_for_text(page.content, raw_path)
        if candidate is None:
            issues.append(
                Issue(
                    "error",
                    "raw_path_invalid",
                    page.relative_path,
                    f"Raw source escapes `_raw/`: `{raw_path}`.",
                    line,
                )
            )
        elif not candidate.is_file():
            issues.append(
                Issue(
                    "error",
                    "raw_source_missing",
                    page.relative_path,
                    f"Frontmatter source does not exist: `{raw_path}`.",
                    line,
                )
            )

    validates_body_citations = page.page_type in {
        "concept",
        "entity",
        "source",
        "synthesis",
        "question",
        "timeline",
    }
    for raw_path, line in page.body_raw_paths.items():
        if not validates_body_citations or raw_path.endswith("/"):
            continue
        candidate = safe_raw_path(root, raw_path)
        if candidate is None:
            issues.append(
                Issue(
                    "error",
                    "raw_path_invalid",
                    page.relative_path,
                    f"Raw citation escapes `_raw/`: `{raw_path}`.",
                    line,
                )
            )
        elif not candidate.is_file():
            issues.append(
                Issue(
                    "error",
                    "raw_citation_missing",
                    page.relative_path,
                    f"Cited raw source does not exist: `{raw_path}`.",
                    line,
                )
            )


def validate_citation_sections(page: Page, issues: list[Issue]) -> None:
    if page.page_type != "source":
        return

    evidence_sections = [
        section
        for name, section in page.sections.items()
        if name in CITATION_REQUIRED_SECTIONS and section.has_content
    ]
    if not evidence_sections:
        issues.append(
            Issue(
                "warning",
                "evidence_sections_missing",
                page.relative_path,
                "Source page has no recognized evidence sections.",
            )
        )
        return

    for section in evidence_sections:
        if not section.raw_paths:
            issues.append(
                Issue(
                    "error",
                    "citation_section_missing",
                    page.relative_path,
                    f"Section `{section.name}` has factual content but no `_raw/` citation.",
                    section.line,
                )
            )


def page_aliases(root: Path, page: Page) -> set[str]:
    relative_to_wiki = page.path.relative_to(root / "_wiki").as_posix()
    candidates = {
        page.path.stem,
        page.title,
        page.relative_path,
        relative_to_wiki,
        page.relative_path.removesuffix(".md"),
        relative_to_wiki.removesuffix(".md"),
        *page.aliases,
    }
    return {normalized for candidate in candidates if (normalized := normalize_name(candidate))}


def validate_duplicate_identity(root: Path, pages: list[Page], issues: list[Issue]) -> dict[str, list[Page]]:
    ids: dict[str, list[Page]] = defaultdict(list)
    aliases: dict[str, list[Page]] = defaultdict(list)
    for page in pages:
        if page.page_id:
            ids[page.page_id.casefold()].append(page)
        for alias in page_aliases(root, page):
            aliases[alias].append(page)

    for page_id, matches in ids.items():
        if len(matches) < 2:
            continue
        paths = ", ".join(page.relative_path for page in matches)
        for page in matches:
            issues.append(
                Issue(
                    "error",
                    "id_duplicate",
                    page.relative_path,
                    f"Page id `{page_id}` is duplicated across: {paths}.",
                )
            )

    for alias, matches in aliases.items():
        unique_matches = {page.relative_path: page for page in matches}
        if len(unique_matches) < 2:
            continue
        paths = ", ".join(sorted(unique_matches))
        for page in unique_matches.values():
            issues.append(
                Issue(
                    "error",
                    "alias_ambiguous",
                    page.relative_path,
                    f"Name or alias `{alias}` resolves to multiple pages: {paths}.",
                )
            )

    return aliases


def resolve_link(target: str, aliases: dict[str, list[Page]]) -> list[Page]:
    normalized = normalize_name(target)
    unique = {page.relative_path: page for page in aliases.get(normalized, [])}
    return list(unique.values())


def topic_level(root: Path, page: Page) -> str:
    relative = page.path.relative_to(root / "_wiki")
    if len(relative.parts) >= 2 and relative.parts[0] == "topics" and relative.parts[1] in {"l0", "l1", "l2"}:
        return relative.parts[1]
    return ""


def validate_links_and_taxonomy(
    root: Path,
    pages: list[Page],
    aliases: dict[str, list[Page]],
    issues: list[Issue],
) -> None:
    for page in pages:
        for link in page.links:
            matches = resolve_link(link.target, aliases)
            if not matches:
                issues.append(
                    Issue(
                        "error",
                        "wikilink_unresolved",
                        page.relative_path,
                        f"Wikilink does not resolve: `[[{link.target}]]`.",
                        link.line,
                    )
                )
            elif len(matches) > 1:
                paths = ", ".join(sorted(match.relative_path for match in matches))
                issues.append(
                    Issue(
                        "error",
                        "wikilink_ambiguous",
                        page.relative_path,
                        f"Wikilink `[[{link.target}]]` is ambiguous: {paths}.",
                        link.line,
                    )
                )

        level = topic_level(root, page)
        if page.page_type == "topic" and not level:
            issues.append(
                Issue(
                    "error",
                    "topic_level_invalid",
                    page.relative_path,
                    "Topic page must live under `_wiki/topics/l0`, `l1`, or `l2`.",
                )
            )
        if level and page.page_type != "topic":
            issues.append(
                Issue(
                    "error",
                    "topic_type_invalid",
                    page.relative_path,
                    "Files under `_wiki/topics/` must use `type: topic`.",
                )
            )

        child_section = page.sections.get("child topics")
        if not level or not child_section:
            continue
        expected_level = {"l0": "l1", "l1": "l2", "l2": ""}[level]
        for link in child_section.links:
            matches = resolve_link(link.target, aliases)
            if len(matches) != 1:
                continue
            child = matches[0]
            child_level = topic_level(root, child)
            if child.page_type != "topic" or child_level != expected_level:
                expected = expected_level.upper() if expected_level else "no child topic"
                issues.append(
                    Issue(
                        "error",
                        "topic_child_level_invalid",
                        page.relative_path,
                        f"`[[{link.target}]]` is in `Child Topics`; expected {expected}.",
                        link.line,
                    )
                )

    index_page = next((page for page in pages if page.relative_path == "_wiki/index.md"), None)
    if index_page:
        linked_l0: set[str] = set()
        for link in index_page.links:
            matches = resolve_link(link.target, aliases)
            if len(matches) != 1:
                continue
            target = matches[0]
            if topic_level(root, target) == "l0":
                linked_l0.add(target.relative_path)
            elif target.path.name not in INDEX_ALLOWED_NON_TOPIC:
                issues.append(
                    Issue(
                        "error",
                        "index_target_invalid",
                        index_page.relative_path,
                        "Root index may link only L0 topics or approved operational pages; "
                        f"found `[[{link.target}]]`.",
                        link.line,
                    )
                )

        for page in pages:
            if topic_level(root, page) == "l0" and page.relative_path not in linked_l0:
                issues.append(
                    Issue(
                        "error",
                        "index_l0_missing",
                        index_page.relative_path,
                        f"L0 topic is missing from the root index: `[[{page.title}]]`.",
                    )
                )


def lint_vault(root: Path) -> tuple[list[Page], list[Issue]]:
    root = root.resolve()
    wiki_dir = root / "_wiki"
    issues: list[Issue] = []
    if not wiki_dir.is_dir():
        return [], [Issue("error", "wiki_missing", "_wiki", "Wiki directory does not exist.")]

    paths = sorted(path for path in wiki_dir.rglob("*.md") if path.name not in REPORT_NAMES)
    pages = [parse_page(root, path, issues) for path in paths]
    aliases = validate_duplicate_identity(root, pages, issues)
    validate_links_and_taxonomy(root, pages, aliases, issues)
    issues.sort(key=lambda issue: (issue.severity != "error", issue.path, issue.line or 0, issue.code))
    return pages, issues


def replace_frontmatter_value(content: str, key: str, value: str) -> str:
    lines = content.splitlines(keepends=True)
    closing_index = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if closing_index is None:
        return content
    pattern = re.compile(rf"^({re.escape(key)}:\s*).*$")
    for index in range(1, closing_index):
        line_without_newline = lines[index].rstrip("\r\n")
        match = pattern.match(line_without_newline)
        if not match:
            continue
        newline = "\r\n" if lines[index].endswith("\r\n") else "\n"
        lines[index] = f"{match.group(1)}{value}{newline}"
        break
    return "".join(lines)


def mark_needs_review(pages: list[Page], issues: list[Issue]) -> list[str]:
    error_paths = {issue.path for issue in issues if issue.severity == "error"}
    updated_paths: list[str] = []
    for page in pages:
        if page.relative_path not in error_paths or page.status != "active" or not page.frontmatter_valid:
            continue
        content = replace_frontmatter_value(page.content, "status", "needs-review")
        content = replace_frontmatter_value(content, "updated", date.today().isoformat())
        if content != page.content:
            page.path.write_text(content, encoding="utf-8")
            updated_paths.append(page.relative_path)
    return updated_paths


def result_dict(root: Path, pages: list[Page], issues: list[Issue], status_updates: list[str]) -> dict[str, Any]:
    errors = sum(issue.severity == "error" for issue in issues)
    warnings = sum(issue.severity == "warning" for issue in issues)
    return {
        "date": date.today().isoformat(),
        "root": root.resolve().as_posix(),
        "pages_scanned": len(pages),
        "errors": errors,
        "warnings": warnings,
        "status_updates": status_updates,
        "issues": [asdict(issue) for issue in issues],
    }


def format_report(result: dict[str, Any]) -> str:
    lines = [
        f"# xWiki Lint Report - {result['date']}",
        "",
        f"Scanned {result['pages_scanned']} wiki pages. Errors: {result['errors']}. Warnings: {result['warnings']}.",
        "",
    ]

    if result["status_updates"]:
        lines.extend([f"## Status Updates ({len(result['status_updates'])})", ""])
        lines.extend(f"- `{path}` -> `needs-review`" for path in result["status_updates"])
        lines.append("")

    for severity in ("error", "warning"):
        matching = [issue for issue in result["issues"] if issue["severity"] == severity]
        lines.extend([f"## {severity.title()}s ({len(matching)})", ""])
        if not matching:
            lines.extend([f"No {severity}s found.", ""])
            continue
        for issue in matching:
            location = issue["path"]
            if issue["line"] is not None:
                location = f"{location}:{issue['line']}"
            lines.append(f"- `{issue['code']}` `{location}` - {issue['message']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic xWiki schema and content lint checks.")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Vault root. Defaults to the repository root.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--save", action="store_true", help="Save markdown report to _wiki/lint-report.md.")
    parser.add_argument(
        "--fix-status",
        action="store_true",
        help="Mark active pages with lint errors as needs-review. Never auto-promotes pages.",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    pages, issues = lint_vault(root)
    status_updates: list[str] = []
    if args.fix_status:
        status_updates = mark_needs_review(pages, issues)
        if status_updates:
            pages, issues = lint_vault(root)

    result = result_dict(root, pages, issues, status_updates)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        report = format_report(result)
        print(report, end="")
        if args.save:
            report_path = root / "_wiki" / "lint-report.md"
            report_path.write_text(report, encoding="utf-8")
            print(f"\nSaved: {report_path.relative_to(root).as_posix()}")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
