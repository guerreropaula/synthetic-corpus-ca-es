# Corpus Overview

This directory contains the final parallel (ca-es) literary corpus and its associated metadata, which constitute the main contribution of this work.
It comprises **63 literary texts** (1,577,899 Catalan words; 1,669,795 Spanish words; 30,289 aligned paragraph pairs) within five dialectal variants of Catalan. The target translations have been performed using Google's TranslateGemma-27B IT.


## Corpus Composition

| Property | Value |
|---|---|
| Documents | 63 |
| Publication range | 1905-1948 |
| Catalan words | 1,577,899 |
| Spanish wors | 1,669,795 |
| Aligned paragraph pairs | 30,289 |
| Mean paragraphs per document | 476.7 (median: 395) |
| Dialectal variants | central (56), baleàric (3), nord-occidental (2), valencià (1), septentrional (1) |
| Original Catalan texts | 54 |
| Catalan translations (traduccio=1) | 9 |


## Files in the repository

### corpus_ca_es.csv
Paragraph-level aligned corpus. Each row represents one aligned paragraph pair.

| Column | Description |
|---|---|
| `doc_id` | Document identifier linking to `metadata_filtered.csv` |
| `para_id` | Paragraph index within the document (zero-based) |
| `ca` | Source paragraph in Catalan |
| `es` | Translated paragraph in Spanish |
| `offset_ca` | Character offset of the paragraph in the source `.txt` file |
| `offset_es` | Character offset of the paragraph in the translation `.txt` file |

**Size:** 30,289 aligned paragraph pairs across 63 documents.

---

### corpus_ca_es_fulltext.csv
Document-level corpus. Each row contains the complete text of one document in both languages.

| Column | Description |
|---|---|
| `doc_id` | Document identifier |
| `text_ca` | Full Catalan source text (paragraphs joined) |
| `text_es` | Full Spanish translation (paragraphs joined) |

**Size:** 63 documents; 1,577,899 Catalan words; 1,669,795 Spanish words.

---

### metadata_filtered.csv
Filtered version of the metadata, restricted to the 63 documents present in the final aligned corpus. Produced by `06_filter_metadata.py`. This file serves as the definitive registry of documents included in the corpus.

Columns are identical to `data/raw/metadata.csv`:

| Column | Description |
|---|---|
| `doc_id` | Internal document identifier |
| `obra_id` | Original CTILC numeric identifier |
| `autor` | Author name |
| `titol` | Title |
| `any` | Year of publication |
| `llengua` | Textual domain (`LIT` for all documents in this corpus) |
| `traduccio` | `1` if the Catalan text is itself a translation; `0` if an original |
| `variant` | Dialectal variant of Catalan |
| `n_paragraphs` | Paragraph count |


