# Product Requirements Document – Enhanced Hebrew Translation Accuracy

_Last updated: 2025‑04‑20 06:30 CDT_

## 1  Purpose
Enable high‑quality, context‑aware Hebrew translations for all transcripts in the Bryan Rigg Scribe project, matching (or surpassing) English output fidelity and reducing manual post‑editing to &lt;3 % of segments.

## 2  Background / Problem Statement
The current pipeline supports English and other languages but has **no automated Hebrew path** (all rows show `translation_he_status = not_started`). Simple MT often mishandles proper nouns, RTL punctuation, and idioms, leading to low accuracy.

## 3  Goals & Success Metrics
| Goal | Metric | Target |
|------|--------|--------|
| Batch‑translate 100 % of files to Hebrew | `translation_he_status = completed` for 728/728 | 100 % |
| Improve accuracy vs raw Google | BLEU +5 / manual QA < 3 % error segments | ≥ 5‑pt gain |
| Minimise manual fixes | Avg < 15 sec edits per 1k chars | ≤ 0:15 |

## 4  User Stories
1. _Researcher_ wants readable Hebrew subtitles to share with Israeli historians.  
2. _QA reviewer_ needs a report flagging low‑confidence segments for quick verification.  
3. _Engineer_ wants a repeatable pipeline that defaults to the best provider.

## 5  Scope
### In‑scope
- Automatic Hebrew translation of all transcripts.
- Provider selection (Google vs Microsoft vs OpenAI fallback).
- Glossary / proper‑noun protection.
- Improved chunking (paragraph‑level).
- RTL punctuation post‑processing.
- Confidence score + flagging.
- CLI runner `process_translations.py --languages heb` integration.

### Out‑of‑scope (Phase 1)
- Human GUI editor.  
- Audio dubbing to Hebrew.

## 6  Functional Requirements
| # | Requirement |
|---|-------------|
| FR‑1 | System shall determine preferred provider for Hebrew via config (`provider_for['heb']`). |
| FR‑2 | System shall load `docs/hebrew_glossary.csv` and protect terms via placeholder swap. |
| FR‑3 | System shall translate in paragraph chunks (split on blank lines). |
| FR‑4 | If primary provider fails or returns non‑Hebrew text, system shall retry with OpenAI GPT‑4 prompt. |
| FR‑5 | System shall run heuristic post‑processing: fix punctuation, ensure RTL marks. |
| FR‑6 | System shall compute similarity between source and back‑translation; if below 0.80, mark segment `low_confidence`. |
| FR‑7 | QA report `hebrew_translation_report.csv` lists file_id, segments flagged. |

## 7  Non‑Functional Requirements
- Retry logic: max 3 attempts / provider.  
- Throughput: ≥ 120 k chars/min with Google batch API.  
- Cost tracking per provider.

## 8  Technical Design (High Level)
1. **Config** – add `language_profiles` section:
   ```yaml
   heb:
     provider: google
     chunk_size: paragraph
     glossary: docs/hebrew_glossary.csv
   ```
2. **Glossary Handler** – util replacing glossary matches with `[[G0]]`, `[[G1]]`,… before API call, restore after.
3. **Chunker** – splits transcript on `\n\n`.
4. **Provider Wrapper** – chooses translator, fallback chain.
5. **Post‑processor** – fixes punctuation & adds Unicode RTL mark `E` where needed.
6. **Confidence Scorer** – Google `detectLanguage` + back‑translate sample, compute BLEU.
7. **CLI Integration** – `process_translations.py --languages heb --batch-size 10`.

## 9  Milestones & Timeline
| Date | Deliverable |
|------|-------------|
| Apr 24 | Provider comparison report & decision |
| Apr 27 | Glossary v1 + placeholder utility |
| Apr 30 | Pipeline coding complete (FR‑1 → FR‑5) |
| May 03 | Confidence scorer & QA report (FR‑6 – FR‑7) |
| May 05 | First full run, QA sign‑off |

## 10  Risks & Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| Provider API quota limits | Med | High | Batch throttle, spread across keys |
| RTL post‑processing bugs | Med | Med | Unit tests with tricky samples |
| Glossary coverage gaps | High | Med | Allow dynamic glossary additions |

## 11  Open Questions
1. Preferred style for dates/numbers in Hebrew?  
2. Should glossary be shared with English or separate?

---
**Next Action**: approve PRD or leave comments, then we’ll start provider evaluation & glossary creation.
