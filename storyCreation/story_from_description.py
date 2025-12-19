#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import random
from typing import Any, Dict, List, Tuple, Optional

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig


MOOD_LABELS = ["ENERGETIC", "SOLO", "CALM", "DEEP", "DISSONANT", "ANXIOUS"]


# ---------- small utilities ----------

def mistral_inst(user_text: str) -> str:
    return f"<s>[INST] {user_text.strip()} [/INST]"


def truncate_to_words(text: str, n_words: int) -> str:
    text = text.strip()
    if n_words is None or n_words <= 0:
        return text
    words = text.split()
    if len(words) <= n_words:
        return text
    return " ".join(words[:n_words]).strip()


def estimate_max_new_tokens(target_words: int) -> int:
    # Rough but effective: tokens ~= words * (1.2..1.6). Keep tight for speed.
    if not target_words or target_words <= 0:
        return 180
    return max(48, int(target_words * 1.45))


def parse_block(raw: str) -> Tuple[str, str, str]:
    """
    Expected:
      MOOD: ...
      TEXT:
      ...
      FACTS:
      ...
    Returns: (mood, text, facts)
    """
    raw = raw.strip()
    mood = "CALM"
    text = raw
    facts = ""

    # mood
    for line in raw.splitlines()[:10]:
        if line.strip().upper().startswith("MOOD:"):
            cand = line.split(":", 1)[1].strip().upper()
            if cand in MOOD_LABELS:
                mood = cand
            break

    u = raw.upper()
    t_pos = u.find("TEXT:")
    f_pos = u.find("FACTS:")

    if t_pos != -1:
        if f_pos != -1 and f_pos > t_pos:
            text = raw[t_pos + 5:f_pos].strip()
            facts = raw[f_pos + 6:].strip()
        else:
            text = raw[t_pos + 5:].strip()

    return mood, text, facts



# ---------- model loading / generation ----------

def load_model(model_id: str, use_4bit: bool = True):
    tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quant_cfg = None
    if use_4bit:
        quant_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )

    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            torch_dtype=torch.float16,
            quantization_config=quant_cfg,
        )
    except Exception as e:
        print("⚠️  4-bit load failed. Falling back to non-quantized load.")
        print(f"Details: {e}")
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        )

    model.eval()

    # Small speed knobs (safe defaults)
    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True

    return model, tokenizer


@torch.inference_mode()
def generate_once(
    model,
    tokenizer,
    prompt: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
) -> str:
    inputs = tokenizer(prompt, return_tensors="pt")
    # Works well on single-GPU setups (your case).
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    out_ids = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=temperature,
        top_p=top_p,
        use_cache=True,
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )

    # Only decode the newly generated tokens
    gen_ids = out_ids[0][inputs["input_ids"].shape[-1]:]
    return tokenizer.decode(gen_ids, skip_special_tokens=True).strip()


# ---------- prompt builder (short, fast) ----------

def build_prompt_first(music_prompt: str, words: int) -> str:
    return mistral_inst(
        f"""
Write scene 1 of ONE coherent tale.
In ONE short sentence, establish the setting (place + year) and keep it consistent.
Never mention instruments/audio terms. Use MUSIC FEELING only for emotion/pacing/tension.

Pick exactly one MOOD label from: {", ".join(MOOD_LABELS)}.

Output EXACTLY:
MOOD: <LABEL>
TEXT:
~{words} words, 1–2 short paragraphs.
FACTS:
PROTAGONIST: ...
SIDE CHARACTER: ...
GOAL: ...
CENTRAL CONFLICT: ...
MYSTERY (known / missing): ...
SETTING (place + year): ...

MUSIC FEELING:
{music_prompt}
"""
    )


def build_prompt_next(prev_text: str, facts: str, music_prompt: str, words: int, is_last: bool) -> str:
    end_rule = (
        "This is the FINAL scene: resolve the central conflict and reveal/close the mystery with clear closure."
        if is_last
        else
        "End with a small hook into the next scene."
    )

    return mistral_inst(
        f"""
Continue the SAME tale. Facts and previous scene are binding.
Never mention instruments/audio terms. Use MUSIC FEELING only for emotion/pacing/tension.

FACTS (binding, keep consistent):
{facts}

PREVIOUS SCENE (binding):
{prev_text}

{end_rule}

Pick exactly one MOOD label from: {", ".join(MOOD_LABELS)}.

Output EXACTLY:
MOOD: <LABEL>
TEXT:
~{words} words, 1–2 short paragraphs.

MUSIC FEELING:
{music_prompt}
"""
    )


# ---------- main ----------
   

def load_segments(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # FORMAT A (your CLAP output): a list of chunks
    # [
    #   {"time": "...", "top": [{"label": "...", "score": 0.33}, ...]},
    #   ...
    # ]
    if isinstance(data, list):
        segments: List[Dict[str, Any]] = []
        for i, item in enumerate(data):
            top = item.get("top", [])

            # find the best available label
            label = None
            if isinstance(top, list) and len(top) > 0:
                # choose highest score if scores exist, otherwise first label
                def score_of(x):
                    try:
                        return float(x.get("score", -1e9))
                    except Exception:
                        return -1e9

                best = max(
                    (x for x in top if isinstance(x, dict) and "label" in x),
                    key=score_of,
                    default=None
                )
                if best is not None:
                    label = str(best["label"]).strip()

            if not label:
                raise ValueError(f"Chunk #{i} has no usable top[].label in {path}")

            segments.append({"id": i + 1, "music_prompt": label})

        if not segments:
            raise ValueError(f"No segments parsed from list JSON in {path}")
        return segments

    # FORMAT B (old): {"segments":[{"id":..,"music_prompt":..}, ...]}
    if isinstance(data, dict) and "segments" in data:
        segments = data.get("segments", [])
        if not segments:
            raise ValueError("segments is empty")
        for i, seg in enumerate(segments):
            if "music_prompt" not in seg:
                raise ValueError(f"Segment #{i} missing 'music_prompt' field.")
        return segments

    raise ValueError("Unsupported JSON format. Expected list (CLAP output) or dict with 'segments'.")



def main():
    p = argparse.ArgumentParser(description="Fast fragmented story generator from text music prompts (English).")
    p.add_argument("--segments", required=True, help="Path to JSON with segments[].music_prompt")
    p.add_argument("--out_json", default="story.json", help="Output JSON path")
    p.add_argument("--out_txt", default="full_story.txt", help="Output full story text path")
    p.add_argument("--model", default="mistralai/Mistral-7B-Instruct-v0.2", help="HF model id")
    p.add_argument("--no_4bit", action="store_true", help="Disable 4-bit quantization")
    p.add_argument("--words", type=int, default=90, help="Target words per fragment (no mid-word cuts)")
    p.add_argument("--temperature", type=float, default=0.65)
    p.add_argument("--top_p", type=float, default=0.9)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--print_live", action="store_true", help="Print each fragment as soon as generated")
    args = p.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        torch.manual_seed(args.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(args.seed)

    segments = load_segments(args.segments)

    print(f"Loading model: {args.model}")
    model, tokenizer = load_model(args.model, use_4bit=(not args.no_4bit))

    max_new_tokens = estimate_max_new_tokens(args.words)
    prev_text = ""
    facts = ""
    n_segments = len(segments)
    fragments: List[Dict[str, Any]] = []
    story_parts: List[str] = []

    for idx, seg in enumerate(segments):
        seg_id = seg.get("id", idx + 1)
        music_prompt = seg["music_prompt"].strip()

        is_last = (idx == n_segments - 1)
        prompt = build_prompt_first(music_prompt, args.words) if idx == 0 else build_prompt_next(prev_text, facts, music_prompt, args.words, is_last)

        raw = generate_once(
            model=model,
            tokenizer=tokenizer,
            prompt=prompt,
            max_new_tokens=max_new_tokens,
            temperature=args.temperature,
            top_p=args.top_p,
        )

        mood, text, new_facts = parse_block(raw)
        prev_text = text
        if idx == 0 and new_facts.strip():
            facts = new_facts
        text = truncate_to_words(text, args.words)

        if args.print_live:
            print(f"\n=== FRAGMENT {seg_id} | MOOD={mood} ===\n{text}\n", flush=True)

        fragments.append({"id": seg_id, "mood": mood, "text": text})
        story_parts.append(text)

    full_story = "\n\n".join(story_parts).strip()

    out = {"fragments": fragments, "full_story": full_story}

    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    with open(args.out_txt, "w", encoding="utf-8") as f:
        f.write(full_story)

    print(f"Saved JSON: {args.out_json}")
    print(f"Saved full story: {args.out_txt}")


if __name__ == "__main__":
    main()
