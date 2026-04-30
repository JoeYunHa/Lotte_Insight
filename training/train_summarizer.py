"""Train and evaluate a KoBART summarizer on structured Lotte article summaries."""

from __future__ import annotations

import argparse
import inspect
import json
import math

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    EarlyStoppingCallback,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
)

from settings import (
    ARTICLE_SNIPPET_LENGTH,
    DATA_DIR,
    DEFAULT_EVAL_BATCH_SIZE,
    DEFAULT_SUMMARIZER_BATCH_SIZE,
    DEFAULT_SUMMARIZER_EARLY_STOPPING_PATIENCE,
    DEFAULT_SUMMARIZER_EPOCHS,
    DEFAULT_SUMMARIZER_LR,
    DEFAULT_SUMMARIZER_MAX_SOURCE_LEN,
    DEFAULT_SUMMARIZER_MAX_TARGET_LEN,
    DEFAULT_SUMMARIZER_NUM_BEAMS,
    DEFAULT_SUMMARIZER_PRETRAINED,
    DEFAULT_SUMMARIZER_WEIGHT_DECAY,
    DEFAULT_TRAIN_SEED,
    DEFAULT_TRAIN_WARMUP_RATIO,
    DEFAULT_VALIDATION_SPLIT,
    LABELED_PLAYERS_CSV,
    LABELED_TITLES_CSV,
    SUMMARIZER_MODEL_DIR,
)

SUMMARY_REQUIRED_COLUMNS = {
    "event_summary": "",
    "key_players": "",
    "lotte_stance": "neutral",
    "game_ref": "false",
    "game_context": "",
}


def build_source_text(row: dict) -> str:
    parts = [f"title: {str(row.get('title', '')).strip()}"]

    description = str(row.get("description_snippet", "") or "").strip()
    if description:
        parts.append(f"description: {description[:ARTICLE_SNIPPET_LENGTH]}")

    published_at = str(row.get("published_at", "") or "").strip()
    if published_at:
        parts.append(f"published_at: {published_at}")

    topic_label = str(row.get("primary_label", "") or "").strip()
    if topic_label:
        parts.append(f"topic_label: {topic_label}")

    game_context = str(row.get("game_context", "") or "").strip()
    if game_context:
        parts.append(f"game_context: {game_context}")

    return "\n".join(parts)


def build_target_text(row: dict) -> str:
    return str(row.get("event_summary", "") or "").strip()


def load_data() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in [LABELED_TITLES_CSV, LABELED_PLAYERS_CSV]:
        if not path.exists():
            print(f"  Skipped: {path.name} not found")
            continue

        dataframe = pd.read_csv(path, encoding="utf-8-sig")
        for column, default_value in SUMMARY_REQUIRED_COLUMNS.items():
            if column not in dataframe.columns:
                dataframe[column] = default_value
        before = len(dataframe)
        dataframe = dataframe[dataframe["is_lotte_related"].astype(str).str.lower() == "true"].copy()
        dataframe["event_summary"] = dataframe["event_summary"].fillna("").astype(str).str.strip()
        dataframe = dataframe[dataframe["event_summary"] != ""].copy()
        removed = before - len(dataframe)
        print(f"  Loaded: {path.name} ({len(dataframe)} rows, filtered {removed} rows)")
        frames.append(dataframe)

    if not frames:
        raise FileNotFoundError(f"Structured summary training data not found under: {DATA_DIR}")

    dataframe = pd.concat(frames, ignore_index=True)
    dataframe = dataframe.drop_duplicates(subset=["title"]).reset_index(drop=True)
    dataframe["source_text"] = dataframe.apply(build_source_text, axis=1)
    dataframe["target_text"] = dataframe.apply(build_target_text, axis=1)

    print(f"\nTotal usable summary rows: {len(dataframe)}")
    game_ref_count = dataframe["game_ref"].astype(str).str.lower().eq("true").sum()
    print(f"  Rows with game_ref=true       {int(game_ref_count):>4}")
    target_char_lens = [len(text) for text in dataframe["target_text"].tolist()]
    avg_target_len = float(np.mean(target_char_lens)) if target_char_lens else 0.0
    max_target_len = max(target_char_lens) if target_char_lens else 0
    over_192 = sum(1 for length in target_char_lens if length > 192)
    print(f"  Avg target chars              {avg_target_len:.1f}")
    print(f"  Max target chars              {max_target_len}")
    print(f"  Rows likely over 192 chars    {over_192}  (rough truncation risk estimate)")
    return dataframe


class SummaryDataset:
    def __init__(self, encodings):
        self.encodings = encodings

    def __len__(self):
        return len(self.encodings["input_ids"])

    def __getitem__(self, idx):
        return {key: value[idx] for key, value in self.encodings.items()}


def tokenize_dataset(
    tokenizer,
    sources: list[str],
    targets: list[str],
    max_source_len: int,
    max_target_len: int,
):
    model_inputs = tokenizer(
        sources,
        max_length=max_source_len,
        truncation=True,
        padding="max_length",
    )

    labels = tokenizer(
        text_target=targets,
        max_length=max_target_len,
        truncation=True,
        padding="max_length",
    )
    label_ids = []
    for row in labels["input_ids"]:
        label_ids.append([token if token != tokenizer.pad_token_id else -100 for token in row])

    model_inputs["labels"] = label_ids
    return SummaryDataset(model_inputs)


def _char_f1(pred: str, ref: str) -> float:
    pred_chars = set(pred)
    ref_chars = set(ref)
    if not pred_chars or not ref_chars:
        return 0.0
    common = pred_chars & ref_chars
    precision = len(common) / len(pred_chars)
    recall = len(common) / len(ref_chars)
    if precision + recall == 0.0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    if isinstance(predictions, tuple):
        predictions = predictions[0]

    labels = np.where(labels != -100, labels, 0)
    pred_texts = tokenizer_for_metrics.batch_decode(predictions, skip_special_tokens=True)
    label_texts = tokenizer_for_metrics.batch_decode(labels, skip_special_tokens=True)

    exact_match = 0
    char_f1_total = 0.0

    for pred_text, label_text in zip(pred_texts, label_texts, strict=False):
        pred_text = pred_text.strip()
        label_text = label_text.strip()
        if pred_text == label_text:
            exact_match += 1
        char_f1_total += _char_f1(pred_text, label_text)

    total = max(len(pred_texts), 1)
    return {
        "exact_match": exact_match / total,
        "char_f1": char_f1_total / total,
    }


tokenizer_for_metrics = None


def build_training_args(**kwargs):
    signature = inspect.signature(Seq2SeqTrainingArguments.__init__)
    supported = set(signature.parameters)
    normalized = dict(kwargs)

    # Transformers version compatibility:
    # newer versions use `evaluation_strategy`, some builds expose `eval_strategy`.
    if "evaluation_strategy" in normalized and "evaluation_strategy" not in supported and "eval_strategy" in supported:
        normalized["eval_strategy"] = normalized.pop("evaluation_strategy")

    filtered = {key: value for key, value in normalized.items() if key in supported}
    return Seq2SeqTrainingArguments(**filtered)


def build_trainer(model, args, data_collator, compute_metrics, **kwargs):
    signature = inspect.signature(Seq2SeqTrainer.__init__)
    supported = set(signature.parameters)
    normalized = {
        "model": model,
        "args": args,
        "data_collator": data_collator,
        "compute_metrics": compute_metrics,
        **kwargs,
    }

    # Transformers version compatibility:
    # newer versions replaced `tokenizer` with `processing_class`.
    if "tokenizer" in normalized and "tokenizer" not in supported and "processing_class" in supported:
        normalized["processing_class"] = normalized.pop("tokenizer")

    filtered = {key: value for key, value in normalized.items() if key in supported}
    return Seq2SeqTrainer(**filtered)


def train(
    pretrained: str = DEFAULT_SUMMARIZER_PRETRAINED,
    epochs: int = DEFAULT_SUMMARIZER_EPOCHS,
    lr: float = DEFAULT_SUMMARIZER_LR,
    batch_size: int = DEFAULT_SUMMARIZER_BATCH_SIZE,
    seed: int = DEFAULT_TRAIN_SEED,
    max_source_len: int = DEFAULT_SUMMARIZER_MAX_SOURCE_LEN,
    max_target_len: int = DEFAULT_SUMMARIZER_MAX_TARGET_LEN,
    num_beams: int = DEFAULT_SUMMARIZER_NUM_BEAMS,
    early_stopping_patience: int = DEFAULT_SUMMARIZER_EARLY_STOPPING_PATIENCE,
):
    dataframe = load_data()
    train_df, val_df = train_test_split(
        dataframe,
        test_size=DEFAULT_VALIDATION_SPLIT,
        random_state=seed,
    )
    train_df = train_df.reset_index(drop=True)
    val_df = val_df.reset_index(drop=True)

    print(f"\nTrain: {len(train_df)} rows  Validation: {len(val_df)} rows")

    tokenizer = AutoTokenizer.from_pretrained(pretrained)
    model = AutoModelForSeq2SeqLM.from_pretrained(pretrained)

    global tokenizer_for_metrics
    tokenizer_for_metrics = tokenizer

    train_dataset = tokenize_dataset(
        tokenizer,
        train_df["source_text"].tolist(),
        train_df["target_text"].tolist(),
        max_source_len=max_source_len,
        max_target_len=max_target_len,
    )
    eval_dataset = tokenize_dataset(
        tokenizer,
        val_df["source_text"].tolist(),
        val_df["target_text"].tolist(),
        max_source_len=max_source_len,
        max_target_len=max_target_len,
    )

    data_collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model)
    steps_per_epoch = max(1, math.ceil(len(train_dataset) / batch_size))
    warmup_steps = max(0, int(steps_per_epoch * epochs * DEFAULT_TRAIN_WARMUP_RATIO))

    training_args = build_training_args(
        output_dir=str(SUMMARIZER_MODEL_DIR),
        overwrite_output_dir=True,
        num_train_epochs=epochs,
        learning_rate=lr,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=DEFAULT_EVAL_BATCH_SIZE,
        weight_decay=DEFAULT_SUMMARIZER_WEIGHT_DECAY,
        warmup_steps=warmup_steps,
        predict_with_generate=True,
        generation_num_beams=num_beams,
        generation_max_length=max_target_len,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="steps",
        logging_steps=10,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        seed=seed,
        report_to=[],
    )

    trainer = build_trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=early_stopping_patience)],
    )

    trainer.train()
    metrics = trainer.evaluate()
    trainer.save_model(str(SUMMARIZER_MODEL_DIR))
    tokenizer.save_pretrained(str(SUMMARIZER_MODEL_DIR))
    with (SUMMARIZER_MODEL_DIR / "summarizer_config.json").open("w", encoding="utf-8") as file:
        json.dump(
            {
                "pretrained": pretrained,
                "max_source_len": max_source_len,
                "max_target_len": max_target_len,
                "num_beams": num_beams,
            },
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\nSaved summarizer model: {SUMMARIZER_MODEL_DIR}")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return metrics


def evaluate(
    pretrained_dir: str | None = None,
    max_source_len: int = DEFAULT_SUMMARIZER_MAX_SOURCE_LEN,
    max_target_len: int = DEFAULT_SUMMARIZER_MAX_TARGET_LEN,
    num_beams: int = DEFAULT_SUMMARIZER_NUM_BEAMS,
):
    model_dir = pretrained_dir or str(SUMMARIZER_MODEL_DIR)
    dataframe = load_data()
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_dir)

    global tokenizer_for_metrics
    tokenizer_for_metrics = tokenizer

    dataset = tokenize_dataset(
        tokenizer,
        dataframe["source_text"].tolist(),
        dataframe["target_text"].tolist(),
        max_source_len=max_source_len,
        max_target_len=max_target_len,
    )

    data_collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model)
    training_args = build_training_args(
        output_dir=str(SUMMARIZER_MODEL_DIR / "eval_tmp"),
        per_device_eval_batch_size=DEFAULT_EVAL_BATCH_SIZE,
        predict_with_generate=True,
        generation_num_beams=num_beams,
        generation_max_length=max_target_len,
        report_to=[],
    )
    trainer = build_trainer(
        model=model,
        args=training_args,
        eval_dataset=dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )
    metrics = trainer.evaluate()
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretrained", type=str, default=DEFAULT_SUMMARIZER_PRETRAINED)
    parser.add_argument("--epochs", type=int, default=DEFAULT_SUMMARIZER_EPOCHS)
    parser.add_argument("--lr", type=float, default=DEFAULT_SUMMARIZER_LR)
    parser.add_argument("--batch", type=int, default=DEFAULT_SUMMARIZER_BATCH_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_TRAIN_SEED)
    parser.add_argument("--max-source-len", type=int, default=DEFAULT_SUMMARIZER_MAX_SOURCE_LEN)
    parser.add_argument("--max-target-len", type=int, default=DEFAULT_SUMMARIZER_MAX_TARGET_LEN)
    parser.add_argument("--num-beams", type=int, default=DEFAULT_SUMMARIZER_NUM_BEAMS)
    parser.add_argument("--early-stopping-patience", type=int, default=DEFAULT_SUMMARIZER_EARLY_STOPPING_PATIENCE)
    parser.add_argument("--eval-only", action="store_true")
    args = parser.parse_args()

    if args.eval_only:
        evaluate(
            pretrained_dir=str(SUMMARIZER_MODEL_DIR),
            max_source_len=args.max_source_len,
            max_target_len=args.max_target_len,
            num_beams=args.num_beams,
        )
        return

    train(
        pretrained=args.pretrained,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch,
        seed=args.seed,
        max_source_len=args.max_source_len,
        max_target_len=args.max_target_len,
        num_beams=args.num_beams,
        early_stopping_patience=args.early_stopping_patience,
    )


if __name__ == "__main__":
    main()
