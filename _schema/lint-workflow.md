# Lint Workflow

Use this workflow after ingest, broad content edits, or taxonomy maintenance.
Health and lint are separate deterministic gates:

```bash
python3 .tools/health.py
python3 .tools/lint.py
```

Install lint dependencies once per Python environment:

```bash
python3 -m pip install -r requirements.txt
```

`health.py` checks queue and graph-wide structural coverage. `lint.py` parses
YAML and Markdown to validate individual pages and their references. Neither
command makes LLM calls.

## Deterministic Checks

`python3 .tools/lint.py` checks:

- required frontmatter fields, page types, statuses, and ISO dates
- list types for `tags`, `sources`, and optional `aliases`
- optional page IDs and aliases for duplicate or ambiguous identities
- H1 titles and page-type directory placement
- existence and containment of frontmatter raw sources and body citations
- source-level citations in factual research sections such as `Summary`,
  `Research Problem`, `Method`, `Experiments`, and `Key Results`
- unresolved or ambiguous wikilinks while ignoring links inside code fences
- topic paths and `Child Topics` links across the fixed L0/L1/L2 hierarchy
- root-index coverage for every L0 topic

Section-level citation lint is a minimum provenance gate. It does not prove that
every sentence is supported or that a cited page range is correct.

Useful variants:

```bash
python3 .tools/lint.py --json
python3 .tools/lint.py --save
python3 .tools/lint.py --fix-status
```

`--fix-status` only changes an `active` page with lint errors to
`needs-review` and updates its `updated` date. It never promotes a page to
`active`; promotion requires review after the underlying problem is fixed.

Lint exits with a non-zero status when errors remain, so it can be used in CI.

## Semantic Review

After deterministic checks pass:

1. Read `_wiki/index.md` and `_wiki/log.md`.
2. Search for markers such as `Needs source:`, `Open question:`,
   `Contradiction:`, and `TODO`.
3. Inspect likely stale claims, weak citations, accidental duplicates, missing
   concepts, and contradictions that require source interpretation.
4. Make small fixes directly when the evidence is clear.
5. For larger conceptual issues, create a durable question or synthesis only
   when it contributes knowledge rather than recording routine maintenance.
6. Append meaningful lint and repair work to `_wiki/log.md`.

## Log Format

```markdown
## [YYYY-MM-DD] lint | Wiki health check

- Checked: brief scope.
- Fixed: pages or links changed.
- Found: issues that still need attention.
```
