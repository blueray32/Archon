"""
Utility helpers for managing golden set labels and diagnostics.

Commands:
  python -m src.scripts.golden_tools unlabeled
  python -m src.scripts.golden_tools label-csv
  python -m src.scripts.golden_tools merge-labels
  python -m src.scripts.golden_tools seed-golden
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
GOLDEN_PATH = ROOT / "python" / "golden_set_archon.json"
PREDICTIONS_PATH = ROOT / "artifacts" / "predictions_golden.json"
CSV_PATH = ROOT / "artifacts" / "golden_label_todo.csv"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return json.loads(path.read_text())


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_unlabeled() -> None:
    golden = _load_json(GOLDEN_PATH)
    notes = {
        k: v
        for k, v in golden.items()
        if not k.startswith("_")
    }
    missing = [
        key for key, payload in notes.items()
        if not any((payload.get("area"), payload.get("service"), payload.get("status")))
    ]
    print(f"Unlabeled: {len(missing)}")
    for key in missing[:50]:
        print(key)


def cmd_label_csv() -> None:
    golden = _load_json(GOLDEN_PATH)
    predictions = _load_json(PREDICTIONS_PATH)
    rows = [
        [
            "path",
            "area",
            "service",
            "status",
            "suggested_area",
            "suggested_service",
            "suggested_status",
        ]
    ]
    for key, payload in golden.items():
        if key.startswith("_"):
            continue
        prediction = predictions.get(key, {})
        rows.append(
            [
                key,
                payload.get("area", ""),
                payload.get("service", ""),
                payload.get("status", ""),
                prediction.get("area", ""),
                prediction.get("service", ""),
                prediction.get("status", ""),
            ]
        )

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
    print(f"Wrote {CSV_PATH}")


def cmd_merge_labels() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    golden = _load_json(GOLDEN_PATH)
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            path = (row.get("path") or "").strip()
            if not path or path.startswith("_") or path not in golden:
                continue
            for field in ("area", "service", "status"):
                value = (row.get(field) or "").strip()
                if value:
                    golden[path][field] = value
    _write_json(GOLDEN_PATH, golden)
    print(f"Updated {GOLDEN_PATH}")


def cmd_seed_golden() -> None:
    golden = _load_json(GOLDEN_PATH)
    predictions = _load_json(PREDICTIONS_PATH)
    seeded: dict[str, Any] = {}

    for key, payload in golden.items():
        if key.startswith("_"):
            seeded[key] = payload
            continue
        prediction = predictions.get(key, {})
        seeded[key] = {
            "area": payload.get("area") or prediction.get("area", ""),
            "service": payload.get("service") or prediction.get("service", ""),
            "status": payload.get("status") or prediction.get("status", ""),
        }

    output_path = GOLDEN_PATH.parent / "golden_seeded.json"
    _write_json(output_path, seeded)
    print(f"seeded → {output_path}")


def _input_with_default(prompt: str, default: str) -> str:
    suffix = f" [{default}]" if default else ""
    response = input(f"{prompt}{suffix}: ").strip()
    return response or default


def cmd_label_interactive() -> None:
    golden = _load_json(GOLDEN_PATH)
    predictions = _load_json(PREDICTIONS_PATH)

    unlabeled_keys: list[str] = [
        key
        for key, payload in golden.items()
        if not key.startswith("_")
        and not any(
            (payload.get("area"), payload.get("service"), payload.get("status"))
        )
    ]

    if not unlabeled_keys:
        print("All notes are labeled. Nothing to do.")
        return

    total = len(unlabeled_keys)
    print(f"{total} unlabeled notes. Enter 'q' to quit early.\n")

    for idx, key in enumerate(unlabeled_keys, start=1):
        payload = golden[key]
        suggestion = predictions.get(key, {})

        current_area = payload.get("area", "")
        current_service = payload.get("service", "")
        current_status = payload.get("status", "")

        suggested_area = suggestion.get("area", "")
        suggested_service = suggestion.get("service", "")
        suggested_status = suggestion.get("status", "")

        print(f"[{idx}/{total}] {key}")
        print(f"  current: area={current_area!r}, service={current_service!r}, status={current_status!r}")
        print(f"  suggest: area={suggested_area!r}, service={suggested_service!r}, status={suggested_status!r}")

        while True:
            choice = input("Action ([a]ccept/[m]anual/[s]kip/[q]uit): ").strip().lower()
            if not choice:
                choice = "a" if any((suggested_area, suggested_service, suggested_status)) else "m"

            if choice == "a":
                payload["area"] = suggested_area
                payload["service"] = suggested_service
                payload["status"] = suggested_status
                _write_json(GOLDEN_PATH, golden)
                print("  ✓ Accepted suggestions\n")
                break
            if choice == "m":
                payload["area"] = _input_with_default("    area", current_area or suggested_area)
                payload["service"] = _input_with_default("    service", current_service or suggested_service)
                payload["status"] = _input_with_default("    status", current_status or suggested_status)
                _write_json(GOLDEN_PATH, golden)
                print("  ✓ Saved manual labels\n")
                break
            if choice == "s":
                print("  ↷ Skipped\n")
                break
            if choice == "q":
                print("Stopping early at user request.")
                _write_json(GOLDEN_PATH, golden)
                return
            print("  ! Invalid choice. Please enter a/m/s/q.")


def cmd_label_auto() -> None:
    golden = _load_json(GOLDEN_PATH)
    predictions = _load_json(PREDICTIONS_PATH)

    updated = 0
    missing_predictions: list[str] = []

    for key, payload in golden.items():
        if key.startswith("_"):
            continue
        if any((payload.get("area"), payload.get("service"), payload.get("status"))):
            continue

        prediction = predictions.get(key)
        if not prediction:
            missing_predictions.append(key)
            continue

        payload["area"] = prediction.get("area", "")
        payload["service"] = prediction.get("service", "")
        payload["status"] = prediction.get("status", "")
        updated += 1

    _write_json(GOLDEN_PATH, golden)

    print(f"Auto-labeled {updated} notes using predictions.")
    if missing_predictions:
        print("No predictions found for the following notes (left unlabeled):")
        for key in missing_predictions:
            print(f" - {key}")


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python -m src.scripts.golden_tools "
            "[unlabeled|label-csv|merge-labels|seed-golden|label|label-auto]"
        )
        raise SystemExit(1)
    command = sys.argv[1]
    if command == "unlabeled":
        cmd_unlabeled()
    elif command == "label-csv":
        cmd_label_csv()
    elif command == "merge-labels":
        cmd_merge_labels()
    elif command == "seed-golden":
        cmd_seed_golden()
    elif command == "label":
        cmd_label_interactive()
    elif command == "label-auto":
        cmd_label_auto()
    else:
        print(f"Unknown command: {command}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
