import json
import re
import urllib.request
from collections import deque
import random
import argparse

ONTOLOGY_URL = "https://raw.githubusercontent.com/audioset/ontology/master/ontology.json"

# -----------------------------
# Heuristic hints (keep these)
# -----------------------------
INSTRUMENT_HINTS = {
    "guitar","piano","violin","cello","drum","drums","bass","flute","saxophone","trumpet","clarinet",
    "harp","organ","ukulele","banjo","mandolin","trombone","tuba","oboe","voice","vocal","choir",
    "synth","synthesizer","accordion","marimba","xylophone","cymbal","snare","kick","horn","strings",
}
GENRE_HINTS = {
    "jazz","rock","pop","hip hop","rap","techno","house","ambient","classical","blues","metal",
    "reggae","folk","disco","punk","edm","electronic","country","opera",
}
DROP_EXACT = {
    "Music",
    "Musical instrument",
    "Plucked string instrument",
    "Bowed string instrument",
    "String section",
    "Percussion",
    "Singing",
}

# -----------------------------
# Caption grammar
# -----------------------------
ENERGY = [
    "very low energy", "low energy", "moderate energy", "high energy", "very high energy",
    "restrained intensity", "surging intensity"
]
TEMPO = [
    "very slow tempo", "slow tempo", "moderate tempo", "fast tempo", "very fast tempo",
    "rubato pacing", "steady pulse"
]
MOOD = [
    "dark", "bright", "warm", "cold", "bittersweet", "melancholic", "joyful",
    "ominous", "mysterious", "playful", "anxious", "serene", "solemn"
]
TEXTURE = [
    "sparse texture", "dense texture", "spacious texture", "tight and dry texture",
    "wide and reverberant space", "smooth and clean texture", "airy and light texture",
    "grainy and gritty texture", "shimmering texture"
]
TENSION = [
    "subdued tension", "rising tension", "high tension", "fragile stability",
    "unresolved tension", "sudden release", "gentle release"
]
PHRASING = [
    "long legato phrases", "short staccato gestures", "fragmented phrasing",
    "sustained tones", "sharp attacks", "breath-like phrasing"
]
ARC = [
    "static atmosphere", "gradual build", "approaching climax",
    "post-climax release", "bittersweet resolution", "melancholic closure",
    "unresolved ending"
]

CONTEXT = [
    "live concert recording",
    "live performance",
    "studio recording",
    "intimate room recording",
]
ENSEMBLE = [
    "solo performance",
    "duo performance",
    "trio performance",
    "quartet performance",
    "string quartet performance",
    "small ensemble performance",
    "band performance",
    "orchestral performance",
    "a cappella vocal performance",
]

CAPTION_WRAPPERS = [
    "{c}",
    "this audio is {c}",
    "this recording has {c}",
    "music with {c}",
    "a performance with {c}",
]

BASE_EXAMPLES = [
    "low energy, slow tempo, dark and spacious texture, subdued tension, long legato phrases, sense of isolation and mystery",
    "energy drops but emotional weight increases, fragile stability, bittersweet release, reflective pacing, unresolved warmth, melancholic closure",
]


def download_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (clap-labelbank)"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def find_id_by_name(nodes, name: str) -> str:
    for n in nodes:
        if n.get("name") == name:
            return n["id"]
    for n in nodes:
        if (n.get("name") or "").strip().lower() == name.lower():
            return n["id"]
    raise ValueError(f'Could not find node named "{name}".')


def collect_subtree_ids(nodes_by_id, root_id: str):
    visited = set()
    q = deque([root_id])
    while q:
        nid = q.popleft()
        if nid in visited:
            continue
        visited.add(nid)
        for cid in nodes_by_id[nid].get("child_ids", []) or []:
            q.append(cid)
    return visited


def is_leaf(nodes_by_id, nid: str) -> bool:
    return len(nodes_by_id[nid].get("child_ids", []) or []) == 0


def normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def build_music_leaf_names():
    nodes = download_json(ONTOLOGY_URL)
    nodes_by_id = {n["id"]: n for n in nodes}

    music_id = find_id_by_name(nodes, "Music")
    subtree_ids = collect_subtree_ids(nodes_by_id, music_id)

    leaf = []
    for nid in subtree_ids:
        if is_leaf(nodes_by_id, nid):
            name = (nodes_by_id[nid].get("name") or "").strip()
            if name and name not in DROP_EXACT:
                leaf.append(name)

    return sorted(set(leaf), key=lambda s: s.lower())


def extract_instrument_and_genre_terms(leaf_labels):
    instruments = set()
    genres = set()

    for lab in leaf_labels:
        t = normalize_text(lab)
        if any(h in t for h in INSTRUMENT_HINTS):
            instruments.add(t)
        if any(h in t for h in GENRE_HINTS):
            genres.add(t)

    # Manual important ones
    instruments |= {
        "piano", "violin", "cello", "viola", "double bass", "voice",
        "acoustic guitar", "electric guitar", "drum kit",
        "saxophone", "trumpet", "clarinet", "flute",
        "strings",
    }
    genres |= {
        "classical", "jazz", "rock", "pop", "ambient", "electronic", "opera", "folk",
        "blues", "metal", "hip hop", "techno", "house", "country", "reggae",
    }

    instruments = sorted({i for i in instruments if len(i) <= 30}, key=str)
    genres = sorted({g for g in genres if len(g) <= 20}, key=str)
    return instruments, genres


def choose_instrument_phrase(rng: random.Random, instruments, p_include: float = 0.80):
    if (not instruments) or (rng.random() > p_include):
        return ""
    k = 1 if rng.random() < 0.75 else 2
    picks = rng.sample(instruments, k=min(k, len(instruments)))

    if len(picks) == 1:
        inst = picks[0]
        style = rng.choice([
            f"featuring {inst}",
            f"with prominent {inst}",
            f"centered on {inst}",
        ])
        return style

    inst_a, inst_b = picks[0], picks[1]
    return rng.choice([
        f"featuring {inst_a} and {inst_b}",
        f"interplay between {inst_a} and {inst_b}",
    ])


def choose_genre_phrase(rng: random.Random, genres, p_include: float = 0.65):
    if (not genres) or (rng.random() > p_include):
        return ""
    g = rng.choice(genres)
    return rng.choice([f"{g} feel", f"in a {g} style", f"{g} leaning"])


def format_caption(head_parts, body_parts):
    head = ", ".join([p for p in head_parts if p])
    body = "; ".join([p for p in body_parts if p])
    if head and body:
        return f"{head}; {body}"
    return head or body


def shrink_to_max_chars(items, max_chars: int):
    """
    items = list of dicts: {"key":..., "text":..., "prio":...}
    Higher prio gets dropped first.
    """
    # Keep only non-empty
    items = [it for it in items if it["text"]]
    # Try removing least important until fits
    while True:
        head_parts = [it["text"] for it in items if it.get("group") == "head"]
        body_parts = [it["text"] for it in items if it.get("group") == "body"]
        s = format_caption(head_parts, body_parts)
        if len(s) <= max_chars:
            return s

        # Find droppable with highest prio
        droppables = sorted(items, key=lambda it: it["prio"], reverse=True)
        if not droppables:
            break
        # drop one
        items.remove(droppables[0])

    # Last resort: truncate
    s = format_caption(
        [it["text"] for it in items if it.get("group") == "head"],
        [it["text"] for it in items if it.get("group") == "body"],
    )
    if len(s) <= max_chars:
        return s
    return s[: max(0, max_chars - 1)].rstrip(",; ") + "…"


def build_unified_captions(
    max_caps: int,
    seed: int,
    max_chars: int,
    oversample_factor: int,
    # toggles
    use_context: bool,
    use_ensemble: bool,
    use_instruments: bool,
    use_genres: bool,
    use_energy: bool,
    use_tempo: bool,
    use_mood: bool,
    use_texture: bool,
    use_tension: bool,
    use_phrasing: bool,
    use_arc: bool,
):
    rng = random.Random(seed)

    instruments, genres = [], []
    if use_instruments or use_genres:
        leaf = build_music_leaf_names()
        instruments, genres = extract_instrument_and_genre_terms(leaf)

    filtered = set()
    # include base examples (truncate if needed)
    for b in BASE_EXAMPLES:
        b2 = b if len(b) <= max_chars else (b[: max(0, max_chars - 1)].rstrip(",; ") + "…")
        filtered.add(b2)

    def make_one():
        # head
        ctx = rng.choice(CONTEXT) if use_context else ""
        ens = rng.choice(ENSEMBLE) if use_ensemble else ""
        inst = choose_instrument_phrase(rng, instruments) if use_instruments else ""
        gen = choose_genre_phrase(rng, genres) if use_genres else ""

        # body
        e = rng.choice(ENERGY) if use_energy else ""
        t = rng.choice(TEMPO) if use_tempo else ""
        m = (rng.choice(MOOD) + " tone") if use_mood else ""
        x = rng.choice(TEXTURE) if use_texture else ""
        ten = rng.choice(TENSION) if use_tension else ""
        p = rng.choice(PHRASING) if use_phrasing else ""
        a = rng.choice(ARC) if use_arc else ""

        # items with drop priority (higher -> drop first if too long)
        items = []
        # head (drop context/ensemble first)
        if ctx: items.append({"group": "head", "key": "ctx", "text": ctx, "prio": 90})
        if gen: items.append({"group": "head", "key": "gen", "text": gen, "prio": 70})
        if ens: items.append({"group": "head", "key": "ens", "text": ens, "prio": 80})
        if inst: items.append({"group": "head", "key": "inst", "text": inst, "prio": 60})

        # body (drop arc/phrasing first)
        if e: items.append({"group": "body", "key": "energy", "text": e, "prio": 10})
        if t: items.append({"group": "body", "key": "tempo", "text": t, "prio": 20})
        if m: items.append({"group": "body", "key": "mood", "text": m, "prio": 30})
        if x: items.append({"group": "body", "key": "texture", "text": x, "prio": 50})
        if ten: items.append({"group": "body", "key": "tension", "text": ten, "prio": 55})
        if p: items.append({"group": "body", "key": "phrasing", "text": p, "prio": 85})
        if a: items.append({"group": "body", "key": "arc", "text": a, "prio": 95})

        return shrink_to_max_chars(items, max_chars=max_chars)

    attempts = 0
    max_attempts = max_caps * oversample_factor * 50

    while len(filtered) < max_caps and attempts < max_attempts:
        s = make_one()
        if len(s) <= max_chars:
            filtered.add(s)
        attempts += 1

    if len(filtered) < max_caps:
        print(
            f"[WARN] Only got {len(filtered)} captions <= {max_chars} chars. "
            f"Try increasing max_chars or oversample_factor, or disabling some sections."
        )

    out = sorted(filtered, key=lambda s: (len(s), s.lower()))
    return out[:max_caps]


def build_unified_labelbank(captions):
    bank = []
    for c in captions:
        prompts = sorted({w.format(c=c) for w in CAPTION_WRAPPERS})
        bank.append({"label": c, "synonyms": [], "prompts": prompts})
    return bank


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--max_caps", type=int, default=300)
    p.add_argument("--max_chars", type=int, default=100)
    p.add_argument("--seed", type=int, default=3)
    p.add_argument("--oversample_factor", type=int, default=10)

    # toggles (Python 3.9+)
    boo = argparse.BooleanOptionalAction
    p.add_argument("--context", action=boo, default=True, help="Include context (live/studio/room).")
    p.add_argument("--ensemble", action=boo, default=True, help="Include ensemble type (solo/quartet/etc.).")
    p.add_argument("--instruments", action=boo, default=True, help="Include instrument phrases.")
    p.add_argument("--genres", action=boo, default=True, help="Include genre phrases.")

    p.add_argument("--energy", action=boo, default=True)
    p.add_argument("--tempo", action=boo, default=True)
    p.add_argument("--mood", action=boo, default=True)
    p.add_argument("--texture", action=boo, default=True)
    p.add_argument("--tension", action=boo, default=True)
    p.add_argument("--phrasing", action=boo, default=True)
    p.add_argument("--arc", action=boo, default=True)

    args = p.parse_args()

    captions = build_unified_captions(
        max_caps=args.max_caps,
        seed=args.seed,
        max_chars=args.max_chars,
        oversample_factor=args.oversample_factor,
        use_context=args.context,
        use_ensemble=args.ensemble,
        use_instruments=args.instruments,
        use_genres=args.genres,
        use_energy=args.energy,
        use_tempo=args.tempo,
        use_mood=args.mood,
        use_texture=args.texture,
        use_tension=args.tension,
        use_phrasing=args.phrasing,
        use_arc=args.arc,
    )
    bank = build_unified_labelbank(captions)

    with open("clap_unified_labels.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(captions) + "\n")

    with open("clap_unified_labelbank.json", "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)

    print(f"Wrote clap_unified_labels.txt ({len(captions)} captions, max {args.max_chars} chars)")
    print(f"Wrote clap_unified_labelbank.json ({len(bank)} items)")
    print("\nPreview:")
    for c in captions[:6]:
        print(" -", c)


if __name__ == "__main__":
    main()
