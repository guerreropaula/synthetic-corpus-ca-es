"""
03_build_corpus.py
------------------
This script performs two main tasks:
  1. Removes prompt artifact lines from Spanish translation files
  2. Builds two aligned bilingual corpus files from:
     - Catalan originals:      data/raw/<doc_id>.txt
     - Spanish translations:   data/processed/<doc_id>_es.txt
     - Metadata:               data/raw/metadata.csv

Outputs:
    corpus/corpus_ca_es.csv          — paragraph-level alignment with offsets
    corpus/corpus_ca_es_fulltext.csv — document-level full text

Usage:
  python scripts/05_build_corpus.py              # Full run: preprocess + build
  python scripts/05_build_corpus.py --dry-run    # Dry run: show what would be removed
  python scripts/05_build_corpus.py --no-preprocess  # Skip preprocessing, only build
"""

import csv
import re
import sys
from pathlib import Path

RAW_DIR       = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
CORPUS_DIR    = Path(__file__).parent.parent / "corpus"
OUTPUT_PARA   = CORPUS_DIR / "corpus_ca_es.csv"
OUTPUT_FULL   = CORPUS_DIR / "corpus_ca_es_fulltext.csv"
METADATA_PATH = RAW_DIR / "metadata.csv"

# Pattern to match LLM artifact lines: [Texto literario. ... ]
MARKER_PATTERN = re.compile(r'^\s*"?\[Texto literario\..*', re.IGNORECASE)

ALIGNMENT_FIELDS = [
    "para_id",
    "offset_ca",
    "offset_es",
    "n_paragraphs_ca",
    "n_paragraphs_es",
    "aligned_paragraphs",
    "is_truncated",
    "text_ca",
    "text_es",
]

def is_marker_line(line):
    """
    Check if a line contains only a marker (with optional quotes/whitespace).
    """
    stripped = line.strip()
    if MARKER_PATTERN.match(line):
        remainder = line.split(']', 1)
        if len(remainder) == 1:
            return True
        elif len(remainder) == 2:
            after_bracket = remainder[1].strip()
            if after_bracket in ('', '"', '"\n'):
                return True
            if not after_bracket or after_bracket.isspace():
                return True
    return False


def remove_markers_from_file(file_path, dry_run=False):
    """
    Remove marker lines from a file. Returns count of lines removed.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"  ERROR reading {file_path}: {e}")
        return 0
    
    original_count = len(lines)
    filtered_lines = [line for line in lines if not is_marker_line(line)]
    removed_count = original_count - len(filtered_lines)
    
    if removed_count > 0:
        if not dry_run:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(filtered_lines)
                print(f"    {file_path.name}: removed {removed_count} marker line(s)")
            except Exception as e:
                print(f"  ERROR writing {file_path}: {e}")
                return 0
        else:
            print(f"    [DRY RUN] {file_path.name}: would remove {removed_count} marker line(s)")
    
    return removed_count


def preprocess_markers(dry_run=False):
    """
    Remove marker lines from all Spanish translation files. Returns total count of lines removed.
    """
    es_files = sorted(PROCESSED_DIR.glob("*_es.txt"))
    
    if not es_files:
        print(f"  No Spanish translation files found in {PROCESSED_DIR}")
        return 0
    
    print(f"  Found {len(es_files)} Spanish translation file(s).")
    
    if dry_run:
        print("  [DRY RUN MODE] - No files will be modified.\n")
    else:
        print()
    
    total_removed = 0
    for file_path in es_files:
        removed = remove_markers_from_file(file_path, dry_run=dry_run)
        total_removed += removed
    
    print(f"  Total marker lines removed: {total_removed}")
    if dry_run:
        print("  (No files were modified.)\n")
    else:
        print()
    
    return total_removed

def load_metadata(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    if not path.exists():
        return {}, ["doc_id"]
    sample = path.read_text(encoding="utf-8")[:2000]
    delimiter = "\t" if "\t" in sample.split("\n")[0] else ","
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        fieldnames = [col.strip() for col in (reader.fieldnames or ["doc_id"])]
        index = {}
        for row in reader:
            doc_id = row.get("doc_id", "").strip()
            if doc_id:
                index[doc_id] = {k.strip(): v.strip() for k, v in row.items()}
    return index, fieldnames


def load_full_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1").strip()


def load_paragraphs(path: Path) -> list[str]:
    raw = load_full_text(path)
    if not raw:
        return []
    return [p.strip() for p in raw.split("\n\n") if p.strip()]


def compute_offsets(paragraphs: list[str]) -> list[int]:
    offsets, pos = [], 0
    for p in paragraphs:
        offsets.append(pos)
        pos += len(p) + 2
    return offsets


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Preprocess Spanish translation files and build aligned bilingual corpus.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without actually modifying files.",
    )
    parser.add_argument(
        "--no-preprocess",
        action="store_true",
        help="Skip marker removal preprocessing, only build corpus.",
    )
    args = parser.parse_args()
    
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Preprocess markers (unless --no-preprocess)
    if not args.no_preprocess:
        print("Step 1: Removing marker lines from Spanish translation files...")
        preprocess_markers(dry_run=args.dry_run)
    
    # Step 2: Build corpus
    print("Step 2: Building aligned bilingual corpus...")
    
    metadata, meta_fields = load_metadata(METADATA_PATH)

    # Doc IDs that have both sides
    processed_files = sorted(PROCESSED_DIR.glob("doc_*_es.txt"))
    doc_ids = [p.stem.replace("_es", "") for p in processed_files]

    if not doc_ids:
        print("No CA/ES document pairs found. Run the previous pipeline steps first.")
        return


    # 1. Output 1: paragraph-level alignment
    
    para_fieldnames = meta_fields + [f for f in ALIGNMENT_FIELDS if f not in meta_fields]

    total_para_rows = 0
    total_para_docs = 0

    with open(OUTPUT_PARA, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=para_fieldnames)
        writer.writeheader()

        for doc_id in doc_ids:
            paras_ca = load_paragraphs(RAW_DIR / f"{doc_id}.txt")
            paras_es = load_paragraphs(PROCESSED_DIR / f"{doc_id}_es.txt")

            if not paras_ca:
                print(f"  [SKIP] {doc_id}: CA text empty or missing.")
                continue
            if not paras_es:
                print(f"  [SKIP] {doc_id}: ES translation empty or missing.")
                continue

            aligned_n    = min(len(paras_ca), len(paras_es))
            is_truncated = len(paras_ca) != len(paras_es)

            if is_truncated:
                print(f"  [WARN] {doc_id}: CA={len(paras_ca)} vs ES={len(paras_es)} paragraphs — truncating to {aligned_n}.")

            offsets_ca = compute_offsets(paras_ca[:aligned_n])
            offsets_es = compute_offsets(paras_es[:aligned_n])
            doc_meta   = metadata.get(doc_id, {"doc_id": doc_id})

            for i in range(aligned_n):
                row = {field: doc_meta.get(field, "") for field in meta_fields}
                row["doc_id"] = doc_id
                row.update({
                    "para_id":           i,
                    "offset_ca":         offsets_ca[i],
                    "offset_es":         offsets_es[i],
                    "n_paragraphs_ca":   len(paras_ca),
                    "n_paragraphs_es":   len(paras_es),
                    "aligned_paragraphs": aligned_n,
                    "is_truncated":      str(is_truncated),
                    "text_ca":           paras_ca[i],
                    "text_es":           paras_es[i],
                })
                writer.writerow(row)
                total_para_rows += 1

            total_para_docs += 1
            print(f"  [PARA] {doc_id}: {aligned_n} paragraph pairs written.")

    print(f"\nParagraph corpus -> {OUTPUT_PARA}")
    print(f"  Documents: {total_para_docs} | Rows: {total_para_rows}")



    # 2. Output 2: full-text document level
    
    full_fieldnames = meta_fields + ["text_ca", "text_es"]

    total_full_rows = 0

    with open(OUTPUT_FULL, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=full_fieldnames)
        writer.writeheader()

        for doc_id in doc_ids:
            text_ca = load_full_text(RAW_DIR / f"{doc_id}.txt")
            text_es = load_full_text(PROCESSED_DIR / f"{doc_id}_es.txt")

            if not text_ca:
                print(f"  [WARN] {doc_id}: text_ca vacío.")
            if not text_es:
                print(f"  [WARN] {doc_id}: text_es vacío.")

            doc_meta = metadata.get(doc_id, {"doc_id": doc_id})
            row = {field: doc_meta.get(field, "") for field in meta_fields}
            row["doc_id"]  = doc_id
            row["text_ca"] = text_ca
            row["text_es"] = text_es
            writer.writerow(row)
            total_full_rows += 1
            print(f"  [FULL] {doc_id}: written (ca={len(text_ca)} chars, es={len(text_es)} chars)")

    print(f"\nFulltext corpus -> {OUTPUT_FULL}")
    print(f"  Documents: {total_full_rows}")


if __name__ == "__main__":
    main()