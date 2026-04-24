# Paper
---
**Paula Guerrero Castelló**  

This respository contains the paper *“Building a Synthetic Parallel Catalan–Spanish Corpus of Literary Texts”*.

## Abstract


This paper describes the design and analysis of a synthetic parallel corpus of
Catalan literary texts and their automatic Spanish translations. Starting from plain-text
documents containing XML tags retrieved from the Corpus Textual Informatitzat de la
Llengua Catalana (CTILC), we built a five-script pipeline that (1) loads and normalizes the
raw texts, (2) translates them from Catalan into Spanish using Google’s Gemma3-27B-IT,
(3) postprocesses and builds a paragraph-level bilingual corpus, (4) analyzes the distribution
of the resulting corpus, and finally (5) performs a comparative linguistic analysis covering
log-odds extraction, n-gram frequencies, and lexical richness metrics. The resulting corpus
contains 63 documents (1,577,899 Catalan words; 1,669,666 Spanish words; 30,032 aligned
paragraph pairs) published between 1905 and 1948 and spans five dialectal variants of Cata-
lan. The results shed light on the translation behavior of a large language model in literary
prose: higher hapax rates in Catalan than in Spanish, broadly comparable MATTR scores
across languages, a mild lexical normalization relative to the Catalan source texts regarding
diachronic forms, and a slight tendency for translations to be longer, while preserving many
named entities.


## Keywords

Corpus linguistics · Parallel corpus · Catalan · Spanish · Machine translation

---
***MSc in Language Analysis and Processing***
***University of the Basque Country (UPV/EHU)***  
