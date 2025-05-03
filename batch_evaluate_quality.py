#!/usr/bin/env python3
"""
Batch evaluate translation quality via GPT-4 and store results in the database.
"""
import argparse
import logging
import sys
from db_manager import DatabaseManager

# Import Hebrew evaluator
try:
    from scripts.evaluate_hebrew_quality import evaluate as eval_hebrew
except ImportError:
    eval_hebrew = None

# Placeholder for future EN/DE evaluators
# from scripts.evaluate_english_quality import evaluate as eval_en
# from scripts.evaluate_german_quality import evaluate as eval_de


def get_evaluator(lang: str):
    if lang == "he" and eval_hebrew:
        return lambda fid, model: eval_hebrew(fid, model)
    # elif lang == "en" and eval_en:
    #     return lambda fid, model: eval_en(fid, model)
    # elif lang == "de" and eval_de:
    #     return lambda fid, model: eval_de(fid, model)
    else:
        raise NotImplementedError(f"No evaluator implemented for language '{lang}'")


def main():
    parser = argparse.ArgumentParser(description="Batch evaluate translation quality.")
    parser.add_argument("--db", default="media_tracking.db", help="Path to SQLite DB file")
    parser.add_argument("--languages", default="he", help="Comma-separated list of languages (e.g. he,en,de)")
    parser.add_argument("--model", default="gpt-4.1", help="OpenAI model to use")
    parser.add_argument("--threshold", type=float, default=8.5, help="Passing score threshold")
    parser.add_argument("--limit", type=int, help="Max files per language")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    db = DatabaseManager(args.db)

    langs = [l.strip() for l in args.languages.split(",") if l.strip()]
    for lang in langs:
        logging.info(f"Starting batch evaluation for '{lang}' translations...")
        col = f"translation_{lang}_status"
        # fetch completed translations with transcripts available
        rows = db.execute_query(
            f"SELECT file_id FROM processing_status WHERE {col} = ? AND transcription_status = ?",
            ("completed", "completed"),
        )
        fids = [r["file_id"] for r in rows]
        if args.limit:
            fids = fids[: args.limit]
        try:
            evaluator = get_evaluator(lang)
        except NotImplementedError as ex:
            logging.warning(ex)
            continue

        for fid in fids:
            try:
                result = evaluator(fid, args.model)
                score = result.get("score_0_to_10")
                issues = result.get("issues", [])
                comment = result.get("overall_comment", "")
                # persist evaluation
                db.add_quality_evaluation(fid, lang, args.model, score, issues, comment)
                # update processing_status
                status = "qa_completed" if score >= args.threshold else "qa_failed"
                db.update_translation_status(fid, lang, status)
                logging.info(f"{fid}[{lang}] → score {score} → {status}")
            except Exception as e:
                logging.error(f"Error evaluating {fid} [{lang}]: {e}")

    logging.info("Batch evaluation finished.")


if __name__ == "__main__":
    main()
