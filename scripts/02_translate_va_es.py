"""
02_translate_va_es.py
---------------------
Translates raw Catalan paragraphs into Spanish using Gemma 3 27B IT

Usage:
    python 02_translate_va_es.py                  # translate all docs
    python 02_translate_va_es.py --doc-id book1   # single doc
    python 02_translate_va_es.py --resume         # skip already-translated docs
    python 02_translate_va_es.py --batch-size 4   # override batch size

Input:
    data/raw/<doc_id>.txt
Output:
    data/processed/<doc_id>_es.txt
"""


import argparse
import logging
import sys
import torch
from pathlib import Path
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
from tqdm import tqdm
import pandas as pd

RAW_DIR       = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

MODEL_ID       = "google/gemma-3-27b-it"
BATCH_SIZE     = 12
MAX_NEW_TOKENS = 512
MIN_PARA_LEN   = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("translate.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def load_model(model_id: str):
    log.info(f"Loading model: {model_id} (4-bit NF4)")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    processor = AutoProcessor.from_pretrained(model_id)
    if processor.tokenizer.pad_token is None:
        processor.tokenizer.pad_token = processor.tokenizer.eos_token
        processor.tokenizer.pad_token_id = processor.tokenizer.eos_token_id

    try:
        model = AutoModelForImageTextToText.from_pretrained(
            model_id, quantization_config=bnb_config, device_map="auto", attn_implementation="sdpa"
        )
        log.info("Using SDPA attention.")
    except Exception as e:
        log.warning(f"SDPA unavailable, falling back: {e}")
        model = AutoModelForImageTextToText.from_pretrained(
            model_id, quantization_config=bnb_config, device_map="auto"
        )

    model.eval()

    try:
        model = torch.compile(model)
        log.info("torch.compile applied.")
    except Exception as e:
        log.warning(f"torch.compile skipped: {e}")

    return processor, model


def build_messages(text: str) -> list:
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "source_lang_code": "ca",
                    "target_lang_code": "es",
                    "text": "[Literary text. Preserve register, tone, and style.]\n\n" + text,
                }
            ],
        }
    ]


def translate_batch(processor, model, paragraphs: list[str]) -> list[str]:
    processor.tokenizer.padding_side = "left"

    encoded_list = [
        processor.apply_chat_template(
            build_messages(p),
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        )
        for p in paragraphs
    ]

    max_len = max(e["input_ids"].shape[1] for e in encoded_list)
    pad_id  = processor.tokenizer.pad_token_id

    input_ids      = torch.full((len(paragraphs), max_len), pad_id, dtype=torch.long)
    attention_mask = torch.zeros((len(paragraphs), max_len), dtype=torch.long)

    for i, enc in enumerate(encoded_list):
        seq_len = enc["input_ids"].shape[1]
        input_ids[i, max_len - seq_len:]      = enc["input_ids"][0]
        attention_mask[i, max_len - seq_len:] = enc["attention_mask"][0]

    device = next(model.parameters()).device
    inputs = {
        "input_ids":      input_ids.to(device, dtype=torch.long),
        "attention_mask": attention_mask.to(device),
    }

    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=True,
            pad_token_id=pad_id,
        )

    return [
        processor.decode(ids[max_len:], skip_special_tokens=True).strip()
        for ids in outputs
    ]


def translate_batch_safe(processor, model, paragraphs: list[str]) -> list[str]:
    try:
        return translate_batch(processor, model, paragraphs)
    except torch.cuda.OutOfMemoryError:
        log.warning("OOM on batch — retrying one by one.")
        torch.cuda.empty_cache()
    except Exception as e:
        log.warning(f"Batch error ({e}) — retrying one by one.")

    results = []
    for para in paragraphs:
        try:
            results.extend(translate_batch(processor, model, [para]))
        except Exception as e:
            log.error(f"Single paragraph failed, keeping original: {e}")
            results.append(para)
    return results


def translate_file(doc_id: str, processor, model, resume: bool = False):
    src_path = RAW_DIR       / f"{doc_id}.txt"
    out_path = PROCESSED_DIR / f"{doc_id}_es.txt"

    if resume and out_path.exists():
        log.info(f"[{doc_id}] Already translated — skipping.")
        return

    paragraphs = [
        p.strip()
        for p in src_path.read_text(encoding="utf-8").split("\n\n")
        if p.strip() and len(p.strip()) >= MIN_PARA_LEN
    ]
    log.info(f"[{doc_id}] {len(paragraphs)} paragraph(s) to translate.")

    translations = []
    with open(out_path, "w", encoding="utf-8") as out_f, \
         tqdm(total=len(paragraphs), desc=doc_id, unit="para") as pbar:

        for i in range(0, len(paragraphs), BATCH_SIZE):
            batch = paragraphs[i : i + BATCH_SIZE]
            results = translate_batch_safe(processor, model, batch)

            for translated in results:
                if translations:
                    out_f.write("\n\n")
                out_f.write(translated)
                out_f.flush()
                translations.append(translated)

                idx = len(translations) - 1
                if idx < 3:
                    print(f"\n--- paragraph {idx + 1} ---\n{translated}\n")

            pbar.update(len(batch))

    log.info(f"[{doc_id}] Saved -> {out_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Translate Valencian texts to Spanish with TranslateGemma 27B.")
    parser.add_argument("--doc-id",     type=str, default=None)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--resume",     action="store_true")
    parser.add_argument("--model-id",   type=str, default=MODEL_ID)
    parser.add_argument("--variety",    type=str, default=None,
                        help="Filter by dialect: valencià, central, nord-occidental, balearic")
    parser.add_argument("--year",       type=int, default=None,
                        help="Filter by minimum year (e.g. 1920)")
    parser.add_argument("--stride",     type=int, default=1,
                        help="Take every Nth document (for parallel jobs).")
    parser.add_argument("--offset",     type=int, default=0,
                        help="Starting index within the stride (0-based).")
    return parser.parse_args()


def main():
    args = parse_args()

    global BATCH_SIZE
    BATCH_SIZE = args.batch_size

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    processor, model = load_model(args.model_id)

    if args.doc_id:
        doc_ids = [args.doc_id]
    else:
        doc_ids = [p.stem for p in sorted(RAW_DIR.glob("*.txt"))]

        if args.variety or args.year is not None:
            df = pd.read_csv(RAW_DIR / "metadata.csv")
            df["variant"] = df["variant"].astype(str).str.lower()
            df["year"]    = pd.to_numeric(df["year"], errors="coerce")

            if args.variety:
                variety_map = {
                    "valencia":        "valencià",
                    "valencià":        "valencià",
                    "central":         "central",
                    "nord-occidental": "nord-occidental",
                    "balearic":        "balearic",
                    "balèaric":        "balearic",
                    "balear":          "balearic",
                }
                v  = variety_map.get(args.variety.lower(), args.variety.lower())
                df = df[df["variant"] == v]

            if args.year is not None:
                df = df[df["year"] >= args.year]

            allowed_docs = set(df["doc_id"].astype(str))
            doc_ids      = [d for d in doc_ids if d in allowed_docs]

        doc_ids = doc_ids[args.offset::args.stride]

    if not doc_ids:
        log.warning("No documents found in %s", RAW_DIR)
        return

    for doc_id in doc_ids:
        translate_file(doc_id, processor, model, resume=args.resume)

    log.info("Done.")


if __name__ == "__main__":
    main()