# Model Training Process

## Overview

The current pipeline under `training/` trains a KoELECTRA-based 8-label multi-label classifier for Lotte Giants news articles.

The implementation is centered in [train_classifier.py](/C:/Users/yunha/Desktop/lotte-insight/training/train_classifier.py), with shared CSV utilities in [collect_utils.py](/C:/Users/yunha/Desktop/lotte-insight/training/collect_utils.py), label definitions in [label_schema.py](/C:/Users/yunha/Desktop/lotte-insight/training/label_schema.py), and default paths and hyperparameters in [settings.py](/C:/Users/yunha/Desktop/lotte-insight/training/settings.py).

## Source Data

Training reads these two files:

- `training/data/labeled_titles.csv`
- `training/data/labeled_players.csv`

These are defined by `LABELED_TITLES_CSV` and `LABELED_PLAYERS_CSV` in [settings.py](/C:/Users/yunha/Desktop/lotte-insight/training/settings.py).

## CSV Schema

The shared CSV header is `CSV_HEADERS` in [collect_utils.py](/C:/Users/yunha/Desktop/lotte-insight/training/collect_utils.py).

| Field | Purpose |
| --- | --- |
| `id` | Row identifier |
| `title` | Article title |
| `description_snippet` | Short article description |
| `source_name` | Publisher / domain |
| `published_at` | Normalized publication time |
| `primary_label` | Main label from GPT/manual review |
| `secondary_labels` | Additional labels separated by `;` |
| `confidence_score` | Labeling confidence |
| `confidence_note` | Reason for uncertainty |
| `detected_players` | Detected player names separated by `;` |
| `is_lotte_related` | Hard inclusion flag for training |

Only these columns are used directly for model input/targets:

- `title`
- `description_snippet`
- `primary_label`
- `secondary_labels`
- `is_lotte_related`

The remaining columns are metadata for collection, audit, and review.

## Label Set

The fixed label order is defined in [label_schema.py](/C:/Users/yunha/Desktop/lotte-insight/training/label_schema.py):

```text
[
  INJURY_ROSTER,
  TRANSACTION_CONTRACT,
  MATCH_RELATED,
  PERFORMANCE_ANALYSIS,
  INTERVIEW,
  PLAYER_RELATED,
  CLUB_OPERATION,
  ETC,
]
```

This order is used for:

- multi-hot encoding
- model output dimension
- saved `label_encoder.json`
- evaluation reports

## Data Collection and Labeling

The training CSV files are produced by:

- [collect_for_labeling.py](/C:/Users/yunha/Desktop/lotte-insight/training/collect_for_labeling.py)
- [collect_players.py](/C:/Users/yunha/Desktop/lotte-insight/training/collect_players.py)

Shared preprocessing happens in `item_to_row()` inside [collect_utils.py](/C:/Users/yunha/Desktop/lotte-insight/training/collect_utils.py):

- strip HTML from title and description
- truncate `description_snippet` to `ARTICLE_SNIPPET_LENGTH` (`120`)
- derive `source_name` from the article URL
- normalize `published_at`

`auto_label()` then fills:

- `primary_label`
- `secondary_labels`
- `confidence_score`
- `confidence_note`
- `detected_players`
- `is_lotte_related`

`safe_label()` also normalizes GPT output:

- invalid `primary_label` becomes `ETC`
- invalid or duplicate secondary labels are removed
- secondary labels are saved as a semicolon-delimited string

## Training Data Loading

`load_data()` in [train_classifier.py](/C:/Users/yunha/Desktop/lotte-insight/training/train_classifier.py) performs the actual training-time filtering and normalization.

### 1. Read and Filter Source CSVs

For each CSV:

- skip it if the file does not exist
- load with `utf-8-sig`
- keep only rows where `is_lotte_related == "true"` ignoring case

After that, both dataframes are concatenated.

### 2. Deduplicate and Clean Text

The merged dataframe is then:

- deduplicated by `title`
- normalized so `title` is a trimmed string
- normalized so `description_snippet` is a trimmed string truncated to `ARTICLE_SNIPPET_LENGTH`

### 3. Build Multi-Label Targets

`normalize_label_set(primary_label, secondary_labels)` creates the label set for each row:

1. Add `primary_label` if valid.
2. Parse `secondary_labels` by splitting on `;`.
3. Keep only labels present in `VALID_LABEL_SET`.
4. Remove duplicates.
5. If any non-`ETC` label exists, drop `ETC`.
6. If only `ETC` remains, keep `["ETC"]`.
7. If nothing valid remains, drop the row from training.

The remaining label sets are converted to multi-hot vectors by `encode_multihot()`.

### 4. Returned Objects

`load_data()` returns:

- `titles: list[str]`
- `descriptions: list[str]`
- `multilabels: list[list[float]]`
- `primary_labels: list[str]`

`primary_labels` is used only for train/validation stratification. If the stored primary label is invalid but the normalized label set is not empty, the first valid label from the normalized set is used instead.

## Input Representation

The model backbone is:

- pretrained model: `monologg/koelectra-small-v3-discriminator`
- tokenizer: `AutoTokenizer`
- classifier head: `AutoModelForSequenceClassification`

The model receives a pair of text segments:

- segment A: `title`
- segment B: `description_snippet`

Tokenization in `ArticleDataset` is:

```python
tokenizer(
    titles,
    descriptions,
    truncation="only_second",
    padding="max_length",
    max_length=128,
    return_tensors="pt",
)
```

Implications:

- maximum sequence length is `128`
- only the description segment is truncated
- padding is always to length `128`

Each dataset item contains:

```python
{
  "input_ids": Tensor[128],
  "attention_mask": Tensor[128],
  "token_type_ids": Tensor[128],  # if emitted by the tokenizer
  "labels": Tensor[8],
}
```

## Multi-Label Encoding

Each article is encoded as an 8-dimensional multi-hot vector aligned to `VALID_LABELS`.

Examples:

```text
["MATCH_RELATED", "INTERVIEW"] -> [0, 0, 1, 0, 1, 0, 0, 0]
["ETC"]                        -> [0, 0, 0, 0, 0, 0, 0, 1]
```

## Train / Validation Split

`train()` uses `train_test_split()` with:

- validation ratio: `DEFAULT_VALIDATION_SPLIT` = `0.15`
- random seed: runtime `seed` argument, default `42`
- stratification target: `primary_labels`

This means the split is stratified by one representative label per row, not by the full multi-label combination.

## Loss and Class Imbalance

The classifier is created with:

```python
AutoModelForSequenceClassification.from_pretrained(
    PRETRAINED,
    num_labels=len(VALID_LABELS),
    problem_type="multi_label_classification",
)
```

Training uses explicit binary cross-entropy on logits:

```python
loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weights)
```

`compute_pos_weights()` calculates, for each label:

```text
pos_weight_i = negative_count_i / positive_count_i
```

Then clips every weight into `[0.5, 5.0]`.

Important detail:

- `pos_weights` are computed from the full merged labeled dataset returned by `load_data()`, not only from the training split.

## Training Loop

The main loop in [train_classifier.py](/C:/Users/yunha/Desktop/lotte-insight/training/train_classifier.py) is:

1. Set `torch.manual_seed(seed)`.
2. Select `cuda` if available, otherwise `cpu`.
3. Load and normalize data with `load_data()`.
4. Split into train and validation subsets.
5. Build tokenizer and KoELECTRA classifier.
6. Build `ArticleDataset` and `DataLoader`.
7. Compute `pos_weights`.
8. Create `AdamW` optimizer with `weight_decay=0.01`.
9. Create linear warmup/decay scheduler.
10. For each epoch:
11. Run training forward/backward passes.
12. Clip gradients with `max_norm=1.0`.
13. Step optimizer and scheduler.
14. Evaluate on the validation split.
15. Compute validation macro-F1 and micro-F1.
16. Save the checkpoint if validation macro-F1 improved.

Default settings from [settings.py](/C:/Users/yunha/Desktop/lotte-insight/training/settings.py):

| Parameter | Value |
| --- | --- |
| epochs | `5` |
| learning rate | `5e-5` |
| train batch size | `16` |
| evaluation-only batch size | `32` |
| warmup ratio | `0.1` |
| random seed | `42` |
| validation split | `0.15` |
| target minimum macro-F1 | `0.70` |

Note:

- inside `train()`, both the train loader and validation loader use the `batch_size` argument passed to training
- `DEFAULT_EVAL_BATCH_SIZE=32` is used only by `evaluate()`

## Prediction Rule for Multi-Label Output

The model output for each batch is:

```python
logits = model(**batch).logits
```

Shape:

```text
[batch_size, 8]
```

`predict_from_logits()` converts logits to predictions as follows:

1. Apply `torch.sigmoid(logits)`.
2. Mark labels with probability `>= 0.5` as positive.
3. If a row has no positive label, force the top-scoring label on.
4. If `ETC` and any non-`ETC` label are both positive, remove `ETC`.
5. If step 4 makes the row empty, restore the best non-`ETC` label.

This is the current canonical post-processing logic for the multi-label training pipeline.

## Evaluation

`evaluate()`:

1. Reloads the saved tokenizer, model, and `label_encoder.json`
2. Rebuilds the full dataset from the current CSV files
3. Runs batched inference with `predict_from_logits()`
4. Prints:
   - macro F1
   - micro F1
   - samples F1
   - per-label `classification_report`

Evaluation is full-data evaluation against the current labeled CSVs. It does not recreate the train/validation split used during training.

## Saved Artifacts

The best checkpoint is written to:

- `training/models/classifier_koelectra`

Artifacts:

- Hugging Face model files
- tokenizer files
- `label_encoder.json`

Example `label_encoder.json`:

```json
[
  "INJURY_ROSTER",
  "TRANSACTION_CONTRACT",
  "MATCH_RELATED",
  "PERFORMANCE_ANALYSIS",
  "INTERVIEW",
  "PLAYER_RELATED",
  "CLUB_OPERATION",
  "ETC"
]
```

## CLI Usage

Train and then run full-data evaluation:

```bash
python training/train_classifier.py
```

Train with custom epochs / learning rate / batch size:

```bash
python training/train_classifier.py --epochs 10 --lr 5e-5 --batch 16
```

Run evaluation only:

```bash
python training/train_classifier.py --eval-only
```

## Current Limitations

- The model sees only `title` and `description_snippet`, not full article body text.
- Prediction threshold is a single global value `0.5`; there is no per-label threshold tuning.
- `confidence_score` and `confidence_note` are stored in the CSVs but are not used during training.
- Deduplication is done only by `title`, so semantically duplicated articles with slightly different titles may remain.
- `torch.manual_seed(seed)` is set, but the script does not enforce full deterministic behavior across all CUDA paths.

## Serving Mismatch to Be Aware Of

The training pipeline is now multi-label, but [backend/models/classifier.py](/C:/Users/yunha/Desktop/lotte-insight/backend/models/classifier.py) is not yet fully aligned with it.

Current backend inference still:

- applies `softmax` instead of `sigmoid`
- selects one top label as the primary output
- derives secondary labels from low softmax cutoffs instead of using the same multi-label threshold logic as training

So this document describes the training/evaluation pipeline accurately, but the online classifier path should be updated separately if production inference must match training-time multi-label behavior exactly.

## Summary

The current supervised training flow is:

- source: labeled CSV rows filtered by `is_lotte_related == true`
- input text: `title + description_snippet`
- target: normalized `primary_label + secondary_labels`
- encoding: 8-dim multi-hot vectors
- objective: `BCEWithLogitsLoss` with per-label positive weights
- prediction rule: `sigmoid` thresholding plus empty-row / `ETC` cleanup
- checkpoint criterion: best validation macro-F1
