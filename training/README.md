# v1.1 synthetic training data

`synthetic-v1.1.json` contains 1,200 original bilingual examples generated with
DeepSeek for this project on 2026-10-06. Prompts requested generic spoken English
and faithful Simplified Chinese, including negation, uncertainty, numbers, units,
idioms, incomplete clauses and everyday meeting topics. Prompts did not contain
TED transcripts or quotations. This is AI-generated training material, not a
human-verified reference corpus. No personal credentials or meeting records are included.

The SHA-256 is `e27ab26e05472661f348b0694270c04ad235696bd65d30b60a1bc9665ac9cec5`.
After token-length and unknown-target-token filtering, all 1,200 examples remain.
A deterministic shuffle with seed 20261006 assigns 80 examples to synthetic
validation and 1,120 to training. Validation and train have no exact normalized
English overlap, and no pair exceeds 90% character similarity across the split.
Development TED references were checked for exact normalized English overlap of
at least eight words; none was found. This check does not prove semantic independence.

The base is `Helsinki-NLP/opus-mt-en-zh`, pinned to
`408d9bc410a388e1d9aef112a2daba955b945255`. See its
[model card](https://huggingface.co/Helsinki-NLP/opus-mt-en-zh) and Apache 2.0 notice.
Training used Python 3.12.13, PyTorch 2.10.0+cu128, Transformers 4.57.6,
SentencePiece 0.2.2, CTranslate2 4.8.2, and an RTX 4080. These training dependencies
are optional and are absent from the Windows runtime package.

With the pinned base downloaded locally, reproduce the experiment using
`python scripts/train_offline_mt.py --base BASE_DIRECTORY --output OUTPUT_DIRECTORY`.
Use full-parameter AdamW, learning rate 2e-5, weight decay 0.01, batch size 16,
gradient norm clipping 1.0, bfloat16 autocast and three epochs. Epoch 2 was selected
using development TED comparisons; the two holdout talks were excluded from
selection. Floating-point training may vary across hardware and runtime versions.

Convert the selected checkpoint with
`ct2-transformers-converter --model OUTPUT_DIRECTORY/marian-epoch2 --output_dir CONVERTED_DIRECTORY --quantization int8 --copy_files source.spm target.spm vocab.json tokenizer_config.json`.
The bundled runtime uses CPU int8, beam 2, a beam 4 retry for unreadable output,
the `>>cmn_Hans<<` source prefix, source `</s>`, and separate source/target tokenizers.
The accepted model and training summaries are recorded in `docs/mt-training-v1.1.json`.
Weights are delivered in the Release ZIP, not committed to Git.
