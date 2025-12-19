#!/usr/bin/env python3
"""
CLAP local runner for VS Code.

- Mode A: pipeline zero-shot classification (needs candidate labels)
- Mode B: embeddings + similarity (recommended for creative projects)

NEW:
- --labelbank_json supports AudioSet-music JSON labelbank with prompt ensembles:
  each label has many prompts -> prompt embeddings averaged -> label embedding

CLAP is typically used with ~10s chunks; we chunk long audio.
"""

import argparse
import json
import math
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

import numpy as np
import torch
import torch.nn.functional as F
import librosa

from transformers import pipeline, ClapModel, ClapProcessor


DEFAULT_LABELS = [
    "a string quartet performance",
    "a solo piano performance",
    "a solo vocal performance",
    "a calm, delicate performance",
    "a tense, energetic performance",
    "applause from an audience",
]


def load_audio_mono(path: str, target_sr: int = 48000) -> Tuple[np.ndarray, int]:
    """Load audio as mono float32 at target_sr."""
    y, _sr = librosa.load(path, sr=target_sr, mono=True)
    y = y.astype(np.float32)
    return y, target_sr


def chunk_audio(
    y: np.ndarray,
    sr: int,
    chunk_s: float = 10.0,
    hop_s: Optional[float] = None,
) -> List[Tuple[int, int, np.ndarray]]:
    """Return list of (start_sample, end_sample, chunk_array)."""
    if hop_s is None:
        hop_s = chunk_s

    chunk_n = int(round(chunk_s * sr))
    hop_n = int(round(hop_s * sr))
    if chunk_n <= 0 or hop_n <= 0:
        raise ValueError("chunk_s and hop_s must be > 0")

    chunks = []
    n = len(y)
    if n == 0:
        return chunks

    n_chunks = max(1, 1 + math.floor((n - chunk_n) / hop_n)) if n >= chunk_n else 1

    for i in range(n_chunks):
        start = i * hop_n
        end = start + chunk_n
        if start >= n:
            break
        chunk = y[start:end]
        if len(chunk) < chunk_n:
            pad = np.zeros(chunk_n, dtype=np.float32)
            pad[: len(chunk)] = chunk
            chunk = pad
        chunks.append((start, min(end, n), chunk))

    return chunks


def seconds_str(start_s: float, end_s: float) -> str:
    return f"{start_s:0.2f}s–{end_s:0.2f}s"


def run_pipeline(audio_path: str, labels: List[str], top_k: int, device: int):
    """Quick test mode: requires candidate_labels."""
    clf = pipeline(
        task="zero-shot-audio-classification",
        model="laion/clap-htsat-fused",
        device=device,
    )

    out = clf(
        audio_path,
        candidate_labels=labels,
        hypothesis_template="This audio is {}."
    )
    return out[:top_k]


def load_labelbank_json(path: str) -> List[Dict[str, Any]]:
    """
    Expected structure (per item):
      { "label": "Violin", "synonyms": [...], "prompts": ["a violin solo", ...] }
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("labelbank_json must be a non-empty JSON list.")
    for item in data[:3]:
        if "label" not in item or "prompts" not in item:
            raise ValueError("labelbank_json items must have 'label' and 'prompts'.")
    return data


def compute_label_embeddings_from_labelbank(
    processor: ClapProcessor,
    model: ClapModel,
    labelbank: List[Dict[str, Any]],
    device: torch.device,
    batch_size: int = 64,
) -> Tuple[List[str], torch.Tensor]:
    """
    Build a label embedding matrix using prompt ensembling:
      - embed ALL prompts
      - normalize prompt embeddings
      - average per label
      - normalize label embeddings

    Returns:
      labels: list[str] length N
      label_mat: torch.Tensor shape (N, D) on CPU
    """
    labels = [item["label"] for item in labelbank]
    prompts: List[str] = []
    prompt_label_idx: List[int] = []

    for i, item in enumerate(labelbank):
        ps = item.get("prompts", [])
        if not ps:
            continue
        for p in ps:
            prompts.append(str(p))
            prompt_label_idx.append(i)

    if not prompts:
        raise ValueError("No prompts found in labelbank_json.")

    # Embed prompts in batches
    all_prompt_embs = []
    model.eval()

    for start in range(0, len(prompts), batch_size):
        batch_prompts = prompts[start:start + batch_size]
        text_inputs = processor(
            text=batch_prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
        )
        text_inputs = {k: v.to(device) for k, v in text_inputs.items()}

        with torch.no_grad():
            emb = model.get_text_features(**text_inputs)
            emb = F.normalize(emb, dim=-1)
        all_prompt_embs.append(emb.detach().cpu())

    prompt_embs = torch.cat(all_prompt_embs, dim=0)  # (P, D)
    idx = torch.tensor(prompt_label_idx, dtype=torch.long)  # (P,)

    # Aggregate prompt embeddings -> label embeddings
    n_labels = len(labels)
    d = prompt_embs.shape[-1]
    label_sum = torch.zeros((n_labels, d), dtype=torch.float32)
    counts = torch.zeros((n_labels,), dtype=torch.float32)

    label_sum.index_add_(0, idx, prompt_embs)
    counts.index_add_(0, idx, torch.ones_like(idx, dtype=torch.float32))

    counts = torch.clamp(counts, min=1.0).unsqueeze(1)
    label_mat = label_sum / counts
    label_mat = F.normalize(label_mat, dim=-1)  # (N, D)

    return labels, label_mat


def run_embeddings(
    audio_path: str,
    labels: Optional[List[str]],
    labelbank_json: Optional[str],
    chunk_s: float,
    hop_s: Optional[float],
    top_k: int,
    batch_size: int,
):
    """
    Recommended mode:
    - chunk audio
    - extract audio embeddings per chunk
    - extract text embeddings once (labels or labelbank prompt-ensembled labels)
    - cosine similarity
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    processor = ClapProcessor.from_pretrained("laion/clap-htsat-fused")
    model = ClapModel.from_pretrained("laion/clap-htsat-fused").to(device)
    model.eval()

    # Build label matrix
    if labelbank_json:
        labelbank = load_labelbank_json(labelbank_json)
        label_names, label_mat = compute_label_embeddings_from_labelbank(
            processor=processor,
            model=model,
            labelbank=labelbank,
            device=device,
            batch_size=batch_size,
        )
    else:
        if not labels:
            raise ValueError("Provide --labels/--labels_file or --labelbank_json for embeddings mode.")
        label_names = labels

        text_inputs = processor(
            text=label_names,
            return_tensors="pt",
            padding=True,
            truncation=True,
        )
        text_inputs = {k: v.to(device) for k, v in text_inputs.items()}
        with torch.no_grad():
            text_emb = model.get_text_features(**text_inputs)
            text_emb = F.normalize(text_emb, dim=-1)
        label_mat = text_emb.detach().cpu()

    # Audio
    y, sr = load_audio_mono(audio_path, target_sr=48000)
    chunks = chunk_audio(y, sr=sr, chunk_s=chunk_s, hop_s=hop_s)

    results = []
    for (start, end, chunk) in chunks:
        start_s = start / sr
        end_s = end / sr

        audio_inputs = processor(audios=chunk, sampling_rate=sr, return_tensors="pt")
        audio_inputs = {k: v.to(device) for k, v in audio_inputs.items()}

        with torch.no_grad():
            audio_emb = model.get_audio_features(**audio_inputs)
            audio_emb = F.normalize(audio_emb, dim=-1).detach().cpu()  # (1, D)

        sims = (audio_emb @ label_mat.T).squeeze(0).numpy().tolist()

        ranked = sorted(
            [{"label": lab, "score": float(sc)} for lab, sc in zip(label_names, sims)],
            key=lambda x: x["score"],
            reverse=True,
        )[:top_k]

        results.append({
            "time": seconds_str(start_s, end_s),
            "top": ranked,
        })

    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--audio", required=True, help="Path to an audio file (wav/flac/mp3/m4a...)")
    p.add_argument("--mode", choices=["pipeline", "embeddings"], default="pipeline",
                   help="pipeline = quick zero-shot; embeddings = chunked features + similarity")

    p.add_argument("--labels", nargs="*", default=None,
                   help="Candidate labels (phrases). If omitted, uses a small default set.")
    p.add_argument("--labels_file", default=None,
                   help="Text file with one label per line (overrides --labels).")

    # NEW: labelbank with prompt ensembles
    p.add_argument("--labelbank_json", default=None,
                   help="JSON labelbank with prompts per label (recommended).")

    p.add_argument("--top_k", type=int, default=5, help="How many top labels to show")
    p.add_argument("--chunk_s", type=float, default=10.0, help="Chunk size in seconds (embeddings mode)")
    p.add_argument("--hop_s", type=float, default=None, help="Hop size in seconds (embeddings mode). Default = chunk_s")
    p.add_argument("--batch_size", type=int, default=64, help="Text embedding batch size (labelbank mode)")
    p.add_argument("--out", default=None, help="Optional output JSON path")

    args = p.parse_args()

    audio_path = str(Path(args.audio).expanduser())
    if not Path(audio_path).exists():
        raise FileNotFoundError(audio_path)

    # Load plain labels (txt/args/default)
    labels = None
    if args.labels_file:
        lf = Path(args.labels_file).expanduser()
        labels = [line.strip() for line in lf.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        labels = args.labels if args.labels else DEFAULT_LABELS

    if args.mode == "pipeline":
        # pipeline ignores labelbank_json by design; it expects a flat candidate label list
        device = 0 if torch.cuda.is_available() else -1
        output = run_pipeline(audio_path, labels=labels, top_k=args.top_k, device=device)
    else:
        output = run_embeddings(
            audio_path=audio_path,
            labels=labels,
            labelbank_json=args.labelbank_json,
            chunk_s=args.chunk_s,
            hop_s=args.hop_s,
            top_k=args.top_k,
            batch_size=args.batch_size,
        )

    print(json.dumps(output, indent=2, ensure_ascii=False))

    if args.out:
        out_path = Path(args.out).expanduser()
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
