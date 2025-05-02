Evaluation & QA System – Product Requirements Document (PRD)

Version 1.0 | Last updated 2025-05-02

⸻

1 Background & Problem Statement

Groove Jones now generates thousands of transcripts, translations, and subtitles across three core languages (EN, DE, HE). Quality gaps—­missing files, silent chunks, untranslated passages—slow downstream delivery and erode client trust. A lightweight Evaluation & QA System is needed to:
	•	guarantee every deliverable exists and is non-empty,
	•	surface language or format mismatches early,
	•	grow into a deep-quality scoring engine without a ground-up rewrite.

⸻

2 Objectives

#	Objective	Success metric (MVP)	Future metric (vNext)
1	Detect missing / empty transcript, translation, and subtitle files.	0% undetected missing files in weekly audit.	SLA: auto-alert within 10 min of file creation.
2	Flag language mismatches in translations (e.g. German inside English).	≤ 1% false-positives, ≤ 0.1% misses on sample set.	Per-segment accuracy > 99%.
3	Provide machine-readable pass/fail status for CI/CD gating.	CLI exit ≠ 0 when any check fails.	GitHub Action with annotated diff comments.
4	Foundation for granular quality scoring (semantic & timing) powered by GPT-4.1.	Modular evaluator interface in place.	Segment-level BLEURT-style scores surfaced in dashboard.



⸻

3 Scope

3.1 In-Scope (MVP)
	•	Discovery: iterate over DB rows returned by DatabaseManager.get_files_by_status("*").
	•	Existence check for each expected artefact:
transcripts/*.txt, translations/<lang>/*.txt, subtitles/<lang>/*.srt.
	•	Non-empty check ( > 10 bytes by default, configurable).
	•	Basic language-ID check on every translation file (fast heuristic via langdetect).
	•	CLI tool evaluate_quality.py:

python evaluate_quality.py --all
python evaluate_quality.py --file-id=<UUID>
python evaluate_quality.py --json-out=report.json


	•	Summary report (stdout + optional JSON):
	•	totals, failures by type, elapsed time.
	•	Return code:
	•	0 = all checks passed,
	•	1 = any missing/empty file,
	•	2 = language mismatch,
	•	>2 = internal error.

3.2 Out-of-Scope (MVP)
	•	Semantic fidelity scoring.
	•	Timing alignment validation (subtitle vs. audio).
	•	Web UI or dashboards.
	•	Auto-correction workflows.

⸻

4 User Stories

ID	As a …	I want …	So that …
U-01	Release engineer	to run one command that validates all deliverables before packaging	I never ship incomplete assets
U-02	Localization PM	a per-file JSON report with failure reasons	I can assign fixes to the right team
U-03	DevOps engineer	a non-zero CLI exit code in CI	the pipeline halts on quality regressions
U-04	QA analyst (future)	segment-level confidence flags	I focus review time on risky passages



⸻

5 Detailed Requirements

5.1 Functional

#	Requirement	Priority
F-01	CLI accepts --all, --file-id, --limit, --json-out	Must
F-02	For each DB row, derive expected artefact paths using FileManager helpers	Must
F-03	Mark Missing, Empty, Language-Mismatch, or OK per artefact	Must
F-04	Persist evaluation result back to DB (qa_status, qa_errors[])	Should
F-05	JSON output structure: root summary + array of per-file results	Must
F-06	Config file (qa_config.yaml) to tweak size-threshold, languages, exit-code mapping	Should

5.2 Non-Functional

Item	Target
Runtime	≤ 2 min per 1 000 media rows (SSD, langdetect)
Concurrency	Up to 4 parallel worker threads
CPU / RAM	≤ 1 GB even on 10 k files
Security	Read-only FS access; no external network calls in MVP
Logging	Structured (jsonlines) with timestamps and severity

5.3 Interfaces & Data

{
  "file_id": "uuid",
  "checks": {
    "transcript":    "missing|empty|ok",
    "translation_en":"ok",
    "translation_de":"empty",
    "translation_he":"lang_mismatch",
    "subtitle_en":   "ok"
  },
  "fail_reasons": ["translation_de_empty", "translation_he_lang_mismatch"],
  "evaluated_at": "2025-05-02T23:15:04Z"
}



⸻

6 Technical Architecture

flowchart TD
    subgraph Pipeline
      A[DB rows\n(media)] -->|batch| B[Evaluator CLI]
      B --> C[File IO checks]
      C --> D[Lang-ID module]
      D --> E{Pass?}
      E -->|No| F[Write QA errors → DB]
      E -->|Yes| G[Write qa_status=passed]
      B --> H[JSON / stdout report]
    end

	•	Lang-ID: langdetect (fast) → fallback future GPT-4.1 classifier.
	•	Worker pool: Python concurrent.futures.ThreadPoolExecutor(max_workers=4).

⸻

7 Acceptance Criteria (MVP)
	1.	Running python evaluate_quality.py --file-id=<goodFile> returns exit 0.
	2.	Deleting one translation file flips exit code to 1; JSON lists "translation_en_missing".
	3.	Replacing 100 bytes in de translation with English triggers exit 2.
	4.	Processing 1 000 mixed files finishes in under 2 minutes on M2 Pro laptop.
	5.	DB row gains qa_status='failed', qa_errors=['subtitle_he_empty'] when issue found.

⸻

8 Milestones & Timeline

Date	Milestone
May 10	Config schema + stub CLI scaffolding merged
May 17	File-exist/size checks + DB writes
May 24	Language-ID check + JSON reporting
May 28	Load/perf tests, arg-parsing polish
May 31	MVP GA – integrated into main CI pipeline



⸻

9 Future Roadmap (vNext → Q3 2025)

Area	Feature
Semantic QA	GPT-4.1 powered segment-pair scoring; BLEU / COMET fallback
Timing QA	Subtitle vs. transcript vs. audio offset diff (PyDub + ASR peaks)
Confidence Heat-map	Visual HTML/React dashboard with color-coded segments
Auto-requeue	Failed artefacts automatically returned to the translation queue
Alerting	Slack / Email hooks on QA failures above configurable threshold



⸻

10 Risks & Mitigations

Risk	Impact	Mitigation
High false-positives from langdetect on short sentences	Wasted manual review time	minimum-chars threshold 50; future GPT classifier
Slow I/O on shared NAS	SLA miss	async batching + per-host cache warm-up
Growing language list breaks heuristic lists	undetected mismatches	Config-driven allowed ISO codes



⸻

11 Open Questions
	1.	Should we treat empty subtitle files as critical (exit 1) or warn-only?
	2.	Where should the JSON report be archived (S3, DB blob)?
	3.	Do we need PII redaction checks as part of quality gate?

Owner to resolve by May 8.

⸻

Authored by: Product Ops | Reviewers: Localization Engineering, DevOps, QA