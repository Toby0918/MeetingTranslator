"""Reproduce the v1.1 synthetic-data experiment; never reads TED evaluation files."""
import argparse
import hashlib
import json
import random
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True, help='Local pinned HF Marian model directory')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--data', type=Path, default=Path(__file__).resolve().parents[1] / 'training/synthetic-v1.1.json')
    args = parser.parse_args()
    import torch
    from torch.utils.data import DataLoader
    from transformers import MarianMTModel, MarianTokenizer

    if not torch.cuda.is_available():
        raise SystemExit('This training recipe requires CUDA. The release application runs on CPU.')
    digest = hashlib.sha256(args.data.read_bytes()).hexdigest()
    if digest != 'e27ab26e05472661f348b0694270c04ad235696bd65d30b60a1bc9665ac9cec5':
        raise SystemExit('Training data differs from the pinned v1.1 experiment.')
    random.seed(20261006)
    torch.manual_seed(20261006)
    torch.set_num_threads(4)
    tokenizer = MarianTokenizer.from_pretrained(args.base, local_files_only=True)
    model = MarianMTModel.from_pretrained(args.base, local_files_only=True).to('cuda')
    pairs = json.loads(args.data.read_text(encoding='utf-8'))
    samples = []
    for pair in pairs:
        encoding = tokenizer('>>cmn_Hans<< ' + pair['en'], text_target=pair['zh'])
        if (len(encoding['input_ids']) <= 160 and len(encoding['labels']) <= 160
                and tokenizer.unk_token_id not in encoding['labels']):
            samples.append(encoding)
    random.shuffle(samples)
    validation, train = samples[:80], samples[80:]

    def collate(rows):
        batch = tokenizer.pad([{k: v for k, v in row.items() if k != 'labels'}
                               for row in rows], return_tensors='pt')
        size = max(len(row['labels']) for row in rows)
        batch['labels'] = torch.tensor([row['labels'] + [-100] * (size - len(row['labels'])) for row in rows])
        return {k: v.to('cuda') for k, v in batch.items()}

    loader = DataLoader(train, batch_size=16, shuffle=True, collate_fn=collate, num_workers=0)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
    records = []
    started = time.perf_counter()
    for epoch in range(1, 4):
        model.train()
        losses = []
        for batch in loader:
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda', dtype=torch.bfloat16):
                loss = model(**batch).loss
            if not torch.isfinite(loss):
                raise RuntimeError('Non-finite loss')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(loss.item())
        model.eval()
        validation_losses = []
        with torch.inference_mode():
            for start in range(0, len(validation), 16):
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    loss = model(**collate(validation[start:start + 16])).loss
                validation_losses.append(loss.item())
        checkpoint = args.output / f'marian-epoch{epoch}'
        model.save_pretrained(checkpoint, safe_serialization=True)
        tokenizer.save_pretrained(checkpoint)
        record = {'epoch': epoch, 'train_loss': sum(losses) / len(losses),
                  'validation_loss': sum(validation_losses) / len(validation_losses),
                  'elapsed_seconds': time.perf_counter() - started}
        records.append(record)
        print(json.dumps(record), flush=True)
    (args.output / 'training-run.json').write_text(json.dumps({
        'dataset_sha256': digest, 'seed': 20261006, 'training_examples': len(train),
        'validation_examples': len(validation), 'filtered': len(pairs) - len(samples),
        'torch_version': torch.__version__, 'gpu': torch.cuda.get_device_name(),
        'epochs': records}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
