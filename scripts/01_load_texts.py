"""
01_load_texts.py
----------------
Loads already-downloaded Valencian/Catalan literary texts in XML-embedded .txt format:

    <DOCUMENT>
      <OBRA id="137">
        <AUTOR>Gener, Pompeu</AUTOR>
        <TÍTOL>La taverna intel·lectual</TÍTOL>
        <ANY>1917</ANY>
        <CLASSIFICACIÓ_TEXTUAL llengua="LIT" ... />
      </OBRA>
      <TEXT>Full text as a single block…</TEXT>
    </DOCUMENT>

For each file the script:
  1. Parses the metadata from the XML header tags.
  2. Extracts the plain text from <TEXT>.
  3. Segments into paragraphs (double newline split).
  4. Saves a plain-text file to data/raw/<doc_id>.txt
  5. Appends a row to data/raw/metadata.csv.

Usage:
    cd /Users/folder/corpus-linguistics-project
    python scripts/01_load_texts.py --input_dir data/corpus_ctilc

Input directory should contain one or more *.txt files in the format above.

Output:
    data/raw/<doc_id>.txt       — plain-text paragraphs per document
    data/raw/metadata.csv       — document-level metadata
"""

import os
import re
import csv
import argparse
from pathlib import Path


RAW_DIR       = Path(__file__).parent.parent / "data" / "raw"
METADATA_FILE = RAW_DIR / "metadata.csv"

MIN_PARAGRAPH_CHARS = 30   # discard very short paragraphs (e.g. chapter headings)

METADATA_FIELDS = ["doc_id", "obra_id", "author", "title", "year", "lang", "traduccio", "variant", "source_file", "n_paragraphs"]


def extract_tag(text: str, tag: str) -> str:
    """Extract the inner text of a simple XML tag. Returns '' if not found."""
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_attr(text: str, tag: str, attr: str) -> str:
    """Extract an attribute value from a self-closing or opening tag."""
    match = re.search(rf'<{tag}[^>]*\s{attr}="([^"]*)"', text)
    return match.group(1).strip() if match else ""


def extract_obra_id(text: str) -> str:
    match = re.search(r'<OBRA\s+id="(\d+)"', text)
    return match.group(1) if match else ""


def parse_file(path: Path) -> dict | None:
    """
    Parse a single .txt file in the XML-embedded format.
    Returns a dict with keys: obra_id, author, title, year, lang, paragraphs.
    Returns None if the file cannot be parsed.
    """
    raw = path.read_text(encoding="utf-8-sig")  

    obra_id = extract_obra_id(raw)
    author  = extract_tag(raw, "AUTOR")
    title   = extract_tag(raw, "TÍTOL") or extract_tag(raw, "TITOL")
    year    = extract_tag(raw, "ANY")
    lang      = extract_attr(raw, "CLASSIFICACIÓ_TEXTUAL", "llengua") or "va"
    traduccio = extract_attr(raw, "CLASSIFICACIÓ_TEXTUAL", "traducció")
    variant   = extract_attr(raw, "CLASSIFICACIÓ_TEXTUAL", "variant")

    text_match = re.search(r"<TEXT>(.*?)</TEXT>", raw, re.DOTALL)
    if not text_match:
        print(f"  WARNING: No <TEXT> tag found in {path.name}. Skipping.")
        return None

    plain_text = text_match.group(1).strip()

    # Segment into paragraphs on double newlines
    paragraphs = [
        re.sub(r"\s+", " ", p.strip())
        for p in re.split(r"\n\s*\n", plain_text)
        if len(p.strip()) >= MIN_PARAGRAPH_CHARS
    ]

    if not paragraphs:
        print(f"  WARNING: No valid paragraphs extracted from {path.name}. Skipping.")
        return None

    return {
        "obra_id":    obra_id,
        "author":     author,
        "title":      title,
        "year":       year,
        "lang":       lang,
        "traduccio":  traduccio,
        "variant":    variant,
        "paragraphs": paragraphs,
    }

def main(input_dir: Path) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    txt_files = sorted(input_dir.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {input_dir}")
        return

    print(f"Found {len(txt_files)} file(s) in {input_dir}\n")

    with open(METADATA_FILE, "w", newline="", encoding="utf-8") as meta_f:
        writer = csv.DictWriter(meta_f, fieldnames=METADATA_FIELDS)
        writer.writeheader()

        for i, path in enumerate(txt_files, start=1):
            print(f"[{i}/{len(txt_files)}] Processing: {path.name}")

            parsed = parse_file(path)
            if parsed is None:
                continue

            obra_id = parsed["obra_id"] or str(i)
            doc_id  = f"doc_{int(obra_id):06d}" if obra_id.isdigit() else f"doc_{i:06d}"

            out_path = RAW_DIR / f"{doc_id}.txt"
            out_path.write_text("\n\n".join(parsed["paragraphs"]), encoding="utf-8")

            print(f"  → {len(parsed['paragraphs'])} paragraphs saved to {out_path.name}")

            writer.writerow({
                "doc_id":       doc_id,
                "obra_id":      parsed["obra_id"],
                "author":       parsed["author"],
                "title":        parsed["title"],
                "year":         parsed["year"],
                "lang":         parsed["lang"],
                "traduccio":    parsed["traduccio"],
                "variant":      parsed["variant"],
                "source_file":  path.name,
                "n_paragraphs": len(parsed["paragraphs"]),
            })

    print(f"\nMetadata saved → {METADATA_FILE}")
    print("Done. Run 02_translate_va_es.py next.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", type=Path, required=True)
    args = parser.parse_args()
    main(args.input_dir)