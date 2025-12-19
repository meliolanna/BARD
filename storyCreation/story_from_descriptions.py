#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from dataclasses import dataclass
from typing import Dict, List, Any

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, pipeline


def mistral_inst(user_text: str) -> str:
    return f"<s>[INST] {user_text.strip()} [/INST]"


def load_textgen(model_id: str, use_4bit: bool = True):
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
        print("4-bit non disponibile / errore bitsandbytes. Fallback senza quantizzazione.")
        print(f"Dettaglio: {e}")
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        )

    gen = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        return_full_text=False,
    )
    return gen


def llm_generate(gen, prompt: str, max_new_tokens: int, temperature: float, top_p: float) -> str:
    out = gen(
        prompt,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=temperature,
        top_p=top_p,
    )
    return out[0]["generated_text"].strip()


def build_outline(gen, setting: str, segments: List[Dict[str, Any]], temperature: float, top_p: float) -> str:
    n = len(segments)
    joined = "\n".join([f"- Segmento {s['id']}: {s['music_description']}" for s in segments])
    user = f"""
Sei un autore di romanzi. Ambientazione: {setting}.
Ho {n} segmenti musicali della STESSA traccia, ciascuno con una descrizione emotiva/dinamica.
Voglio UNA storia coerente complessivamente, con un arco narrativo chiaro, divisa in {n} scene (una per segmento).

Regole:
- Non descrivere strumenti o suoni (niente “sintetizzatori”, “cassa dritta”, ecc.).
- Traduci solo in emozioni, ritmo dell’azione, tensione, scelte dei personaggi.
- Mantieni 1 protagonista principale + 1 comprimario ricorrente.
- Inserisci 1 conflitto centrale e 1 mistero che si chiude alla fine.

Descrizioni segmenti:
{joined}

Ora scrivi un OUTLINE in {n} bullet point, uno per segmento:
- per ogni punto: obiettivo della scena, svolta narrativa, emozione dominante.
Stai conciso.
"""
    return llm_generate(gen, mistral_inst(user), max_new_tokens=350, temperature=temperature, top_p=top_p)


def update_story_state(gen, prev_state: str, last_scene: str, temperature: float, top_p: float) -> str:
    user = f"""
Aggiorna lo "STORY STATE" per mantenere coerenza tra scene.
Devi produrre SOLO uno state compatto, massimo 12 righe.

Formato obbligatorio:
PROTAGONISTA:
COMPRIMARIO:
OBIETTIVO:
CONFLITTO CENTRALE:
MISTERO (cosa sappiamo / cosa manca):
POSTO & TEMPO:
THREAD APERTI (max 4):
TONO ATTUALE (1 riga):

STATE PRECEDENTE:
{prev_state}

ULTIMA SCENA SCRITTA:
{last_scene}
"""
    return llm_generate(gen, mistral_inst(user), max_new_tokens=220, temperature=temperature, top_p=top_p)


def write_scene(
    gen,
    setting: str,
    outline: str,
    segment_id: int,
    segment_desc: str,
    story_state: str,
    is_first: bool,
    temperature: float,
    top_p: float,
    max_new_tokens: int,
) -> str:
    base_rules = """
Stai scrivendo una storia cyberpunk in italiano.
Regole forti:
- Coerenza: personaggi/obiettivi/indizi non devono contraddirsi.
- Ogni scena deve far avanzare la trama (non solo atmosfera).
- Non nominare strumenti o suoni; usa solo impressioni emotive.
- 1–3 paragrafi, prosa chiara, immagini concrete, niente spiegoni.
"""

    if is_first:
        user = f"""
{base_rules}

AMBIENTAZIONE: {setting}

OUTLINE (seguilo):
{outline}

SEGMENTO {segment_id} — descrizione musicale (solo impressioni):
{segment_desc}

Scrivi la SCENA 1:
- presenta protagonista e comprimario
- introduce conflitto centrale + primo indizio del mistero
- chiudi con un gancio forte
"""
    else:
        user = f"""
{base_rules}

AMBIENTAZIONE: {setting}

OUTLINE (seguilo):
{outline}

STORY STATE (vincolante):
{story_state}

SEGMENTO {segment_id} — descrizione musicale (solo impressioni):
{segment_desc}

Scrivi la prossima scena (segmento {segment_id}):
- rispetta lo state e l’outline
- fai evolvere il mistero (nuovo indizio o falsa pista)
- modifica ritmo/tensione in base al segmento
- chiudi con micro-gancio verso la scena successiva
"""

    return llm_generate(gen, mistral_inst(user), max_new_tokens=max_new_tokens, temperature=temperature, top_p=top_p)


def main():
    parser = argparse.ArgumentParser(description="Generate a coherent story from text descriptions of musical chunks (no audio needed).")
    parser.add_argument("--segments", type=str, required=True, help="Path to JSON file with segments.")
    parser.add_argument("--out", type=str, default="story.txt", help="Output story file.")
    parser.add_argument("--model", type=str, default="mistralai/Mistral-7B-Instruct-v0.2", help="HF model id.")
    parser.add_argument("--no_4bit", action="store_true", help="Disable 4-bit quantization.")
    parser.add_argument("--no_outline", action="store_true", help="Skip outline step (less coherent).")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top_p", type=float, default=0.9)
    parser.add_argument("--max_new_tokens", type=int, default=220, help="Tokens per scene.")
    args = parser.parse_args()

    with open(args.segments, "r", encoding="utf-8") as f:
        data = json.load(f)

    setting = data.get("setting", "Milano nel 2080")
    segments = data["segments"]
    if not segments:
        raise ValueError("segments is empty")

    print(f"Loading model: {args.model}")
    gen = load_textgen(args.model, use_4bit=(not args.no_4bit))

    outline = ""
    if not args.no_outline:
        print("Building outline for global coherence...")
        outline = build_outline(gen, setting, segments, args.temperature, args.top_p)
    else:
        outline = "(outline disabilitato)"

    story_state = """PROTAGONISTA:
COMPRIMARIO:
OBIETTIVO:
CONFLITTO CENTRALE:
MISTERO (cosa sappiamo / cosa manca):
POSTO & TEMPO:
THREAD APERTI (max 4):
TONO ATTUALE (1 riga):"""

    scenes: List[str] = []

    for idx, seg in enumerate(segments):
        seg_id = seg.get("id", idx + 1)
        desc = seg["music_description"]

        print(f"✍️  Writing scene {seg_id} ...")
        scene = write_scene(
            gen=gen,
            setting=setting,
            outline=outline,
            segment_id=seg_id,
            segment_desc=desc,
            story_state=story_state,
            is_first=(idx == 0),
            temperature=args.temperature,
            top_p=args.top_p,
            max_new_tokens=args.max_new_tokens,
        )

        print("\n" + "="*60)
        print(f"### SCENA {seg_id}")
        print("="*60)
        print(scene, flush=True)
        print("="*60 + "\n", flush=True)

        scenes.append(f"### SCENA {seg_id}\n{scene}\n")

        print("Updating story state...")
        story_state = update_story_state(gen, story_state, scene, args.temperature, args.top_p)

    full_story = "\n".join(scenes).strip()

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(full_story)

    # opzionale: salva anche outline/state finale
    with open(args.out.replace(".txt", "_outline.txt"), "w", encoding="utf-8") as f:
        f.write(outline.strip() + "\n")
    with open(args.out.replace(".txt", "_state_finale.txt"), "w", encoding="utf-8") as f:
        f.write(story_state.strip() + "\n")

    print(f"Story saved to: {args.out}")
    print(f"Outline saved to: {args.out.replace('.txt','_outline.txt')}")
    print(f"Final state saved to: {args.out.replace('.txt','_state_finale.txt')}")


if __name__ == "__main__":
    main()
