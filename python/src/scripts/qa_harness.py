#!/usr/bin/env python3
"""
QA Harness - Measure precision/recall for auto-tagging

Compares auto-tagged results against a golden dataset.
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class QAMetrics:
    """Track precision/recall metrics."""

    def __init__(self):
        self.true_positives = 0
        self.false_positives = 0
        self.false_negatives = 0
        self.per_label = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    def update(self, predicted: str, actual: str, label_type: str):
        """Update metrics for a single prediction."""
        if predicted == actual and predicted:
            self.true_positives += 1
            self.per_label[label_type]["tp"] += 1
        elif predicted and not actual:
            self.false_positives += 1
            self.per_label[label_type]["fp"] += 1
        elif actual and not predicted:
            self.false_negatives += 1
            self.per_label[label_type]["fn"] += 1

    def precision(self) -> float:
        """Calculate precision."""
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)

    def recall(self) -> float:
        """Calculate recall."""
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)

    def f1(self) -> float:
        """Calculate F1 score."""
        p = self.precision()
        r = self.recall()
        if p + r == 0:
            return 0.0
        return 2 * (p * r) / (p + r)

    def per_label_metrics(self) -> dict[str, dict[str, float]]:
        """Calculate per-label precision/recall."""
        results = {}
        for label_type, counts in self.per_label.items():
            tp = counts["tp"]
            fp = counts["fp"]
            fn = counts["fn"]

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

            results[label_type] = {"precision": precision, "recall": recall, "f1": f1}

        return results


def load_golden_set(path: Path) -> dict[str, dict[str, str]]:
    """
    Load golden dataset.

    Expected format:
    {
      "path/to/note.md": {
        "area": "BIM",
        "service": "agents",
        "status": "published"
      }
    }
    """
    if not path.exists():
        raise FileNotFoundError(f"Golden set not found: {path}")

    data = json.loads(path.read_text())
    logger.info(f"Loaded golden set: {len(data)} notes")
    return data


def load_predictions(path: Path) -> dict[str, dict[str, str]]:
    """Load predicted tags from orchestration output."""
    if not path.exists():
        raise FileNotFoundError(f"Predictions not found: {path}")

    data = json.loads(path.read_text())
    logger.info(f"Loaded predictions: {len(data)} notes")
    return data


def evaluate(golden: dict, predictions: dict, fail_threshold: float = 0.90) -> dict[str, Any]:
    """
    Evaluate predictions against golden set.

    Args:
        golden: Golden dataset
        predictions: Predicted tags
        fail_threshold: Minimum F1 score to pass

    Returns:
        Evaluation report
    """
    metrics = QAMetrics()

    # Match predictions to golden set
    matched_notes = set(golden.keys()) & set(predictions.keys())
    missing_notes = set(golden.keys()) - set(predictions.keys())

    logger.info(f"Evaluating {len(matched_notes)} matched notes")
    if missing_notes:
        logger.warning(f"Missing predictions for {len(missing_notes)} notes")

    # Compute metrics per field
    for note_path in matched_notes:
        gold_tags = golden[note_path]
        pred_tags = predictions[note_path]

        for field in ["area", "service", "status"]:
            gold_val = gold_tags.get(field, "")
            pred_val = pred_tags.get(field, "")

            # Normalize empty strings
            gold_val = gold_val if gold_val else ""
            pred_val = pred_val if pred_val else ""

            metrics.update(pred_val, gold_val, field)

    # Generate report
    overall_f1 = metrics.f1()
    per_label = metrics.per_label_metrics()

    report = {
        "overall": {
            "precision": metrics.precision(),
            "recall": metrics.recall(),
            "f1": overall_f1,
            "true_positives": metrics.true_positives,
            "false_positives": metrics.false_positives,
            "false_negatives": metrics.false_negatives,
        },
        "per_label": per_label,
        "coverage": {
            "matched_notes": len(matched_notes),
            "missing_notes": len(missing_notes),
            "total_golden": len(golden),
        },
        "passed": overall_f1 >= fail_threshold,
        "threshold": fail_threshold,
    }

    return report


def print_report(report: dict):
    """Print evaluation report."""
    logger.info("\n=== QA Evaluation Report ===\n")

    overall = report["overall"]
    logger.info("Overall Metrics:")
    logger.info(f"  Precision: {overall['precision']:.3f}")
    logger.info(f"  Recall:    {overall['recall']:.3f}")
    logger.info(f"  F1 Score:  {overall['f1']:.3f}")
    logger.info(f"  TP: {overall['true_positives']}, FP: {overall['false_positives']}, FN: {overall['false_negatives']}")

    logger.info("\nPer-Label Metrics:")
    for label, metrics in report["per_label"].items():
        logger.info(f"  {label}:")
        logger.info(f"    Precision: {metrics['precision']:.3f}")
        logger.info(f"    Recall:    {metrics['recall']:.3f}")
        logger.info(f"    F1:        {metrics['f1']:.3f}")

    coverage = report["coverage"]
    logger.info("\nCoverage:")
    logger.info(f"  Matched:  {coverage['matched_notes']}/{coverage['total_golden']}")
    logger.info(f"  Missing:  {coverage['missing_notes']}")

    logger.info(f"\nThreshold: F1 >= {report['threshold']:.2f}")
    logger.info(f"Status:    {'✓ PASSED' if report['passed'] else '✗ FAILED'}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="QA harness for auto-tagging")
    parser.add_argument("--golden", type=str, required=True, help="Path to golden dataset JSON")
    parser.add_argument("--predictions", type=str, required=True, help="Path to predictions JSON")
    parser.add_argument("--threshold", type=float, default=0.90, help="Minimum F1 to pass (default: 0.90)")
    parser.add_argument("--output", type=str, help="Save report to JSON file")

    args = parser.parse_args()

    try:
        # Load datasets
        golden = load_golden_set(Path(args.golden))
        predictions = load_predictions(Path(args.predictions))

        # Evaluate
        report = evaluate(golden, predictions, fail_threshold=args.threshold)

        # Print results
        print_report(report)

        # Save if requested
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(json.dumps(report, indent=2))
            logger.info(f"\n✓ Report saved to {output_path}")

        # Exit with appropriate code
        sys.exit(0 if report["passed"] else 1)

    except Exception as e:
        logger.error(f"QA evaluation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
