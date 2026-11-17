#!/usr/bin/env python3
"""Pick the 10 contamination-check questions from the Vals public set.

One question from each of the 9 question types, plus one more
"Simple retrieval - Quantitative" question. The choice is made with a
fixed seed so it is reproducible and not hand picked.

Usage: python3 evals/contamination/select_questions.py
"""

import csv
import random
from pathlib import Path

SEED = 42
EXTRA_TYPE = "Simple retrieval - Quantitative"

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "vals" / "public.csv"
OUTPUT = ROOT / "evals" / "contamination" / "questions.csv"


def main() -> None:
    with SOURCE.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Row number in public.csv (1 based) is the stable question id.
    for i, row in enumerate(rows, start=1):
        row["id"] = f"vals-{i:02d}"

    by_type: dict[str, list[dict]] = {}
    for row in rows:
        by_type.setdefault(row["Question Type"], []).append(row)

    rng = random.Random(SEED)  # nosec B311
    picked = []
    for qtype in sorted(by_type):
        count = 2 if qtype == EXTRA_TYPE else 1
        picked.extend(rng.sample(by_type[qtype], count))

    picked.sort(key=lambda r: r["id"])
    fields = ["id", "Question Type", "Question", "Answer", "Rubric"]
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(picked)

    print(f"seed {SEED}: wrote {len(picked)} questions to {OUTPUT.relative_to(ROOT)}")
    for row in picked:
        print(f"  {row['id']}  {row['Question Type']}")


if __name__ == "__main__":
    main()
