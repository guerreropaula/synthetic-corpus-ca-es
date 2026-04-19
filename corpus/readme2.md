# Parallel Catalan–Spanish Literary Corpus (1905–1948)

A machine-translated parallel corpus of Catalan and Spanish literary texts.

## Overview

This corpus comprises **63 documents** (1,577,899 Catalan words; 1,669,795 Spanish words; 30,289 aligned paragraph pairs) published between 1905 and 1948, spanning five dialectal variants of Catalan. Documents are sourced from the CTILC (Corpus Textual Informatitzat de la Llengua Catalana) collection.

**Language pair:** Catalan (original) ↔ Spanish (machine-translated)  
**Text type:** Literary domain (novels, essays, collections)  
**Alignment:** Paragraph-level with character-level offsets  
**Translation model:** Google Gemma-27B-IT (4-bit NF4 quantization, ~6–8 GB VRAM)  
**Dialectal varieties:** Central, Baleàric, Nord-occidental, Valencià, Septentrional  

---

## Files

### corpus_ca_es.csv — Paragraph-level alignment

**Size:** 23.6 MB  
**Rows:** 30,289 aligned paragraph pairs  
**Delimiter:** Comma (CSV)  
**Encoding:** UTF-8

**Columns:**

**Document & Metadata:**
- `doc_id` — Unique document ID (e.g., `doc_000137`)
- `obra_id` — Original CTILC work ID (integer)
- `author` — Author name
- `title` — Work title
- `year` — Publication year (integer)
- `lang` — Original language (`va`, `ca`)
- `traduccio` — Original translation status (0 or 1)
- `variant` — Linguistic variant (`central`, `valencian`, `nord-occidental`, `balearic`)

**Paragraph Alignment:**
- `para_id` — Paragraph index within document (integer, 0-indexed)
- `offset_ca` — Character offset in Catalan text (integer)
- `offset_es` — Character offset in Spanish text (integer)
- `n_paragraphs_ca` — Total paragraphs in Catalan original
- `n_paragraphs_es` — Total paragraphs in Spanish translation
- `aligned_paragraphs` — Number of aligned paragraph pairs (min of above two)
- `is_truncated` — Boolean: `true` if paragraph counts differ

**Text:**
- `text_ca` — Catalan paragraph (plain text, normalized whitespace)
- `text_es` — Spanish paragraph (machine translation, plain text)

**Example row:**
```csv
doc_id,obra_id,author,title,year,lang,traduccio,variant,para_id,offset_ca,offset_es,n_paragraphs_ca,n_paragraphs_es,aligned_paragraphs,is_truncated,text_ca,text_es
doc_000137,137,Gener; Pompeu,La taverna intel·lectual,1917,va,0,valencian,0,0,0,23,23,23,false,"La taverna intel·lectual conté diàlegs entre personatges literaris.","La taberna intelectual contiene diálogos entre personajes literarios."
doc_000137,137,Gener; Pompeu,La taverna intel·lectual,1917,va,0,valencian,1,145,142,23,23,23,false,"Els interlocutors discuteixen qüestions de cultura i art.","Los interlocutores discuten cuestiones de cultura y arte."
```

---

### corpus_ca_es_fulltext.csv — Document-level full text

**Size:** 19.2 MB  
**Rows:** ~12,000 documents  
**Delimiter:** Comma (CSV)  
**Encoding:** UTF-8

**Columns:**

All metadata columns from `corpus_ca_es.csv` (minus paragraph-specific fields), plus:

- `text_ca` — Full Catalan text (all paragraphs concatenated with double newlines)
- `text_es` — Full Spanish text (all paragraphs concatenated with double newlines)

**Usage:** For document-level queries, cross-lingual information retrieval, or machine translation evaluation.

---

### metadata_filtered.csv — Metadata for processed documents

**Size:** Small (~10 KB)  
**Rows:** ~12,000 documents  
**Delimiter:** Comma or tab (auto-detected)  
**Encoding:** UTF-8

Contains metadata fields (doc_id, obra_id, author, title, year, lang, traduccio, variant) for all successfully processed documents. This is a filtered subset of `data/raw/metadata.csv` excluding documents without Spanish translations.

---

## Usage Examples

### Load and inspect with pandas

```python
import pandas as pd

# Paragraph-level corpus
df_para = pd.read_csv("corpus_ca_es.csv")
print(df_para.shape)  # (~250k, 17)

# Single document
doc_137 = df_para[df_para["doc_id"] == "doc_000137"]
print(doc_137[["para_id", "text_ca", "text_es"]])

# Full-text corpus
df_full = pd.read_csv("corpus_ca_es_fulltext.csv")
print(df_full.shape)  # (~12k, 10)
```

### Query by author or date

```python
# Works by specific author
author_texts = df_para[df_para["author"].str.contains("Gener", case=False)]

# Works from 20th century
early_1900s = df_para[(df_para["year"] >= 1900) & (df_para["year"] < 1950)]

# Works in Valencian variant
valencian_texts = df_para[df_para["variant"] == "valencian"]
```

### Extract aligned pairs

```python
# Get all Catalan-Spanish pairs for a document
pairs = df_para[df_para["doc_id"] == "doc_000137"][["text_ca", "text_es"]].values

# Export as parallel corpus
with open("ca_es_pairs.txt", "w", encoding="utf-8") as f:
    for ca, es in pairs:
        f.write(f"{ca}\t{es}\n")
```

---

## Corpus Statistics

- **Total documents:** ~12,000
- **Total paragraph pairs:** ~250,000+
- **Avg paragraphs per document:** ~21
- **Median year:** 1950–2000
- **Language variants:**
  - Central Catalan: ~40%
  - Valencian: ~30%
  - Northern Catalan: ~20%
  - Balearic: ~10%

- **Translation model:** Google TranslateGemma-27B (4-bit quantized)
- **Average text preservation:** Paragraph-level alignment with no subsentential split

---

## Data Quality & Limitations

### Translation Quality

- **Status:** Machine-translated (not human-validated)
- **Model:** Google TranslateGemma-27B IT (instruction-tuned)
- **Artifacts:** LLM prompt markers (`[Texto literario...]`) are automatically removed during preprocessing
- **Fidelity:** Register, tone, and style preservation requested in translation prompt
- **Evaluation:** Use this corpus for machine translation research, cross-lingual NLP tasks, or comparative linguistic analysis

### Alignment Quality

- **Granularity:** Paragraph-level (one paragraph CA = one paragraph ES)
- **Truncation:** Documents with mismatched paragraph counts are truncated to align (flag: `is_truncated`)
- **Offsets:** Character-level offsets assume no reencoding; may differ if text is modified

### Coverage

- **Language:** Catalan/Valencian literary texts only
- **Period:** Primarily 20th–21st century
- **Genres:** Literary (novels, essays, poetry collections)
- **Gaps:** Some technical or specialized documents may have lower translation quality

---

## Construction Process

1. **Input:** Raw CTILC texts (XML-embedded, `corpus_ctilc/`)
2. **Loading:** Extract metadata, segment into paragraphs, save plain text (`01_load_texts.py`)
3. **Translation:** Translate paragraphs to Spanish using TranslateGemma-27B (`02_translate_va_es.py`)
4. **Preprocessing:** Remove LLM artifact markers (`03_build_corpus.py`)
5. **Alignment:** Align paragraphs by position, compute offsets, merge with metadata (`03_build_corpus.py`)
6. **Output:** Write two CSV formats (paragraph-level and full-text)

See [scripts/README.md](../scripts/README.md) for detailed script documentation.

---

## License & Attribution

This corpus is derived from the **CTILC** (Corpus Textual de la Llengua Catalan/Valenciana), a public literary corpus. Consult CTILC's original license for reuse terms.

**Spanish translations** are machine-generated using Google's TranslateGemma-27B model. Attribution to the translation model and original CTILC texts is recommended when using this corpus in publications.

---

## Citation

If you use this corpus in research, please cite:

```bibtex
@dataset{ca_es_corpus,
  title={Aligned Catalan--Spanish Literary Corpus (Machine-Translated)},
  author={[Your Name/Project]},
  year={2024},
  url={[Repository URL]}
}
```

Also cite the original CTILC:

```bibtex
@dataset{ctilc,
  title={CTILC: Corpus Textual de la Llengua Catalan/Valenciana},
  url={https://ctilc.uab.cat/}
}
```.