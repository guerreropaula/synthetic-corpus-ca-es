# Building a Synthetic Parallel Catalan–Spanish Corpus of Literary Texts

Author: **Paula Guerrero Castelló**  


[![Paper](https://img.shields.io/badge/Paper-PDF-red)](paper/paper.pdf)
[![Corpus](https://img.shields.io/badge/Synthetic%20Corpus-CA%2FES-blue)](corpus/corpus_ca_es.csv)

This repository contains the code and methodology for creating, processing, and analyzing a synthetic parallel bilingual corpus (ca-es). The corpus comprises 3 literary documents (totaling ∼1,6 million words) published between 1905 and 1948, translated using an LLM (Gemma-3-27B-IT).

The corpus is intended as a data augmentation resource for training or fine-tuning MT systems.

## Corpus Summary

| Property | Value |
|---|---|
| Documents | 63 |
| Catalan words | 1,577,899 |
| Spanish words | 1,669,666 |
| Aligned paragraph pairs | 30,031 |
| Publication range | 1905-1948 |
| Dialectal variants | 5 (central, valencià, nord-occidental, baleàric, septentrional) |
| Translation system | Gemma3-27B-IT |

## Pipeline Overview

The pipeline consists of six numbered scripts executed in sequence:

1. **01_load_texts.py** — Parses CTILC XML files, extracts paragraphs, writes plain-text documents and `metadata.csv`.
2. **02_translate_ca_es.py** — Translates each document paragraph by paragraph from Catalan to Spanish using Gemma-27B-IT.
3. **03_build_corpus.py** — Removes MT prompt artifacts, aligns source and translation at paragraph level, writes the corpus files. Filters `metadata.csv` to retain only documents included in the final aligned corpus.
4. **04_analyze_corpus.py** — Computes corpus distribution statistics (temporal, variant, author, word counts) and outputs figures.
5. **05_linguistic_analysis.py** — Performs linguistic analysis: unigram/bigram frequencies, log-odds extraction, and lexical richness metrics (TTR, MATTR, hapax legomena).

See `scripts/README.md` for usage instructions and `data/README.md` for a full description of inputs and outputs.


## Repository Structure

```
.
├── scripts/              # Pipeline scripts (01-05)
├── data/
│   ├── raw/              # Original texts (CTILC) and metadata
│   ├── processed/        # Spanish translations generated
│   └── analysis/         # Reports and resulting figures
├── corpus/               # Final corpus (both at paragraph and document-level)
├── paper/                # Paper describing the methodology and results 
└── README.md
```

## Installation & Usage

### 1. Clone the repository

```
git clone git@github.com:guerreropaula/synthetic-corpus-ca-es.git
cd synthetic-corpus-ca-es
```
### 2. Install dependencies

```
python -m venv env
source env/bin/activate
```

```bash
# PyTorch with CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# All dependencies
pip install -r requirements.txt
```


## Data Source

Source texts are drawn from the **Corpus Textual Informatitzat de la Llengua Catalana (CTILC)**, developed by the Institut d'Estudis Catalans (IEC). The texts included in this project have entered the public domain and are available for research use under a Creative Commons license. See https://ctilc.iec.cat for details.

## Citation

If you use this corpus or code, please cite:

```bibtex
@misc{guerrero2026ca_es_corpus,
  author       = {Guerrero Castelló, Paula},
  title        = {Building a Synthetic Parallel Catalan-Spanish Corpus of Literary Texts},
  year         = {2026},
  institution  = {University of the Basque Country (UPV/EHU)},
  note         = {Unpublished manuscript},
  url          = {https://github.com/guerreropaula/synthetic-corpus-ca-es}
}

```
Also cite the CTILC corpus:

```bibtex
@misc{ctilc_iec,
  author       = {{Institut d'Estudis Catalans}},
  title        = {Corpus Textual Informatitzat de la Llengua Catalana (CTILC)},
  year         = {2015},
  howpublished = {\url{https://ctilc.iec.cat}},
  note         = {Online corpus. Data digitalized and processed by the Institut d'Estudis Catalans}
}
```

For detailed documentation see [data/README.md](data/README.md), [scripts/README.md](scripts/README.md), and [corpus/README.md](corpus/README.md).

> The original texts remain the property of their respective authors and are distributed under the licensing terms of the CTILC corpus. The compiled dataset and code are provided for research purposes.

### Contact
**Contact:** [guerrerocastellopaula@gmail.com](mailto:guerrerocastellopaula@gmail.com)

---
*Project for Corpus Linguistics 2025-26*   
*Master's in Language Analysis and Processing (UPV/EHU)*  