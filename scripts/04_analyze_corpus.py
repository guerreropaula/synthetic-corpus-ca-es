"""
04_analyze_corpus.py
--------------------
Analyzes the distribution of the corpus loaded by 01_load_texts.py.

Reads:
    data/raw/metadata.csv

Produces:
    data/analysis/general/run_<stamp>/corpus_stats.txt     — structured plain-text summary statistics
    data/analysis/general/run_<stamp>/figures/             — individual PNG charts 

Usage:
    python scripts/03_analyze_corpus.py
    python scripts/03_analyze_corpus.py --csv data/raw/metadata.csv # specify custom metadata path
    python scripts/03_analyze_corpus.py --year 1920  # filter by minimum year
    python scripts/03_analyze_corpus.py --variant valencia  # filter by variety (e.g. valencia, central, nord-occidental, balearic) 
    python scripts/03_analyze_corpus.py --only-processed  # keep only documents that exist in data/processed/
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median


RAW_DIR       = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
ANALYSIS_ROOT_DIR = Path(__file__).parent.parent / "data" / "analysis"
ANALYSIS_DIR  = ANALYSIS_ROOT_DIR / "general"
FIGURES_DIR   = ANALYSIS_DIR / "figures"
CORPUS_DIR    = Path(__file__).parent.parent / "corpus"

def load_metadata(csv_path: Path) -> list[dict]:
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def safe_int(val: str, fallback: int = 0) -> int:
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return fallback


def normalize_text(value: str) -> str:
    text = str(value or "").strip()
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_translation_flag(value: str) -> str:
    raw_value = str(value or "").strip()
    normalized = normalize_text(raw_value)

    if normalized in {"1", "si", "s", "yes", "true"}:
        return "Translation"
    if normalized in {"0", "no", "n", "false"}:
        return "Original"
    if not normalized:
        return "Unknown"
    return f"Other ({raw_value})"


def format_stat(value: int | float | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.1f}"
    return f"{value:,}"


def format_share(count: int, total: int) -> str:
    if total <= 0:
        return "0.0%"
    return f"{(count / total) * 100:.1f}%"


def format_config_value(value: object) -> str:
    if value is None or value == "":
        return "n/a"
    return str(value)


def summarize_dominant_category(data: dict[str, int], total: int, fallback: str = "n/a") -> str:
    if not data:
        return fallback
    label, count = max(data.items(), key=lambda item: item[1])
    return f"{label} ({count}, {format_share(count, total)})"


def count_words_in_file(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="ignore").split())


def count_ca_words(records: list[dict]) -> int:
    total = 0
    for r in records:
        doc_id = r.get("doc_id")
        if not doc_id:
            continue
        path = RAW_DIR / f"{doc_id}.txt"
        if path.exists():
            total += count_words_in_file(path)
    return total


def count_es_words(records: list[dict]) -> int:
    total = 0
    for r in records:
        doc_id = r.get("doc_id")
        if not doc_id:
            continue
        path = PROCESSED_DIR / f"{doc_id}_es.txt"
        if path.exists():
            total += count_words_in_file(path)
    return total


def analyze_aligned_corpus(corpus_path: Path) -> dict:
    if not corpus_path.exists():
        return {
            "aligned_pairs": 0,
            "ca_words": 0,
            "es_words": 0,
            "found": False,
        }
    
    aligned_pairs = 0
    ca_words = 0
    es_words = 0
    
    try:
        with open(corpus_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                aligned_pairs += 1
                ca_text = row.get("text_ca", "").strip()
                if ca_text:
                    ca_words += len(ca_text.split())
                es_text = row.get("text_es", "").strip()
                if es_text:
                    es_words += len(es_text.split())
    except Exception as e:
        print(f"Warning: Error reading {corpus_path}: {e}")
        return {
            "aligned_pairs": 0,
            "ca_words": 0,
            "es_words": 0,
            "found": False,
        }
    
    return {
        "aligned_pairs": aligned_pairs,
        "ca_words": ca_words,
        "es_words": es_words,
        "found": True,
    }


def decade(year: int) -> str:
    return f"{(year // 10) * 10}s" if year else "unknown"


def compute_stats(records: list[dict]) -> dict:
    total = len(records)

    years = [safe_int(r["year"]) for r in records if safe_int(r["year"]) > 0]
    decades = Counter(decade(y) for y in years)
    year_range = (min(years), max(years)) if years else (None, None)

    langs = Counter(r["lang"].strip().upper() or "UNKNOWN" for r in records)

    traduccio_counts = Counter()
    for r in records:
        traduccio_counts[normalize_translation_flag(r.get("traduccio", ""))] += 1

    variants = Counter(r.get("variant", "").strip() or "unspecified" for r in records)

    n_paras = [safe_int(r["n_paragraphs"]) for r in records]
    total_paras = sum(n_paras)
    avg_paras    = total_paras / total if total else 0
    median_paras = median(n_paras) if n_paras else 0

    print("Counting Catalan words (data/raw/)...")
    ca_words = count_ca_words(records)
    print("Counting Spanish words (data/processed/)...")
    es_words = count_es_words(records)

    authors = Counter(r["author"].strip() for r in records if r.get("author"))
    top_authors = authors.most_common(15)

    paras_by_decade: dict[str, list[int]] = defaultdict(list)
    for r in records:
        y = safe_int(r["year"])
        d = decade(y) if y else "unknown"
        paras_by_decade[d].append(safe_int(r["n_paragraphs"]))

    avg_paras_by_decade = {
        d: round(sum(v) / len(v), 1) for d, v in paras_by_decade.items() if v
    }

    aligned_corpus_path = CORPUS_DIR / "corpus_ca_es.csv"
    print("Analyzing aligned corpus (corpus_ca_es.csv)...")
    aligned_stats = analyze_aligned_corpus(aligned_corpus_path)

    return {
        "total": total,
        "years": years,
        "year_range": year_range,
        "decades": dict(sorted(decades.items())),
        "langs": dict(langs.most_common()),
        "traduccio": dict(traduccio_counts),
        "variants": dict(variants.most_common()),
        "total_paragraphs": total_paras,
        "ca_words": ca_words,
        "es_words": es_words,
        "avg_paragraphs": round(avg_paras, 1),
        "median_paragraphs": median_paras,
        "top_authors": top_authors,
        "avg_paras_by_decade": avg_paras_by_decade,
        "paras_by_decade": {d: sum(v) for d, v in paras_by_decade.items()},
        "aligned_corpus": aligned_stats,
    }


def text_section(title: str) -> list[str]:
    line = "=" * 78
    return [line, title.upper(), line]


def text_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    widths = [len(header) for header in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def render_row(row: list[str]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    separator = "-+-".join("-" * width for width in widths)
    lines = [render_row(headers), separator]
    lines.extend(render_row(row) for row in rows)
    return lines


def distribution_rows(data: dict[str, int], total: int) -> list[list[str]]:
    return [[label, format_stat(count), format_share(count, total)] for label, count in data.items()]


def write_text_report(stats: dict, out_path: Path, args: argparse.Namespace) -> None:
    y0, y1 = stats["year_range"]
    year_range = f"{y0}-{y1}" if y0 and y1 else "n/a"
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    top_decade = summarize_dominant_category(stats["decades"], stats["total"])
    top_variant = summarize_dominant_category(stats["variants"], stats["total"])
    translation_profile = summarize_dominant_category(stats["traduccio"], stats["total"])

    lines = [
        "CORPUS ANALYSIS SUMMARY",
        f"Generated on: {generated_at}",
        "",
    ]

    lines.extend(text_section("Executive Summary"))
    lines.extend([
        f"- The filtered corpus contains {format_stat(stats['total'])} documents spanning {year_range}.",
        f"- The most represented decade is {top_decade}.",
        f"- The dominant textual variant is {top_variant}.",
        f"- The translation profile is led by {translation_profile}.",
        "",
    ])

    if stats["aligned_corpus"]["found"]:
        lines.extend([
            f"- Parallel Corpus (corpus_ca_es.csv): {format_stat(stats['aligned_corpus']['aligned_pairs'])} aligned pairs.",
            "",
        ])

    lines.extend(text_section("Run Configuration"))
    lines.extend(text_table(
        ["Parameter", "Value"],
        [
            ["CSV source", str(args.csv)],
            ["Only processed", str(args.only_processed)],
            ["Year filter", format_config_value(args.year)],
            ["Variant filter", format_config_value(args.variant)],
            ["Output directory", str(out_path.parent)],
        ],
    ))
    lines.append("")

    lines.extend(text_section("Core Metrics"))
    lines.extend(text_table(
        ["Metric", "Value"],
        [
            ["Total documents", format_stat(stats["total"])],
            ["Total paragraphs", format_stat(stats["total_paragraphs"])],
            ["Average paragraphs per document", format_stat(stats["avg_paragraphs"])],
            ["Median paragraphs per document", format_stat(stats["median_paragraphs"])],
            ["Year range", year_range],
            ["Unique language labels", format_stat(len(stats["langs"]))],
            ["Unique variants", format_stat(len(stats["variants"]))],
        ],
    ))
    lines.append("")

    lines.extend(text_section("Word Counts"))
    lines.extend(text_table(
        ["Source", "Words"],
        [
            ["Catalan originals  (data/raw/)",         format_stat(stats["ca_words"])],
            ["Spanish translations (data/processed/)", format_stat(stats["es_words"])],
        ],
    ))
    lines.append("")

    if stats["aligned_corpus"]["found"]:
        lines.extend(text_section("Parallel Corpus Statistics"))
        lines.extend([
            f"- Aligned pairs (corpus_ca_es.csv): {format_stat(stats['aligned_corpus']['aligned_pairs'])}",
            "",
        ])
        lines.extend(text_table(
            ["Language", "Words"],
            [
                ["Catalan",  format_stat(stats["aligned_corpus"]["ca_words"])],
                ["Spanish",  format_stat(stats["aligned_corpus"]["es_words"])],
            ],
        ))
        lines.append("")

    section_specs = [
        ("Distribution by Decade", ["Decade", "Documents", "Share"], distribution_rows(stats["decades"], stats["total"])),
        ("Language Labels", ["Label", "Documents", "Share"], distribution_rows(stats["langs"], stats["total"])),
        ("Translation Status", ["Status", "Documents", "Share"], distribution_rows(stats["traduccio"], stats["total"])),
        ("Textual Variants", ["Variant", "Documents", "Share"], distribution_rows(stats["variants"], stats["total"])),
        (
            "Average Paragraphs by Decade",
            ["Decade", "Average paragraphs per document"],
            [[decade_label, format_stat(avg)] for decade_label, avg in sorted(stats["avg_paras_by_decade"].items())],
        ),
        (
            "Top Authors",
            ["Author", "Documents", "Share"],
            [[author, format_stat(count), format_share(count, stats["total"])] for author, count in stats["top_authors"]],
        ),
    ]

    for title, headers, rows in section_specs:
        lines.extend(text_section(title))
        lines.extend(text_table(headers, rows))
        lines.append("")

    report = "\n".join(lines).rstrip() + "\n"
    out_path.write_text(report, encoding="utf-8")
    print(report)


def write_matplotlib_figures(stats: dict, fig_dir: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed — skipping PNG figures.")
        return

    fig_dir.mkdir(parents=True, exist_ok=True)

    def save_bar(data: dict, filename: str, title: str,
                 color: str = "#3266AD", horizontal: bool = False) -> None:
        labels = list(data.keys())
        values = list(data.values())
        fig_h = max(4, len(labels) * 0.45 + 1.5) if horizontal else 5
        fig, ax = plt.subplots(figsize=(10, fig_h))
        if horizontal:
            ax.barh(labels, values, color=color)
            ax.invert_yaxis()
        else:
            ax.bar(labels, values, color=color)
            plt.xticks(rotation=45, ha="right")
        ax.set_title(title)
        plt.tight_layout()
        plt.savefig(fig_dir / filename, dpi=150)
        plt.close()
        print(f"  PNG → {fig_dir / filename}")

    def save_pie(data: dict, filename: str, title: str) -> None:
        labels = list(data.keys())
        values = list(data.values())
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=140)
        ax.set_title(title)
        plt.tight_layout()
        plt.savefig(fig_dir / filename, dpi=150)
        plt.close()
        print(f"  PNG → {fig_dir / filename}")

    def save_grouped_bar(data: dict[str, int], filename: str, title: str) -> None:
        labels = list(data.keys())
        values = list(data.values())
        fig, ax = plt.subplots(figsize=(7, 5))
        x = range(len(labels))
        ax.bar(x, values, color=["#3266AD", "#1D9E75"])
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=15, ha="right")
        ax.set_title(title)
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"{int(v):,}")
        )
        plt.tight_layout()
        plt.savefig(fig_dir / filename, dpi=150)
        plt.close()
        print(f"  PNG → {fig_dir / filename}")

    print("\nSaving PNG figures...")
    save_bar(stats["decades"],  "01_by_decade.png",   "Documents by decade")
    save_pie(stats["langs"],    "02_lang_pie.png",     "Language / variety")
    save_pie(stats["traduccio"],"03_traduccio_pie.png","Original vs. translation")
    save_bar(stats["variants"], "04_variants.png",     "Textual variants", color="#1D9E75")
    save_bar(stats["avg_paras_by_decade"], "05_avg_para_decade.png",
             "Avg paragraphs / doc by decade", color="#BA7517")
    save_bar(dict(stats["top_authors"]), "06_top_authors.png",
             "Top 15 authors", color="#7F77DD", horizontal=True)
    save_grouped_bar(
        {"CA (raw)": stats["ca_words"], "ES (processed)": stats["es_words"]},
        "07_word_counts.png",
        "Word counts by source",
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Analyze corpus metadata distribution.")
    parser.add_argument("--csv",     type=Path, default=RAW_DIR / "metadata.csv",
                        help="Path to metadata.csv (default: data/raw/metadata.csv)")
    parser.add_argument("--only-processed", action="store_true", help="Keep only documents that exist in data/processed/")
    parser.add_argument("--out-dir", type=Path, default=ANALYSIS_DIR, help="Output directory (default: data/analysis/general/)")
    parser.add_argument("--no-png",    action="store_true", help="Skip matplotlib PNG figures.")
    parser.add_argument(
        "--no-text", "--no-summary",
        dest="no_text",
        action="store_true",
        help="Skip plain-text summary report.",
    )
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--variant", type=str, default=None)
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.csv.exists():
        print(f"ERROR: metadata.csv not found at {args.csv}")
        print("Run 01_load_texts.py first.")
        sys.exit(1)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    args.out_dir = ANALYSIS_DIR / f"run_{stamp}"
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading metadata from {args.csv} ...")
    records = load_metadata(args.csv)
    print(f"  {len(records)} records loaded.")

    if args.only_processed:
        records = [
            r for r in records
            if (PROCESSED_DIR / f"{r['doc_id']}_es.txt").exists()
        ]
        print(f"  {len(records)} translated ES records found in data/processed.")

    if args.year is not None:
        records = [r for r in records if safe_int(r.get("year", "0")) >= args.year]
        print(f"  {len(records)} records after --year {args.year} filter.")

    if args.variant is not None:
        records = [
            r for r in records
            if r.get("variant", "").strip().lower() == args.variant.lower()
        ]
        print(f"  {len(records)} records after --variant {args.variant} filter.")

    stats = compute_stats(records)

    if not args.no_text:
        txt_path = args.out_dir / "corpus_stats.txt"
        write_text_report(stats, txt_path, args)
        print(f"\nText summary saved → {txt_path}")

    if not args.no_png:
        write_matplotlib_figures(stats, args.out_dir / "figures")

    print("\nDone.")


if __name__ == "__main__":
    main()
