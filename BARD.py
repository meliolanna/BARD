import argparse
import subprocess
import sys
from pathlib import Path

import librosa


def parse_ratio(r: str) -> float:
    """
    Accepts:
      - "1/5" -> 0.2
      - "0.2" -> 0.2
    """
    s = r.strip()
    if "/" in s:
        a, b = s.split("/", 1)
        a = float(a.strip())
        b = float(b.strip())
        if b == 0:
            raise ValueError("Ratio denominator cannot be 0.")
        return a / b
    return float(s)


def compute_chunk_and_words(duration_s: float, ratio: float, reading_wpm: float) -> tuple[int, int]:
    """
    - chunk_s: duration * ratio (e.g. 50s * 1/5 = 10s)
    - words: how many words can be read in chunk_s seconds at reading_wpm
    """
    if duration_s <= 0:
        raise ValueError("Audio duration is 0 or invalid.")

    # keep ratio in a sane range (still allow >1 if you *really* want, but clamp to avoid surprises)
    ratio = max(0.001, min(ratio, 1.0))

    chunk_s = max(1, int(round(duration_s * ratio)))

    # words = seconds * (words/min) / 60
    words = int(round(chunk_s * (reading_wpm / 60.0)))
    words = max(5, words)  # never too tiny

    return chunk_s, words


def run_pipeline(
    audio_file: str,
    ratio_str: str = "1/3",
    reading_wpm: float = 180.0,
    build_labelbank: bool = False,
    force_labelbank: bool = False,
):
    root_dir = Path(__file__).parent.resolve()
    dir_audio_analysis = root_dir / "audioAnalysis"
    dir_story_creation = root_dir / "storyCreation"

    audio_path = (root_dir / audio_file).resolve()

    # Fixed default outputs (as you requested)
    labelbank_path = (dir_audio_analysis / "clap_unified_labelbank.json").resolve()
    clap_out_path = (dir_audio_analysis / "clap_output.json").resolve()

    # --- checks ---
    if not dir_audio_analysis.exists():
        print(f"ERRORE: cartella mancante: {dir_audio_analysis}")
        return

    if not dir_story_creation.exists():
        print(f"ERRORE: cartella mancante: {dir_story_creation}")
        return

    if not audio_path.exists():
        print(f"ERRORE: file audio non trovato: {audio_path}")
        return

    print(f"\nAvvio Pipeline BARD | Input: {audio_path.name}")
    print(f"Root: {root_dir}\n")

    # --- duration ---
    try:
        duration = librosa.get_duration(path=str(audio_path))
        print(f"Durata: {duration:.2f} s")
    except Exception as e:
        print(f"ERRORE: impossibile leggere l'audio: {e}")
        return

    # --- compute chunk_s + words from ratio + reading speed ---
    try:
        ratio = parse_ratio(ratio_str)
        chunk_s, words = compute_chunk_and_words(duration, ratio, reading_wpm)
    except Exception as e:
        print(f"ERRORE: ratio non valido ({ratio_str}): {e}")
        return

    print(f"ratio: {ratio_str}  -> chunk_s: {chunk_s} s")
    print(f"reading_wpm: {reading_wpm:.0f} -> words per chunk: {words}\n")

    py = sys.executable

    # --- [0/2] labelbank (optional) ---
    try:
        should_build = False
        if force_labelbank:
            should_build = True
        elif build_labelbank:
            should_build = True
        elif not labelbank_path.exists():
            # auto-build only if missing
            should_build = True

        if should_build:
            print("[0/2] Generazione labelbank (audioAnalysis)...")
            subprocess.run(
                [
                    py, str(dir_audio_analysis / "build_label_v2.py"),
                    "--max_caps", "300",
                    "--max_chars", "100",
                    "--no-context",
                    "--no-ensemble",
                ],
                cwd=str(root_dir),
                check=True
            )
            if not labelbank_path.exists():
                print(f"ERRORE: labelbank non creato: {labelbank_path}")
                return
        else:
            if not labelbank_path.exists():
                print(f"ERRORE: labelbank mancante e build disabilitato: {labelbank_path}")
                print("Suggerimento: usa --build_labelbank oppure --force_labelbank")
                return
            print("[0/2] Labelbank già presente -> skip.\n")

        # --- [1/2] CLAP ---
        print("[1/2] Analisi Audio CLAP (audioAnalysis/clap_output.json)...")
        subprocess.run(
            [
                py, str(dir_audio_analysis / "clap_local_v2.py"),
                "--audio", str(audio_path),
                "--mode", "embeddings",
                "--labelbank_json", str(labelbank_path),
                "--top_k", "1",
                "--chunk_s", str(chunk_s),
                "--out", str(clap_out_path),
            ],
            cwd=str(root_dir),   # run like your terminal command (paths from project root)
            check=True
        )

        if not clap_out_path.exists():
            print(f"ERRORE: clap_output.json non trovato: {clap_out_path}")
            return

        # --- [2/2] STORY ---
        print("\n[2/2] Generazione Storia (storyCreation/story_from_description.py)...")

        story_script = dir_story_creation / "story_from_description.py"
        if not story_script.exists():
            alt = dir_story_creation / "story_from_descriptions.py"
            if alt.exists():
                story_script = alt
            else:
                print("ERRORE: non trovo story_from_description.py (o story_from_descriptions.py) in storyCreation.")
                return

        subprocess.run(
            [
                py, str(story_script),
                "--segments", str(clap_out_path),
                "--words", str(words),
                print(words),
                "--print_live",
            ],
            cwd=str(root_dir),  # same as your terminal usage
            check=True
        )

        print("\nPIPELINE COMPLETATA")
        print(f"📄 Labelbank   -> {labelbank_path}")
        print(f"📄 CLAP output -> {clap_out_path}")
        print(f"📄 Words/chunk -> {words} (chunk_s={chunk_s}, wpm={reading_wpm:.0f})")

    except subprocess.CalledProcessError as e:
        print(f"\nERRORE CRITICO: uno script è fallito (exit code {e.returncode}).")
    except Exception as e:
        print(f"\nErrore imprevisto: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="BARD pipeline: CLAP -> story, with ratio-based chunking + reading-based words.")
    ap.add_argument("--audio", default="GIOVANNI.mp3", help="Audio file path relative to project root.")
    ap.add_argument("--ratio", default="1/5", help="Chunk length as ratio of song duration (e.g. 1/5 or 0.2).")
    ap.add_argument("--wpm", type=float, default=180.0, help="Reading speed in words-per-minute (used to compute --words).")
    ap.add_argument("--build_labelbank", action="store_true", help="Build labelbank only if you ask (or if missing).")
    ap.add_argument("--force_labelbank", action="store_true", help="Always rebuild labelbank even if it exists.")
    args = ap.parse_args()

    run_pipeline(
        audio_file=args.audio,
        ratio_str=args.ratio,
        reading_wpm=args.wpm,
        build_labelbank=args.build_labelbank,
        force_labelbank=args.force_labelbank,
    )


