"""
05_linguistic_analysis.py
--------------------------
Extended corpus linguistics analysis supporting:
  • Original Catalan texts          (data/raw/<doc_id>.txt)
  • Translated Spanish texts        (data/processed/<doc_id>_es.txt)
  • Comparative Catalan ↔ Spanish analysis

Covers: collocations, log-odds (early vs. late period), n-gram frequencies,
        type-token ratio, lexical richness (overall + per-decade + per-variant),
        and — in comparative mode — cross-language alignment metrics.

Reads:
    data/raw/metadata.csv
    data/raw/<doc_id>.txt            (Catalan originals)
    data/processed/<doc_id>_es.txt   (Spanish translations)

Produces:
    data/analysis/linguistic/run_<stamp>/<lang|compare>/
        log_odds.txt                   (early vs late period)
        unigrams_freq.txt
        bigrams_freq.txt
        ngrams_by_decade.txt
        ngrams_by_variant.txt
        lexical_stats.txt              (overall + by decade + by variant)
        comparative_summary.txt        (--compare mode only)

Usage — single language:
    python scripts/05_linguistic_analysis.py                      # Spanish (default)
    python scripts/05_linguistic_analysis.py --lang ca            # Catalan originals
    python scripts/05_linguistic_analysis.py --lang es            # Spanish translations
    python scripts/05_linguistic_analysis.py --lang ca --split-year 1925
    python scripts/05_linguistic_analysis.py --lang es --variety central
    python scripts/05_linguistic_analysis.py --lang ca --top-n 50 --min-freq 5

Usage — comparative:
    python scripts/05_linguistic_analysis.py --compare
    python scripts/05_linguistic_analysis.py --compare --split-year 1925
    python scripts/05_linguistic_analysis.py --compare --variety central
    python scripts/05_linguistic_analysis.py --compare --top-n 30 --min-freq 10
"""

import argparse
import csv
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from itertools import islice
from pathlib import Path

RAW_DIR           = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR     = Path(__file__).parent.parent / "data" / "processed"
ANALYSIS_ROOT_DIR = Path(__file__).parent.parent / "data" / "analysis"
ANALYSIS_DIR      = ANALYSIS_ROOT_DIR / "linguistic"

DEFAULT_SPLIT_YEAR = 1920   


STOPWORDS_ES = {
    "de","la","el","en","y","a","que","los","se","del","las","un","por","con",
    "una","su","para","es","al","lo","como","más","pero","sus","le","ya","o",
    "fue","este","ha","si","sobre","ser","tiene","son","entre","cuando","muy",
    "sin","hasta","hay","donde","quien","desde","todo","nos","durante","todos",
    "uno","les","ni","contra","otros","ese","eso","ante","ellos","e","esto",
    "mí","antes","algunos","qué","unos","yo","otro","otras","otra","él","tanto",
    "esa","estos","mucho","quienes","nada","muchos","cual","poco","ella","estar",
    "estas","algunas","algo","nosotros","mi","mis","tú","te","ti","tu","tus",
    "ellas","nos","vosotros","vosotras","os","mío","mía","míos","mías","tuyo",
    "era","también","así","porque","cada","aún","han",
}

STOPWORDS_CA = {
    "de","la","el","en","i","a","que","els","es","del","les","un","per","amb",
    "una","seu","para","és","al","lo","com","més","però","seus","li","ja","o",
    "va","este","ha","si","sobre","ser","té","son","entre","quan","molt",
    "sense","fins","hi","on","qui","des","tot","ens","durant","tots",
    "uns","els","ni","contra","altres","aquest","això","davant","ells","e","açò",
    "abans","alguns","què","uns","jo","altre","altres","altra","ell","tant",
    "esta","aquests","molt","qui","res","molts","qual","poc","ella","estar",
    "estes","algunes","algo","nosaltres","mi","mes","tu","te","ti","teu","teus",
    "elles","ens","vosaltres","vosaltres","us","meu","meva","meus","meves","teva",
    "era","també","així","perquè","cada","encara","han","hem","heu","seu","seva",
    "al","del","pel","pels","als","dels",
}

STOPWORDS = {"ca": STOPWORDS_CA, "es": STOPWORDS_ES}


def safe_int(val, fallback=0):
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return fallback


def decade(year):
    return f"{(year // 10) * 10}s" if year else "unknown"


def load_metadata(csv_path):
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_header(args):
    split = getattr(args, "split_year", DEFAULT_SPLIT_YEAR)
    return "\n".join([
        "CORPUS RUN INFO\n",
        f"date       : {datetime.now()}",
        f"lang       : {getattr(args, 'lang', None)}",
        f"compare    : {getattr(args, 'compare', False)}",
        f"split_year : <{split} (early)  vs  >={split} (late)",
        f"variety    : {getattr(args, 'variety', None)}",
        f"top_n      : {getattr(args, 'top_n', None)}",
        f"min_freq   : {getattr(args, 'min_freq', None)}",
    ])


def filter_records(records, args):
    def has_file(r):
        ca_ok = (RAW_DIR / f"{r['doc_id']}.txt").exists()
        es_ok = (PROCESSED_DIR / f"{r['doc_id']}_es.txt").exists()
        if getattr(args, "compare", False):
            return ca_ok and es_ok
        elif getattr(args, "lang", "es") == "ca":
            return ca_ok
        else:
            return es_ok

    records = [r for r in records if has_file(r)]
    
    if getattr(args, "year", None) is not None:
        records = [r for r in records if safe_int(r.get("year", "0")) >= args.year]

    if getattr(args, "variety", None):
        variety_map = {
            "valencia": "valencià", "valencià": "valencià",
            "central": "central",
            "nord-occidental": "nord-occidental",
            "balearic": "balearic", "balèaric": "balearic", "balear": "balearic",
        }
        target = variety_map.get(args.variety.lower(), args.variety.lower())
        records = [r for r in records if r.get("variant", "").strip().lower() == target]

    stride = getattr(args, "stride", 1)
    offset = getattr(args, "offset", 0)
    if stride > 1:
        records = records[offset::stride]

    return records


def tokenize(text, lang="es", remove_stopwords=True):
    if lang == "ca":
        pattern = r"\b[a-záéíóúüïàèòçl·]{3,}\b"
    else:
        pattern = r"\b[a-záéíóúüñ]{3,}\b"
    tokens = re.findall(pattern, text.lower())
    if remove_stopwords:
        sw = STOPWORDS.get(lang, STOPWORDS_ES)
        tokens = [t for t in tokens if t not in sw]
    return tokens


def load_doc(doc_id, lang="es"):
    if lang == "ca":
        path = RAW_DIR / f"{doc_id}.txt"
    else:
        path = PROCESSED_DIR / f"{doc_id}_es.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def ngrams(tokens, n):
    return zip(*[islice(tokens, i, None) for i in range(n)])


def count_ngrams(tokens, n):
    return Counter(ngrams(tokens, n))

def word_bigram_freq_from_tokens(tokens):
    word_freq   = Counter()
    bigram_freq = Counter()
    for i in range(len(tokens) - 1):
        word_freq[tokens[i]] += 1
        bigram_freq[f"{tokens[i]}\t{tokens[i + 1]}"] += 1
    if tokens:
        word_freq[tokens[-1]] += 1
    return word_freq, bigram_freq


def log_odds(freq_i, total_i, freq_j, total_j):
    p_i = freq_i / total_i if total_i else 0
    p_j = freq_j / total_j if total_j else 0
    o_i = p_i / (1 - p_i) if p_i < 1 else float("inf")
    o_j = p_j / (1 - p_j) if p_j < 1 else float("inf")
    if o_i <= 0 or o_j <= 0:
        return 0.0
    return math.log(o_i) - math.log(o_j)


def compute_log_odds_keywords(group_a_tokens, group_b_tokens, min_freq=20):
    freq_a  = Counter(group_a_tokens)
    freq_b  = Counter(group_b_tokens)
    total_a = len(group_a_tokens)
    total_b = len(group_b_tokens)
    vocab   = (set(w for w, c in freq_a.items() if c >= min_freq) |
               set(w for w, c in freq_b.items() if c >= min_freq))
    scores  = {}
    for w in vocab:
        fa = freq_a.get(w, 0)
        fb = freq_b.get(w, 0)
        if fa + fb < min_freq:
            continue
        scores[w] = log_odds(fa or 0.5, total_a, fb or 0.5, total_b)
    return sorted(scores.items(), key=lambda x: -abs(x[1]))


def lexical_stats(tokens_raw):
    types  = len(set(tokens_raw))
    tokens = len(tokens_raw)
    ttr    = types / tokens if tokens else 0
    window = 500
    if tokens >= window:
        ttrs  = [len(set(tokens_raw[i:i + window])) / window
                 for i in range(0, tokens - window + 1, window)]
        mattr = sum(ttrs) / len(ttrs)
    else:
        mattr = ttr
    freq  = Counter(tokens_raw)
    hapax = sum(1 for c in freq.values() if c == 1)
    return {
        "tokens":    tokens,
        "types":     types,
        "ttr":       round(ttr, 4),
        "mattr":     round(mattr, 4),
        "hapax":     hapax,
        "hapax_pct": round(hapax / types * 100, 1) if types else 0,
    }


def vocabulary_overlap(tokens_ca, tokens_es):
    types_ca = set(tokens_ca)
    types_es = set(tokens_es)
    shared   = types_ca & types_es
    r_ca     = len(shared) / len(types_ca) if types_ca else 0
    r_es     = len(shared) / len(types_es) if types_es else 0
    return shared, round(r_ca, 4), round(r_es, 4)


def length_ratio_stats(records):
    rows = []
    for r in records:
        ca_text = load_doc(r["doc_id"], "ca")
        es_text = load_doc(r["doc_id"], "es")
        ca_tok  = tokenize(ca_text, "ca", remove_stopwords=False)
        es_tok  = tokenize(es_text, "es", remove_stopwords=False)
        ratio   = len(es_tok) / len(ca_tok) if ca_tok else 0
        rows.append({
            "doc_id":    r["doc_id"],
            "title":     r.get("title", "")[:60],
            "year":      r.get("year", ""),
            "variant":   r.get("variant", ""),
            "ca_tokens": len(ca_tok),
            "es_tokens": len(es_tok),
            "ratio":     round(ratio, 4),
        })
    return rows


def decade_lexical_divergence(lex_ca_dec, lex_es_dec):
    decades = sorted(set(lex_ca_dec) | set(lex_es_dec))
    rows    = []
    for d in decades:
        ca = lex_ca_dec.get(d, {})
        es = lex_es_dec.get(d, {})
        rows.append({
            "decade":       d,
            "ca_ttr":       ca.get("ttr", 0),
            "es_ttr":       es.get("ttr", 0),
            "ca_mattr":     ca.get("mattr", 0),
            "es_mattr":     es.get("mattr", 0),
            "ca_hapax_pct": ca.get("hapax_pct", 0),
            "es_hapax_pct": es.get("hapax_pct", 0),
            "ttr_delta":    round((es.get("ttr", 0) or 0) - (ca.get("ttr", 0) or 0), 4),
        })
    return rows


def fmt_section(title, lines):
    bar = "=" * 60
    return "\n".join(["", bar, f"  {title}", bar] + lines)


def write_collocations(pmi_items, top_n, out_path, args=None):
    pass


def write_keywords(scored, top_n, out_path, args, label_a, label_b):
    top_a = [(w, s) for w, s in scored if s > 0][:top_n]
    top_b = [(w, s) for w, s in scored if s < 0][:top_n]
    lines = []
    if args is not None:
        lines.append(run_header(args))
        lines.append("")
    lines.append(fmt_section(
        "Log-Odds Ratio (period comparison)",
        [
            f"  >> Distinctive of {label_a} (positive log-odds)",
            *[f"  {w:<30} {s:>8.4f}" for w, s in top_a],
            "",
            f"  >> Distinctive of {label_b} (negative log-odds)",
            *[f"  {w:<30} {s:>8.4f}" for w, s in top_b],
        ],
    ))
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_unigram_freq(word_freq, top_n, out_path, args=None):
    lines = []
    if args is not None:
        lines.append(run_header(args))
    lines.append(fmt_section(
        f"Top {top_n} Unigrams by Frequency",
        [
            f"  {'WORD':<35} {'FREQ':>8}",
            *[
                f"  {word:<35} {count:>8}"
                for word, count in word_freq.most_common(top_n)
            ],
        ],
    ))
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_bigram_freq_tsv(bigram_freq, top_n, out_path, args=None):
    lines = []
    if args is not None:
        lines.append(run_header(args))
    lines.append(fmt_section(
        f"Top {top_n} Bigrams by Frequency",
        [
            f"  {'BIGRAM':<40} {'FREQ':>8}",
            *[
                f"  {pair.replace(chr(9), ' '):<40} {count:>8}"
                for pair, count in bigram_freq.most_common(top_n)
            ],
        ],
    ))
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_ngram_freq(counter, n, top_n, out_path, args=None):
    pass


def write_ngram_by_group(group_counters, n, top_n, out_path, args=None):
    lines = []
    if args is not None:
        lines.append(run_header(args))
    for group, counter in sorted(group_counters.items()):
        lines.append(f"\n  --- {group} ---")
        lines += [
            f"  {' '.join(ng):<50} {c}"
            for ng, c in counter.most_common(top_n)
        ]
    noun = "Bigrams" if n == 2 else "Trigrams"
    out_path.write_text(fmt_section(f"{noun} by Group", lines), encoding="utf-8")


def write_lexical_stats(overall_ca, overall_es, stats_by_group, out_path, args=None):
    header = (
        f"  {'GROUP':<28} {'TOKENS':>8} {'TYPES':>8} "
        f"{'TTR':>7} {'MATTR':>7} {'HAPAX':>7} {'HAPAX%':>7}"
    )
    sep = "  " + "-" * 80

    lines = []
    if args is not None:
        lines.append(run_header(args))

    overall_section = [header, sep]
    for lang_label, s in [("Overall [CA]", overall_ca), ("Overall [ES]", overall_es)]:
        if s:
            overall_section.append(
                f"  {lang_label:<28} {s['tokens']:>8,} {s['types']:>8,} "
                f"{s['ttr']:>7.4f} {s['mattr']:>7.4f} "
                f"{s['hapax']:>7,} {s['hapax_pct']:>6.1f}%"
            )
    lines.append(fmt_section("Overall Lexical Statistics: CA vs ES", overall_section))

    group_section = [header, sep]
    for group, s in sorted(stats_by_group.items()):
        group_section.append(
            f"  {group:<28} {s['tokens']:>8,} {s['types']:>8,} "
            f"{s['ttr']:>7.4f} {s['mattr']:>7.4f} "
            f"{s['hapax']:>7,} {s['hapax_pct']:>6.1f}%"
        )
    lines.append(fmt_section("Lexical Statistics by Decade and Variant", group_section))

    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_comparative_txt(records, lex_ca_dec, lex_es_dec,
                           tokens_ca, tokens_es, top_n, out_path, args):
    lines = [run_header(args)]

    lines.append(fmt_section("Corpus Overview", [
        f"  Documents analysed : {len(records)}",
        f"  CA total tokens    : {len(tokens_ca):,}",
        f"  ES total tokens    : {len(tokens_es):,}",
        f"  ES/CA token ratio  : {len(tokens_es)/len(tokens_ca):.4f}" if tokens_ca else "",
    ]))

    shared, r_ca, r_es = vocabulary_overlap(tokens_ca, tokens_es)
    lines.append(fmt_section("Vocabulary Overlap (shared surface forms)", [
        f"  Shared types : {len(shared):,}",
        f"  Overlap/CA   : {r_ca:.4f}",
        f"  Overlap/ES   : {r_es:.4f}",
        "",
        "  Sample shared types:",
    ] + [f"    {w}" for w in sorted(shared)[:30]]))

    div = decade_lexical_divergence(lex_ca_dec, lex_es_dec)
    hdr = (
        f"  {'DECADE':<10} {'CA_TTR':>8} {'ES_TTR':>8} {'ΔTTR':>8} "
        f"{'CA_MATTR':>10} {'ES_MATTR':>10}"
    )
    rows = [hdr, "  " + "-" * 60]
    for d in div:
        rows.append(
            f"  {d['decade']:<10} {d['ca_ttr']:>8.4f} {d['es_ttr']:>8.4f} "
            f"{d['ttr_delta']:>+8.4f} {d['ca_mattr']:>10.4f} {d['es_mattr']:>10.4f}"
        )
    lines.append(fmt_section("Lexical Richness Divergence by Decade (ES − CA)", rows))

    lr = length_ratio_stats(records)
    hdr2 = f"  {'DOC_ID':<15} {'YEAR':>6} {'CA_TOK':>8} {'ES_TOK':>8} {'RATIO':>7}"
    lr_rows = [hdr2, "  " + "-" * 50]
    for row in sorted(lr, key=lambda x: x["ratio"], reverse=True)[:top_n]:
        lr_rows.append(
            f"  {row['doc_id']:<15} {str(row['year']):>6} "
            f"{row['ca_tokens']:>8,} {row['es_tokens']:>8,} {row['ratio']:>7.4f}"
        )
    lines.append(fmt_section(f"Top {top_n} Docs by ES/CA Length Ratio", lr_rows))

    out_path.write_text("\n".join(lines), encoding="utf-8")


def run_analysis(records, lang, args, split_year=None):
    if split_year is None:
        split_year = getattr(args, "split_year", DEFAULT_SPLIT_YEAR)

    all_tokens_clean = []
    early_tokens     = []
    late_tokens      = []
    decade_tokens    = defaultdict(list)
    variant_tokens   = defaultdict(list)

    for r in records:
        text = load_doc(r["doc_id"], lang)
        if not text:
            print(f"  WARNING: no file for {r['doc_id']} [{lang}], skipping.")
            continue
        clean = tokenize(text, lang, remove_stopwords=True)
        all_tokens_clean.extend(clean)

        year = safe_int(r.get("year", "0"))
        if year and year < split_year:
            early_tokens.extend(clean)
        else:
            late_tokens.extend(clean)

        dec = decade(year)
        var = r.get("variant", "unspecified").strip() or "unspecified"
        decade_tokens[dec].extend(clean)
        variant_tokens[var].extend(clean)

    print(f"  [{lang}] Total tokens: {len(all_tokens_clean):,}  "
          f"Early (<{split_year}): {len(early_tokens):,}  "
          f"Late (≥{split_year}): {len(late_tokens):,}")

    if not early_tokens or not late_tokens:
        print(f"  WARNING: one period has no tokens. "
              f"Try adjusting --split-year (current: {split_year}).")

    label_a = f"early (<{split_year})"
    label_b = f"late (≥{split_year})"

    kw_scores = compute_log_odds_keywords(early_tokens, late_tokens,
                                          min_freq=args.min_freq)

    unigram_counts, bigram_tsv_counts = word_bigram_freq_from_tokens(all_tokens_clean)

    lex_decade  = {d: lexical_stats(toks) for d, toks in decade_tokens.items()}
    lex_variant = {v: lexical_stats(toks) for v, toks in variant_tokens.items()}
    lex_total   = lexical_stats(all_tokens_clean)

    return {
        "keywords":            kw_scores,
        "kw_label_a":          label_a,
        "kw_label_b":          label_b,
        "unigrams":            unigram_counts,
        "bigrams_tsv":         bigram_tsv_counts,
        "bigrams_by_decade":   {d: count_ngrams(toks, 2) for d, toks in decade_tokens.items()},
        "bigrams_by_variant":  {v: count_ngrams(toks, 2) for v, toks in variant_tokens.items()},
        "lex_decade":          lex_decade,
        "lex_variant":         lex_variant,
        "lex_total":           lex_total,
        "lex_total_tokens_raw": all_tokens_clean,
        "dec_keys":            sorted(decade_tokens.keys()),
        "decade_tokens":       decade_tokens,
    }


def save_single_outputs(stats, lang, out_dir, args):
    write_keywords(
        stats["keywords"], args.top_n,
        out_dir / "log_odds.txt",
        args=args,
        label_a=stats["kw_label_a"],
        label_b=stats["kw_label_b"],
    )

    write_unigram_freq(stats["unigrams"], args.top_n,
                       out_dir / "unigrams_freq.txt", args)

    write_bigram_freq_tsv(stats["bigrams_tsv"], args.top_n,
                          out_dir / "bigrams_freq.txt", args)

    write_ngram_by_group(stats["bigrams_by_decade"],  2, 20,
                         out_dir / "ngrams_by_decade.txt",  args)
    write_ngram_by_group(stats["bigrams_by_variant"], 2, 20,
                         out_dir / "ngrams_by_variant.txt", args)

    grouped = {
        **{f"[decade]  {k}": v for k, v in stats["lex_decade"].items()},
        **{f"[variant] {k}": v for k, v in stats["lex_variant"].items()},
    }
    write_lexical_stats(
        overall_ca=stats.get("lex_total") if lang == "ca" else None,
        overall_es=stats.get("lex_total") if lang == "es" else None,
        stats_by_group=grouped,
        out_path=out_dir / "lexical_stats.txt",
        args=args,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Corpus linguistics analysis — Catalan originals and/or Spanish translations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    lang_grp = parser.add_mutually_exclusive_group()
    lang_grp.add_argument(
        "--lang", type=str, default="es", choices=["ca", "es"],
        help="Language to analyse: 'ca' for Catalan originals, 'es' for Spanish (default: es).",
    )
    lang_grp.add_argument(
        "--compare", action="store_true",
        help="Run deep comparative analysis across both CA and ES corpora.",
    )

    parser.add_argument("--csv",        type=Path, default=RAW_DIR / "metadata.csv")
    parser.add_argument("--split-year", type=int,  default=DEFAULT_SPLIT_YEAR,
                        help=f"Year threshold dividing early vs. late period "
                             f"for log-odds keywords (default: {DEFAULT_SPLIT_YEAR}).")
    parser.add_argument("--variety",    type=str,  default=None,
                        help="Filter by dialect variant.")
    parser.add_argument("--stride",     type=int,  default=1)
    parser.add_argument("--offset",     type=int,  default=0)
    
    parser.add_argument("--year", type=int, default=None,
                    help="Only include documents from this year onwards.")

    parser.add_argument("--top-n",      type=int,  default=50)
    parser.add_argument("--min-freq",   type=int,  default=5)

    parser.add_argument("--out-dir",    type=Path, default=None)

    return parser.parse_args()


def main():
    args = parse_args()

    if not args.csv.exists():
        print(f"ERROR: {args.csv} not found. Run 01_load_texts.py first.")
        sys.exit(1)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.out_dir:
        base_dir = args.out_dir
    else:
        base_dir = ANALYSIS_DIR / f"run_{stamp}"

    records = load_metadata(args.csv)
    print(f"  {len(records)} records loaded from metadata.")
    records = filter_records(records, args)
    print(f"  {len(records)} records after filters.")

    if not records:
        print("No documents match the filters. Exiting.")
        sys.exit(0)

    if args.compare:
        print("\n── COMPARATIVE MODE (CA ↔ ES) ──")

        print("\n[1/2] Analysing Catalan originals…")
        out_ca = base_dir / "compare" / "ca"
        out_ca.mkdir(parents=True, exist_ok=True)
        stats_ca = run_analysis(records, "ca", args)

        print("\n[2/2] Analysing Spanish translations…")
        out_es = base_dir / "compare" / "es"
        out_es.mkdir(parents=True, exist_ok=True)
        stats_es = run_analysis(records, "es", args)

        tokens_ca = stats_ca["lex_total_tokens_raw"]
        tokens_es = stats_es["lex_total_tokens_raw"]

        def save_compare_outputs(stats_ca, stats_es):
            grouped_ca = {
                **{f"[decade]  {k}": v for k, v in stats_ca["lex_decade"].items()},
                **{f"[variant] {k}": v for k, v in stats_ca["lex_variant"].items()},
            }
            write_lexical_stats(
                overall_ca=stats_ca["lex_total"],
                overall_es=stats_es["lex_total"],
                stats_by_group=grouped_ca,
                out_path=out_ca / "lexical_stats.txt",
                args=args,
            )
            grouped_es = {
                **{f"[decade]  {k}": v for k, v in stats_es["lex_decade"].items()},
                **{f"[variant] {k}": v for k, v in stats_es["lex_variant"].items()},
            }
            write_lexical_stats(
                overall_ca=stats_ca["lex_total"],
                overall_es=stats_es["lex_total"],
                stats_by_group=grouped_es,
                out_path=out_es / "lexical_stats.txt",
                args=args,
            )

        for stats, out_dir, lang in [(stats_ca, out_ca, "ca"), (stats_es, out_es, "es")]:
            write_keywords(
                stats["keywords"], args.top_n,
                out_dir / "log_odds.txt",
                args=args,
                label_a=stats["kw_label_a"],
                label_b=stats["kw_label_b"],
            )
            write_unigram_freq(stats["unigrams"], args.top_n,
                               out_dir / "unigrams_freq.txt", args)
            write_bigram_freq_tsv(stats["bigrams_tsv"], args.top_n,
                                  out_dir / "bigrams_freq.txt", args)
            write_ngram_by_group(stats["bigrams_by_decade"],  2, 20,
                                 out_dir / "ngrams_by_decade.txt",  args)
            write_ngram_by_group(stats["bigrams_by_variant"], 2, 20,
                                 out_dir / "ngrams_by_variant.txt", args)

        save_compare_outputs(stats_ca, stats_es)

        print("\nBuilding comparative outputs…")
        out_cmp = base_dir / "compare"
        write_comparative_txt(
            records,
            stats_ca["lex_decade"], stats_es["lex_decade"],
            tokens_ca,              tokens_es,
            args.top_n,
            out_cmp / "comparative_summary.txt",
            args,
        )

        print(f"\nAll comparative outputs → {out_cmp}")

    else:
        lang = args.lang
        print(f"\n── SINGLE-LANGUAGE MODE [{lang.upper()}] ──")
        out_dir = base_dir / lang
        out_dir.mkdir(parents=True, exist_ok=True)
        stats = run_analysis(records, lang, args)
        save_single_outputs(stats, lang, out_dir, args)
        print(f"\nAll outputs → {out_dir}")

    print("\nDone.")


if __name__ == "__main__":
    main()