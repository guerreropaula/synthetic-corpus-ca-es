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
    corpus/corpus_ca_es.csv                — paragraph-level alignment with offsets
    corpus/corpus_ca_es_fulltext.jsonl     — document-level full text (JSONL)

Usage:
  python scripts/05_build_corpus.py              # Full run: preprocess + build
  python scripts/05_build_corpus.py --dry-run    # Dry run: show what would be removed
  python scripts/05_build_corpus.py --no-preprocess  # Skip preprocessing, only build
"""

import csv
import json
import re
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

csv.field_size_limit(sys.maxsize)

RAW_DIR        = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR  = Path(__file__).parent.parent / "data" / "processed"
CORPUS_DIR     = Path(__file__).parent.parent / "corpus"
OUTPUT_PARA    = CORPUS_DIR / "corpus_ca_es.csv"
OUTPUT_FULL    = CORPUS_DIR / "corpus_ca_es_fulltext.jsonl"
METADATA_PATH  = RAW_DIR / "metadata.csv"

MARKER_PATTERN = re.compile(
    r'^\s*"?\['
    r'(?:Texto literario|Literario|Literaria|Literary text|Literary)'
    r'[.\s].*',
    re.IGNORECASE
)

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

_model = None


def get_model():
    global _model
    if _model is None:
        print("  Loading multilingual-e5-large model (first run may download weights)...")
        _model = SentenceTransformer("intfloat/multilingual-e5-large")
    return _model


def embed(texts: list[str], prefix: str = "passage") -> np.ndarray:
    model = get_model()
    prefixed = [f"{prefix}: {t}" for t in texts]
    return model.encode(
        prefixed,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=False,
    )


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def make_overlap_embeddings(vecs: np.ndarray, max_merge: int = 2) -> dict[tuple[int, int], np.ndarray]:
    n = len(vecs)
    blocks = {}
    for i in range(n):
        for length in range(1, max_merge + 1):
            if i + length > n:
                break
            mean_vec = vecs[i:i + length].mean(axis=0)
            norm = np.linalg.norm(mean_vec)
            if norm > 0:
                mean_vec = mean_vec / norm
            blocks[(i, length)] = mean_vec
    return blocks


def vecalign_dp(
    paras_ca: list[str],
    paras_es: list[str],
    max_merge: int = 2,
    gap_penalty: float = 0.2,
) -> list[tuple[str, str]]:
    if not paras_ca or not paras_es:
        return []

    vecs_ca = embed(paras_ca, prefix="passage")
    vecs_es = embed(paras_es, prefix="passage")
    blocks_ca = make_overlap_embeddings(vecs_ca, max_merge)
    blocks_es = make_overlap_embeddings(vecs_es, max_merge)

    n, m = len(paras_ca), len(paras_es)
    NEG_INF = -1e9
    dp   = np.full((n + 1, m + 1), NEG_INF, dtype=np.float64)
    back = {}
    dp[0][0] = 0.0

    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] == NEG_INF:
                continue
            for lca in range(1, max_merge + 1):
                for les in range(1, max_merge + 1):
                    ni, nj = i + lca, j + les
                    if ni > n or nj > m:
                        continue
                    sim = cosine_sim(blocks_ca[(i, lca)], blocks_es[(j, les)])
                    penalty = gap_penalty * (lca + les - 2)
                    score = dp[i][j] + sim - penalty
                    if score > dp[ni][nj]:
                        dp[ni][nj] = score
                        back[(ni, nj)] = (i, j, lca, les)

    path = []
    i, j = n, m
    while (i, j) != (0, 0):
        if (i, j) not in back:
            break
        pi, pj, lca, les = back[(i, j)]
        path.append((pi, lca, pj, les))
        i, j = pi, pj
    path.reverse()

    pairs = []
    for si, lca, sj, les in path:
        ca_text = " ".join(paras_ca[si:si + lca]).strip()
        es_text = " ".join(paras_es[sj:sj + les]).strip()
        if ca_text and es_text:
            pairs.append((ca_text, es_text))

    return pairs


def align_paragraphs(paras_ca: list[str], paras_es: list[str]) -> list[tuple[str, str]]:
    return vecalign_dp(paras_ca, paras_es)


def is_marker_line(line: str) -> bool:
    if not MARKER_PATTERN.match(line):
        return False
    parts = line.split(']', 1)
    if len(parts) == 1:
        return True
    after = parts[1].strip()
    return after in ('', '"', '"\n') or not after or after.isspace()


def remove_markers_from_file(file_path: Path, dry_run: bool = False) -> int:
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except Exception as e:
        print(f"  ERROR reading {file_path}: {e}")
        return 0

    filtered = [l for l in lines if not is_marker_line(l)]
    removed = len(lines) - len(filtered)

    if removed > 0:
        if dry_run:
            print(f"    [DRY RUN] {file_path.name}: would remove {removed} marker line(s)")
        else:
            try:
                file_path.write_text("".join(filtered), encoding="utf-8")
                print(f"    {file_path.name}: removed {removed} marker line(s)")
            except Exception as e:
                print(f"  ERROR writing {file_path}: {e}")
                return 0

    return removed


def preprocess_markers(dry_run: bool = False) -> int:
    es_files = sorted(PROCESSED_DIR.glob("*_es.txt"))

    if not es_files:
        print(f"  No Spanish translation files found in {PROCESSED_DIR}")
        return 0

    print(f"  Found {len(es_files)} Spanish translation file(s).")
    if dry_run:
        print("  [DRY RUN MODE] - No files will be modified.\n")
    else:
        print()

    total_removed = sum(remove_markers_from_file(f, dry_run) for f in es_files)
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
        index = {
            row["doc_id"].strip(): {k.strip(): v.strip() for k, v in row.items()}
            for row in reader
            if row.get("doc_id", "").strip()
        }
    return index, fieldnames


def load_full_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1").strip()
    except Exception as e:
        print(f"  [ERROR] load_full_text({path}): {e}")
        return ""


def load_paragraphs(path: Path) -> list[str]:
    raw = load_full_text(path)
    if not raw:
        return []
    blocks = re.split(r'\n\s*\n', raw)
    return [b.replace('\n', ' ').strip() for b in blocks if b.strip()]


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
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be removed without modifying files.")
    parser.add_argument("--no-preprocess", action="store_true",
                        help="Skip marker removal, only build corpus.")
    args = parser.parse_args()

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    if not args.no_preprocess:
        print("Step 1: Removing marker lines from Spanish translation files...")
        preprocess_markers(dry_run=args.dry_run)

    print("Step 2: Building aligned bilingual corpus...")

    metadata, meta_fields = load_metadata(METADATA_PATH)
    doc_ids = [p.stem.replace("_es", "") for p in sorted(PROCESSED_DIR.glob("doc_*_es.txt"))]

    if not doc_ids:
        print("No CA/ES document pairs found. Run the previous pipeline steps first.")
        return

    para_fieldnames = meta_fields + [f for f in ALIGNMENT_FIELDS if f not in meta_fields]
    aligned_docs: dict[str, list[tuple[str, str]]] = {}
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

            is_truncated = len(paras_ca) != len(paras_es)
            if is_truncated:
                print(f"  [WARN] {doc_id}: CA={len(paras_ca)} vs ES={len(paras_es)} — running e5 alignment.")

            try:
                pairs = align_paragraphs(paras_ca, paras_es) if is_truncated else list(zip(paras_ca, paras_es))
            except Exception as e:
                print(f"  [WARN] {doc_id}: alignment failed ({e}), falling back to truncation.")
                n = min(len(paras_ca), len(paras_es))
                pairs = list(zip(paras_ca[:n], paras_es[:n]))

            aligned_n  = len(pairs)
            texts_ca   = [p[0] for p in pairs]
            texts_es   = [p[1] for p in pairs]
            offsets_ca = compute_offsets(texts_ca)
            offsets_es = compute_offsets(texts_es)
            doc_meta   = metadata.get(doc_id, {"doc_id": doc_id})

            for i, (text_ca, text_es) in enumerate(pairs):
                row = {field: doc_meta.get(field, "") for field in meta_fields}
                row["doc_id"] = doc_id
                row.update({
                    "para_id":            i,
                    "offset_ca":          offsets_ca[i],
                    "offset_es":          offsets_es[i],
                    "n_paragraphs_ca":    len(paras_ca),
                    "n_paragraphs_es":    len(paras_es),
                    "aligned_paragraphs": aligned_n,
                    "is_truncated":       str(is_truncated),
                    "text_ca":            text_ca,
                    "text_es":            text_es,
                })
                writer.writerow(row)
                total_para_rows += 1

            aligned_docs[doc_id] = pairs
            total_para_docs += 1
            print(f"  [PARA] {doc_id}: {aligned_n} aligned pairs written.")

    print(f"\nParagraph corpus -> {OUTPUT_PARA}")
    print(f"  Documents: {total_para_docs} | Rows: {total_para_rows}")

    total_full_rows = 0

    with open(OUTPUT_FULL, "w", encoding="utf-8") as f:
        for doc_id in doc_ids:
            if doc_id not in aligned_docs:
                continue
            pairs    = aligned_docs[doc_id]
            text_ca  = "\n\n".join(p[0] for p in pairs)
            text_es  = "\n\n".join(p[1] for p in pairs)
            doc_meta = metadata.get(doc_id, {"doc_id": doc_id})
            record   = {field: doc_meta.get(field, "") for field in meta_fields}
            record["doc_id"]  = doc_id
            record["text_ca"] = text_ca
            record["text_es"] = text_es
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            total_full_rows += 1
            print(f"  [FULL] {doc_id}: {len(pairs)} paragraphs (ca={len(text_ca)} chars, es={len(text_es)} chars)")

    print(f"\nFulltext corpus -> {OUTPUT_FULL}")
    print(f"  Documents: {total_full_rows}")


if __name__ == "__main__":
    main()