# xWiki

xWiki is a personal LLM-maintained knowledge base inspired by Andrej Karpathy's
LLM Wiki pattern.

The goal is to build a persistent, compounding wiki instead of a pile of files
that must be rediscovered from scratch every time. Raw sources stay immutable;
the LLM reads them, extracts useful knowledge, and maintains a structured
markdown wiki with links, summaries, citations, contradictions, and evolving
synthesis pages.

## Structure

```text
_inbox/    New material waiting to be ingested.
_raw/      Source material after ingestion begins; cited by the wiki.
_wiki/     Generated knowledge: summaries, concepts, entities, syntheses, logs.
_schema/   Operating rules: workflows, page conventions, citation style.
.tools/    Deterministic maintenance utilities.
```

## Principles

- `_inbox` is the visible queue of material that has not been ingested yet.
- `_raw` is the source of truth for material that has entered the wiki. Files
  here should be read and cited, not edited.
- `_wiki` is the compiled knowledge layer. The LLM owns and maintains these pages.
- Ingest has two modes: exhaustive ingest processes every readable,
  non-duplicate source in a requested queue; curated ingest first scores and
  selects candidates before full ingest.
- Dynamic topic clustering is a separate maintenance workflow, not part of
  ordinary ingest. Use it only when explicitly reorganizing the wiki structure.
- Wiki pages should be written in English. For non-English sources, translate
  extracted claims, summaries, and analysis into English while preserving the
  original title, author names, URLs, and source paths in metadata.
- Entity pages are selective anchors for people, organizations, datasets,
  systems, institutions, and other named things worth tracking; paper authors
  do not become entity pages by default.
- Research paper ingests should capture method, mechanism, experiments, key
  figures/tables, implementation notes when available, novelty, limitations,
  future work, and related-work position in English.
- `_schema` defines the rules that keep the wiki consistent across sessions.
- Useful answers should be saved back into the wiki when they create durable value.
- Run deterministic health and lint checks after broad maintenance when the
  structure or page content may have drifted.
- The wiki should be periodically linted for stale claims, missing links,
  contradictions, orphan pages, and open research questions.

## Basic Workflow

1. Add new sources to `_inbox`.
2. Ask the LLM to ingest the inbox.
3. The LLM moves each source into `_raw`, reads it, creates or updates wiki
   pages, adds citations and cross-links, updates the index, and records the
   activity in the log.
4. Browse the result in Obsidian, ask follow-up questions, and save valuable
   analyses back into `_wiki`.

For planned future work, see `PLAN.md`.

## How To Use

Most maintenance happens by asking an LLM agent to operate on this vault. Start
from the root of the repo and use short, explicit requests like these.

### Exhaustive Ingest

Use this when every readable, non-duplicate file in `_inbox/` should enter the
wiki.

```text
ingest inbox
```

Expected behavior:

- Move accepted files from `_inbox/` to `_raw/`.
- Read the sources and write source summaries in `_wiki/sources/`.
- Create or update relevant concept, entity, topic, question, or synthesis pages.
- Cite `_raw/` paths for factual claims.
- Update `_wiki/log.md`.
- Run `python3 .tools/health.py` and `python3 .tools/lint.py` when changes are
  meaningful.

### Curated Ingest

Use this when `_inbox/` contains candidates and the agent should decide what is
worth ingesting now.

```text
curated ingest inbox
```

The phrase `inbox curated ingest` is also acceptable. Expected behavior:

- Score candidate sources before moving them into `_raw/`.
- Classify candidates as `ingest-now`, `defer`, `reject`, or `duplicate`.
- Fully ingest only `ingest-now` sources.
- Leave deferred or rejected sources in `_inbox/` unless the schema says
  otherwise.
- Keep concise decisions in `_wiki/log.md`; put detailed scoring in
  `_wiki/log-full.md` when needed.

### Ask Questions

Use this when you want an answer grounded in the existing wiki.

```text
what does the wiki say about agent memory evaluation?
compare Mem0 and AMA-Bench
summarize the PARNI research line
```

The agent should read `_wiki/index.md`, search related wiki pages, cite existing
wiki/source evidence, and preserve uncertainty. If the answer is durable, ask:

```text
save this as a question page
save this as a synthesis
```

### Organize The Wiki

Use this only when you explicitly want taxonomy or directory structure changes.
Ordinary ingest should not reorganize the whole wiki.

```text
organize the AI agents and memory topic
recluster the statistics pages
run a taxonomy pass for agent memory
```

Expected behavior:

- Use only `L0`, `L1`, and `L2` topic levels.
- Keep `_wiki/index.md` linked to L0 topics only.
- Move pages and raw files only when citations and wikilinks can be preserved.
- Run `python3 .tools/health.py`.
- Record the taxonomy pass in `_wiki/log.md`.

### Health Check

Use this after broad edits, ingest, or taxonomy changes.

```text
run health check
```

Equivalent command:

```bash
python3 .tools/health.py
```

The health check reports pending inbox files, stub pages, broken wikilinks,
index sync problems, log coverage, and raw-source coverage.

### Lint Check

Use this after source-page edits, broad ingest, or taxonomy changes.

```bash
python3 -m pip install -r requirements.txt
python3 .tools/lint.py
```

Lint parses YAML and Markdown, then checks page schema, citation coverage, raw
references, duplicate identities and aliases, wikilinks, and L0/L1/L2 topic
rules. Use `--json` for automation or `--fix-status` to conservatively mark
failing active pages as `needs-review`.

### Convert Hard-To-Read Sources

Use this when a source is hard to inspect directly.

```bash
python3 .tools/file_to_md.py path/to/source.pdf
```

Converted markdown is a helper artifact. The original file remains the source
of provenance unless the schema says otherwise.

## Maintenance Commands

```bash
python3 .tools/health.py
python3 .tools/lint.py
python3 .tools/file_to_md.py path/to/source.pdf
```

`health.py` performs deterministic structural checks with no LLM calls.
`lint.py` performs deterministic YAML, Markdown, citation, identity, link, and
taxonomy checks with no LLM calls.
`file_to_md.py` optionally converts rich source formats into markdown companions
for easier ingest.

## Starter Files To Add

- `AGENTS.md`: root pointer that tells LLM agents to read the schema.
- `_schema/AGENTS.md`: the main operating contract for LLM maintainers.
- `_schema/page-types.md`: standard wiki page types and recommended sections.
- `_schema/ingest-workflow.md`: exact process for adding new sources.
- `_schema/source-selection-workflow.md`: curated ingest scoring and decision records.
- `_schema/citation-style.md`: lightweight provenance and uncertainty rules.
- `_schema/lint-workflow.md`: periodic wiki health-check process.
- `_schema/health-workflow.md`: deterministic structural checks.
- `_schema/taxonomy-workflow.md`: dynamic topic hierarchy and directory layout rules.
- `_schema/query-workflow.md`: answering and saving durable wiki questions.
- `_schema/conversion-workflow.md`: optional markdown conversion for rich inputs.
- `_wiki/index.md`: a content-oriented catalog of wiki pages.
- `_wiki/log.md`: a chronological record of ingests, queries, and maintenance.
- `_wiki/overview.md`: a human-readable map of what this wiki currently knows.
