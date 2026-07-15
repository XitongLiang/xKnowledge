# xWiki Future Work Plan

This document describes likely future work for xWiki. It is a roadmap, not an
operating rulebook. Current maintenance rules live in `_schema/`.

## Direction

xWiki should become a lightweight, open-source LLM-maintained wiki template for
turning raw personal or research material into a persistent linked knowledge
base. The core value is not one more note-taking app. The value is a repeatable
workflow where an LLM agent can ingest sources, preserve provenance, maintain
links, answer questions from the wiki, and gradually improve the structure over
time.

The project should stay file-based, transparent, and easy to inspect in
Obsidian or any Markdown editor.

## Near-Term Work

### 1. Stabilize The Public Template

- Keep the repo clean for open-source use.
- Separate private vault content from reusable template files.
- Make the default directory structure easy to understand:
  `_inbox/`, `_raw/`, `_wiki/`, `_schema/`, `.tools/`.
- Keep `README.md`, `AGENTS.md`, and `_schema/` aligned.
- Add small examples that demonstrate the intended workflow without exposing
  private notes or raw source files.

### 2. Improve Ingest Quality

- Keep two ingest modes:
  - exhaustive ingest: every readable, non-duplicate source is accepted;
  - curated ingest: candidate sources are scored before being accepted.
- Improve duplicate detection using title normalization, arXiv IDs, DOI, URL,
  file hash, and semantic similarity.
- Make source pages more consistent across papers, blogs, webpages, books,
  transcripts, and user notes.
- Add stronger support for non-English input while keeping generated wiki pages
  in English.
- Preserve short selection decisions in `_wiki/log.md` and detailed scoring in
  `_wiki/log-full.md`.

### 3. Add Online Source Discovery

- Add an optional workflow for searching papers, blogs, documentation, and
  webpages before curated ingest.
- Keep search-based ingest separate from inbox ingest so the agent does not
  silently import low-quality sources.
- Require source selection records for search-based ingest.
- Prefer primary sources for technical topics: papers, official docs,
  repositories, and project pages.

### 4. Strengthen Taxonomy And Graph Navigation

- Keep the fixed topic depth: `L0`, `L1`, and `L2`.
- Continue using `_wiki/index.md` as a clean root that links only L0 topics.
- Make topic pages local maps rather than full sitemaps.
- Add periodic taxonomy passes for branches that become hard to scan.
- Improve graph readability by keeping logs, workspace files, and operational
  pages out of the conceptual graph.

## Medium-Term Work

### 5. Better Query And Synthesis Workflows

- Make wiki-grounded question answering more reliable.
- Save durable answers as question pages or synthesis pages when they add
  lasting value.
- Track uncertainty, contradictions, and stale claims explicitly.
- Build stronger synthesis pages for major research threads.
- Add comparison templates for related papers, methods, systems, and concepts.

### 6. Search And Retrieval Database

Add an optional local database layer for search and retrieval.

The database should be an index over the Markdown vault, not the primary source
of truth. `_raw/`, `_wiki/`, and `_schema/` should remain readable and usable
without the database.

Core indexes:

- full-text search over wiki pages, source summaries, headings, tags, and raw
  metadata
- vector search over chunks, pages, concepts, and synthesis pages
- structured metadata tables for page type, topic path, source path, created
  date, updated date, tags, and outbound links
- graph edges for wikilinks, source citations, topic membership, and related
  concepts

Recommended first implementation:

- SQLite as the local database
- SQLite FTS5 for lexical search
- a vector table or companion vector index for embeddings
- deterministic rebuild command from Markdown files
- incremental update command based on file mtime or content hash

Query design:

- combine FTS and vector retrieval with a simple hybrid ranker
- filter by page type, topic path, source, date, and language
- preserve provenance by returning file paths, headings, and source citations
- use retrieved pages as context for LLM answers, not as hidden memory

Important constraints:

- generated answers should still cite Markdown pages and raw source paths
- deleting the database should not delete knowledge
- private content should not be exported accidentally through the index
- embedding models and dimensions should be recorded for reproducibility

Open design choices:

- whether to store vectors in SQLite or a separate local vector index
- page-level versus chunk-level embeddings
- how to rank graph-neighbor pages together with lexical/vector results
- whether raw PDFs should be embedded directly or only through source pages and
  extracted markdown helpers

### 7. Local Coding Agent Memory

Develop xWiki into a memory layer for local coding agents.

Possible memory units:

- project facts
- user preferences
- debugging histories
- recurring commands
- repository-specific workflows
- decisions and rejected alternatives
- reusable coding skills

The key research question is how a coding agent should decide what to remember,
what to retrieve, what to forget, and when a memory should become a skill.

Candidate techniques:

- graph-based memory over files, tasks, commits, errors, and decisions
- Bayesian or probabilistic models for deciding which memory is relevant
- trajectory summarization from coding sessions
- retrieval with recency, frequency, and task similarity signals
- skill extraction for repeated workflows
- human approval for high-impact persistent memories

### 8. Distributed Collaborative Memory

Explore a separate project direction for distributed agent memory across users,
teams, or platforms.

The core idea is that memories learned in one context should not be broadcast
blindly. They should be abstracted, classified, filtered, and distributed only
when they are useful and safe for another user or environment.

Important problems:

- memory abstraction from specific experience into reusable pattern
- privacy-preserving filtering
- user- and platform-specific routing
- trust, provenance, and consent
- conflict resolution between local and shared memories
- evaluation of whether shared memories improve downstream behavior

Possible models:

- classification models for memory type and target audience
- probabilistic routing models for deciding who should receive a memory
- graph models for propagating memory through related users, projects, and
  task types
- feedback loops that demote or remove harmful shared memories

### 9. Skill Layer

Add a first-class skill layer inspired by systems such as AutoSkill.

Potential design:

- store reusable operating patterns as explicit Markdown skills
- give each skill triggers, scope, examples, version, provenance, and safety
  notes
- retrieve skills during wiki maintenance or coding-agent work
- distinguish facts, preferences, procedures, and executable tools
- require review before a new skill changes future behavior broadly

This should stay separate from source pages. A source page explains what a
paper says. A skill tells an agent how to act.

## Tooling Work

### 10. Deterministic Maintenance Tools

Implemented in `.tools/lint.py`:

- frontmatter schema and lifecycle validation
- raw-source and body-citation path validation
- section-level source citation coverage
- duplicate page ID and alias detection
- unresolved and ambiguous wikilinks
- topic location, child-level, and root L0 index validation

Continue improving `.tools/` with checks that do not require an LLM:

- orphan pages
- log coverage
- duplicate source candidates
- stale pages
- language-policy violations
- private-file leakage before open-source commits

### 11. Conversion And Extraction

Improve helper tools for hard-to-read sources:

- PDF to Markdown conversion
- metadata extraction
- DOI/arXiv detection
- table extraction when useful
- image or figure extraction for paper notes
- webpage capture with provenance

The original raw file should remain the source of truth unless the schema
explicitly says otherwise.

### 12. Obsidian Experience

Keep Obsidian support useful but optional.

Possible improvements:

- graph settings that emphasize `_wiki/` content
- homepage widgets for wiki, graph, todo, and reading list entry points
- CSS snippets for clean reading and homepage layout
- conventions for excluding workspace, log, and private files from graph views

Do not make the project depend on a specific Obsidian plugin.

## Evaluation

xWiki needs simple ways to tell whether it is improving.

Useful signals:

- fewer duplicate pages
- fewer broken links
- more source-backed answers
- better retrieval of relevant prior notes
- fewer stale or contradictory claims
- faster ingest with the same quality
- more useful synthesis pages
- less manual cleanup after agent maintenance

For coding-agent memory, evaluation should include whether the agent makes
fewer repeated mistakes, follows project conventions better, and needs fewer
reminders from the user.

## Non-Goals

- Do not turn xWiki into a heavy database-first system.
- Do not hide provenance behind opaque embeddings.
- Do not require a cloud service for the basic workflow.
- Do not make every mention into an entity page.
- Do not let ordinary ingest reorganize the entire taxonomy.
- Do not store private raw sources in the public template repository.

## Open Questions

- What is the smallest useful public example vault?
- How much automation should happen before human review?
- Should skills live inside `_schema/`, `_wiki/`, or a separate `_skills/`
  directory?
- How should xWiki represent confidence, contradiction, and source quality?
- Should graph-based memory become part of xWiki itself or remain a separate
  coding-agent memory project?
- How should online search be constrained so curated ingest stays high quality?
