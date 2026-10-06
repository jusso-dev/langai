# ML methodology and honest evaluation

## What dictionary training measures

The primary task aligns a word's encoder representation with its English definitions. It can support retrieval, lexical matching, semantic search, clustering and future RAG. It does not validate grammaticality, conversation, natural translation, discourse or speech. Multilingual foundation models may have limited or no coverage of the uploaded language; script tokenization and baseline results need inspection.

The default is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, configurable through deployment settings and the run request. Auto resolves the repository revision to a full commit before the run is created. Engineers can supply a pinned commit directly. Remote custom model code is disabled. The deployment owner must review the base model's licence and suitability before enabling another repository.

## Splitting before generation

The seed acts on sorted connected groups. NFC/casefold headwords, transitive spelling variants and identical normalized definitions are grouped together. Original case is preserved in the dataset; casefold is used only for conservative leakage grouping. A group cannot cross train, validation or test. This is intentionally stricter than a random original-row split.

Groups target 80/10/10. At least one group is reserved for validation and one for test. Small datasets therefore differ from the target ratios; actual counts are shown. Fewer than three independent groups are rejected. Contrastive training additionally requires at least two unrelated training groups. Three held-out words are a software smoke test, not an adequate linguistic evaluation.

Frozen views:

- Lexical word → definition pairs, one sample per actual definition.
- Reverse definition → word pairs.
- Labelled semantic positive/negative pairs.
- Dictionary words as positive language-identification samples; external negatives only from an explicitly selected approved corpus.
- Explicit spelling variant pairs.
- Two instruction examples per word-definition pair for experimental adapters, preserving source IDs.

Every dictionary-derived sample retains all contributing entry IDs. Negative pairs retain both source IDs and both must have the same split. External negative samples have a separate corpus/sample identity rather than an invented dictionary ID. They are deduplicated, checked against dictionary words/variants, split once and retained in the snapshot.

Negative mining uses within-split definition-term overlap to find harder candidates, falling back deterministically when necessary. It excludes the same connected group and shared known definitions. These are **assumed negatives**, not linguistically verified unrelated concepts. Incomplete dictionaries can still produce false negatives. Review sample exports and use future community-curated semantic relations to improve them.

## Contrastive encoder training

The original encoder is evaluated first on held-out test queries against every definition in the frozen dictionary. Fine-tuning uses only training semantic pairs. The labelled cosine contrastive objective attracts positive pairs and penalizes negative cosine scores above a configurable margin. Using explicit negatives avoids treating known alternate definitions in a batch as automatic in-batch negatives.

AdamW, gradient clipping, deterministic batch ordering and an explicit seed are used. Validation MRR selects the best checkpoint; patience stops unsuccessful epochs. Test results never select checkpoints. Evaluation frequency, margin, sequence length, device, batch size, epochs, learning rate, weight decay and patience are overridable. Environment and code hashes are recorded; exact bitwise reproducibility across hardware/library versions is not guaranteed.

Recall@1/5/10 and MRR use held-out original headwords. All exact normalized correct meanings are relevant, including shared senses. Candidate definitions include training entries because deployed retrieval searches the full dictionary. This is an explicit lexical retrieval evaluation protocol, not evidence of unseen-sentence translation. Similarity distributions include positive and deterministically bounded negative scores (count, mean, standard deviation, quantiles). Delta can be negative; deployment never depends on pretending an improvement occurred.

## Classifier baselines

Character 1–5-gram TF-IDF features feed logistic regression and linear SVM. Only the training partition fits vocabulary/IDF and estimator weights. A sigmoid calibrator uses validation scores. Accuracy, macro F1, ROC AUC and log loss use test rows. Logistic regression is a fixed deployment default; test performance does not select the model. Small validation sets yield unstable calibration. The returned confidence means configured-language versus the selected negative corpus, not universal identification or community membership.

Artifacts contain JSON vocabulary, IDF, coefficients and calibration weights. Inference never unpickles an uploaded artifact. FastText can be added behind Classifier/Trainer later; it is not silently substituted.

## Experimental dictionary adapter

Disabled by default (`LANGAI_ENABLE_EXPERIMENTAL=false`). The local Transformers + PEFT path uses an openly available configurable causal model, two provenance-linked prompts per lexical pair, prompt/padding-masked response loss and LoRA adapters. It selects checkpoints using validation loss and evaluates held-out response loss/perplexity against the base model. The adapter and exact base files are bundled locally. It is marked EXPERIMENTAL throughout and remains a downloadable research artifact, not a conversation API.

## References

- [Sentence Transformers training overview](https://sbert.net/docs/sentence_transformer/training_overview.html)
- [Sentence Transformers loss reference](https://www.sbert.net/docs/package_reference/sentence_transformer/losses.html)
- [Default multilingual model card](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
- [PEFT documentation](https://huggingface.co/docs/peft/index)
