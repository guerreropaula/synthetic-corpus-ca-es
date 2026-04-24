# Scripts

This directory contains the five Python scripts that constitute the corpus-building and analysis pipeline. Scripts are numbered and must be executed in order, as each stage depends on the output of the previous one.

## Description

### 01_load_texts.py
Iterates over all `.txt` files in `data/corpus_ctilc/`, parses their XML-like structure, extracts document metadata and paragraph-segmented text, and writes the outputs to `data/raw/`.

**Output:**
- `data/raw/<doc_id>.txt` — one plain-text file per document, paragraph-segmented.
- `data/raw/metadata.csv` — one row per document with fields: `doc_id`, `obra_id`, `autor`, `titol`, `any`, `llengua`, `traduccio`, `variant`, `n_paragraphs`.

**Filtering:** Paragraphs shorter than 30 characters are discarded. Whitespace within paragraphs is normalized.

---

### 02_translate_ca_es.py
Reads each Catalan document from `data/raw/` and translates it paragraph by paragraph into Spanish using Google's Gemma-27B-IT. 

**Output:**
- `data/processed/<doc_id>_es.txt` — translated document, one paragraph per line.

---

### 03_build_corpus.py
Reads source texts from `data/raw/` and translations from `data/processed/`, removes MT prompt-artifact lines (matching the pattern `[Texto literario...]`, `[Literary...]`), aligns documents at the paragraph level, and writes the final corpus.
Filters `data/raw/metadata.csv` to retain only the documents present in `corpus/corpus_ca_es.csv`, producing a clean registry of all documents included in the final corpus (`corpus/metadata_filtered.csv`).

Paragraph counts between source and translation are compared after splitting on blank lines. If they differ, semantic alignment is performed using `intfloat/multilingual-e5-large` via a DP alignment algorithm (vecalign-style).

**Flags:**
- `--dry-run` — preview which lines would be removed without modifying files.
- `--no-preprocess` — skip the artifact removal step.

**Output:**
- `corpus/corpus_ca_es.csv` — paragraph-level aligned corpus; one row per paragraph pair.
- `corpus/corpus_ca_es_fulltext.jsonl` — document-level full texts; one JSON object per line.

**Fields (paragraph-level CSV):**
- `doc_id`, `para_id` — Document and paragraph identifiers
- `offset_ca`, `offset_es` — Character positions in original/translated text
- `n_paragraphs_ca`, `n_paragraphs_es` — Total paragraph counts
- `aligned_paragraphs` — Number of aligned pairs
- `is_truncated` — True if CA and ES paragraph counts differ (e5 alignment was used)
- `text_ca`, `text_es` — Actual paragraph texts
- (Plus all metadata fields from `metadata.csv`)

**Fields (fulltext JSONL):**
- `doc_id` — Document identifier
- `text_ca` — Full Catalan source text (paragraphs joined with `\n\n`)
- `text_es` — Full Spanish translation (paragraphs joined with `\n\n`)
- (Plus all metadata fields from `metadata.csv`)

---

### 04_analyze_corpus.py
Computes descriptive corpus statistics from `data/raw/metadata.csv` and the aligned corpus. By default restricted to documents with an existing Spanish translation (flag `--only-processed`) and filtered by publication year (flag `--year 1905`).

**Statistics produced:**
- Temporal distribution by decade (document counts, average paragraph counts).
- Textual domain and dialectal variant distribution.
- Translation status (original vs. translated into Catalan).
- Top-15 authors by document count.
- Total and per-document word and paragraph counts for both languages.
- Aligned paragraph pair counts and token totals from `corpus/corpus_ca_es.csv`.

**Output:** `data/analysis/general/run_*/`
- `corpus_stats.txt` — plain-text summary report.
- PNG figures for visual comparison.

**Main flags:** `--only-processed`, `--year <YYYY>`, `--variant <variant_name>`.

---

### 05_linguistic_analysis.py
Performs corpus-linguistic analysis. Supports three modes: single-language Catalan (`--lang ca`), single-language Spanish (`--lang es`), and comparative (`--compare`).

**Analyses:**
- **Unigram and bigram frequencies** — top-N after stopword removal; broken down by decade and dialectal variant.
- **Log-odds extraction** — contrasts texts published before 1920 against those published from 1920 onwards, 
in both single-language  and comparative mode. Minimum frequency threshold: `--min-freq` (default: 50).
- **Lexical richness** — Type-Token Ratio (TTR), Moving-Average TTR (MATTR, 100-token windows), and hapax legomena counts and percentages; computed by decade and variant.
- **Comparative metrics** (--compare only) — vocabulary overlap, per-document ES/CA length ratios, decade-level TTR and MATTR divergence.

**Output:** `data/analysis/linguistic/run_*/`
- `ca/` and `es/` subdirectories with per-language files: `unigrams_freq.txt`, `bigrams_freq.txt`, `ngrams_by_decade.txt`, `ngrams_by_variant.txt`, `lexical_stats.txt`, `log_odds.txt`.
- `compare/comparative_summary.txt` (comparative mode only).


**Usage:**
```bash
# Single-language analysis
python scripts/05_linguistic_analysis.py --lang ca            # Catalan
python scripts/05_linguistic_analysis.py --lang es            # Spanish
python scripts/05_linguistic_analysis.py --lang ca --year 1905 --top-n 50

# Comparative analysis (CA vs. ES)
python scripts/05_linguistic_analysis.py --compare
python scripts/05_linguistic_analysis.py --compare --year 1920 --top-n 30

# Other filters
python scripts/05_linguistic_analysis.py --variety central --min-freq 5
```

---

## Execution Order
The commands below must be executed in order with the specified arguments to reproduce the obtained results.
```bash
python 01_load_texts.py
python 02_translate_ca_es.py
python 03_build_corpus.py
python 04_analyze_corpus.py --year 1905 --only-processed
python 05_linguistic_analysis.py --compare --year 1905 --min-freq 50
```
