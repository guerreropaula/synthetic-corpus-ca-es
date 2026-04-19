# Data 

This directory holds all input and output data produced throughout the entire corpus building and analysis process, organized by stage.

## Directory Structure

```
data/
├── corpus_ctilc/          # Input: raw CTILC source files (384 files)
├── raw/                   # Stage 1 output: extracted plain-text documents in Catalan (64 files)
├── processed/             # Stage 2 output: Spanish translations (64 files)
└── analysis/
    ├── general/           # Stage 4 output: corpus distribution statistics
    └── linguistic/        # Stage 5 output: linguistic analysis results
```

---

## data/corpus_ctilc/

Raw source files downloaded from the CTILC (Corpus Textual Informatitzat de la Llengua Catalana). Each file is a `.txt` document with an XML-like structure containing a metadata header (`<OBRA>`) and a full-text body (`<TEXT>`).

The collection covers literary texts published between 1832 and 1988. This project uses only works published from 1905 onward. Files are not modified.

See https://ctilc.iec.cat for download instructions and licensing terms.

---

## data/raw/

Output of `01_load_texts.py`. Contains one plain-text file per processed document and the master metadata table.

**Files:**
- `<doc_id>.txt` — paragraph-segmented Catalan source text. Each paragraph occupies one or more lines separated by blank lines. The `doc_id` is a zero-padded six-digit string derived from the CTILC `obra_id` (e.g., `doc_000137`).
- `metadata.csv` — one row per document. Columns:

| Column | Description |
|---|---|
| `doc_id` | Internal document identifier (e.g., `doc_000137`) |
| `obra_id` | Original CTILC numeric identifier |
| `autor` | Author name |
| `titol` | Title |
| `any` | Year of publication |
| `llengua` | Textual domain code (literary in this project) |
| `traduccio` | `1` if the text is a translation into Catalan; `0` if an original |
| `variant` | Dialectal variant (`central`, `valencià`, `nord-occidental`, `baleàric`, `septentrional`) |
| `n_paragraphs` | Number of paragraphs after filtering |

---

## data/processed/

Output of `02_translate_ca_es.py`. Contains one Spanish translation file per document.

**Files:**
- `<doc_id>_es.txt` — Spanish translation, maintaining the same paragraph segmentation as the corresponding source file in `data/raw/`. Each paragraph produced by Gemma-27B-IT occupies one block separated by blank lines.

The document identifier links each translation to its source: `doc_000137_es.txt` corresponds to `doc_000137.txt`.

---

## data/analysis/general/

Output of `04_analyze_corpus.py`. Each run produces a timestamped subdirectory `run_*/` containing:

| File | Description |
|---|---|
| `corpus_stats.txt` | Plain-text summary of all computed statistics |
| `corpus_stats.csv` | Tabular version of the same statistics |
| `*.png` | Figures: temporal distribution, variant distribution, author coverage, word and paragraph count distributions |

---

## data/analysis/linguistic/

Output of `05_linguistics_analysis.py`. Each run produces a timestamped subdirectory `run_*/` with per-language subdirectories and, in comparative mode, a `compare/` directory.

### Per-language directories (ca/ and es/)

| File | Description |
|---|---|
| `unigrams_freq.txt` | Top-N unigrams by frequency after stopword removal |
| `bigrams_freq.txt` | Top-N bigrams by frequency after stopword removal |
| `ngrams_by_decade.txt` | Top-20 bigrams per decade |
| `ngrams_by_variant.txt` | Top-20 bigrams per dialectal variant |
| `lexical_stats.txt` | TTR, MATTR, and hapax legomena by decade and variant |
| `keywords_log_odds.txt` | Log-odds keyword ranking (CA vs. ES in comparative mode; earliest vs. latest decade in single-language mode) |

### compare/ (comparative mode only)

| File | Description |
|---|---|
| `comparative_summary.txt` | Cross-language overview: vocabulary overlap, length ratios, decade-level divergence |
| `comparative_analysis.csv` | All cross-language metrics in tabular form |

