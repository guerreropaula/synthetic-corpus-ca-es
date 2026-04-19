"""
Filters the metadata file to retain only documents that have been successfully
translated in the corpus pipeline.

1. Detects processed documents in the `data/processed/` directory.
2. Reads the original metadata file (`metadata.csv`).
3. Filters rows to keep only those whose `doc_id` appears in the processed set.
4. Writes the filtered metadata to `corpus/metadata_filtered.csv`.

Usage:
    python scripts/06_filter_metadata.py
"""

import csv
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
CORPUS_DIR = Path(__file__).parent.parent / "corpus"
METADATA_PATH = RAW_DIR / "metadata.csv"
OUTPUT_METADATA = CORPUS_DIR / "metadata_filtered.csv"

def main():
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    processed_ids = {
        p.stem.replace("_es", "")
        for p in PROCESSED_DIR.glob("doc_*_es.txt")
    }
    print(f"Processed docs found: {len(processed_ids)}")

    sample = METADATA_PATH.read_text(encoding="utf-8")[:2000]
    delimiter = "\t" if "\t" in sample.split("\n")[0] else ","

    rows = []
    with open(METADATA_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        fieldnames = [field.strip() for field in (reader.fieldnames or [])]
        for row in reader:
            doc_id = row.get("doc_id", "").strip()
            if doc_id in processed_ids:
                rows.append({k.strip(): v.strip() for k, v in row.items()})

    print(f"Metadata rows matched: {len(rows)}")

    with open(OUTPUT_METADATA, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved -> {OUTPUT_METADATA}")

if __name__ == "__main__":
    main()