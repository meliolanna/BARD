import subprocess
import sys
from pathlib import Path
import librosa


def run_pipeline(audio_file: str):
    # --- PATHS ASSOLUTI ---
    root_dir = Path(__file__).parent.resolve()
    dir_audio_analysis = root_dir / "audioAnalysis"
    dir_story_creation = root_dir / "storyCreation"

    audio_path = (root_dir / audio_file).resolve()

    # Output finali
    path_segments_output = (dir_story_creation / "segments.json").resolve()
    path_story_json_output = (dir_story_creation / "story.json").resolve()
    path_story_txt_output = (dir_story_creation / "storia.txt").resolve()

    # --- CONTROLLI ---
    if not dir_audio_analysis.exists():
        print(f"ERRORE: cartella mancante: {dir_audio_analysis}")
        return

    if not audio_path.exists():
        print(f"ERRORE: file audio non trovato: {audio_path}")
        return

    dir_story_creation.mkdir(parents=True, exist_ok=True)

    print(f"\nAvvio Pipeline BARD | Input: {audio_path.name}")
    print(f"Root: {root_dir}\n")

    # --- DURATA AUDIO ---
    try:
        duration = librosa.get_duration(path=str(audio_path))
        print(f"Durata: {duration:.2f} s")
    except Exception as e:
        print(f"ERRORE: impossibile leggere l'audio: {e}")
        return

    chunk_s = max(1, int(duration / 5))
    print(f"chunk_s: {chunk_s}\n")

    py = sys.executable  # usa il python dell'ambiente (venv)

    try:
        # --- [1/3] LABELBANK ---
        print("[1/3] Generazione labelbank (audioAnalysis)...")
        subprocess.run(
            [
                py, "build_label_v2.py",
                "--max_caps", "300",
                "--max_chars", "100",
                "--no-context",
                "--no-ensemble",
            ],
            cwd=str(dir_audio_analysis),
            check=True
        )

        labelbank_path = dir_audio_analysis / "clap_unified_labelbank.json"
        if not labelbank_path.exists():
            print(f"ERRORE: labelbank non creato: {labelbank_path}")
            return

        # --- [2/3] CLAP ANALYSIS ---
        print("\n[2/3] Analisi Audio CLAP (output in storyCreation)...")
        subprocess.run(
            [
                py, "clap_local_v2.py",
                "--audio", str(audio_path),
                "--mode", "embeddings",
                "--labelbank_json", labelbank_path.name,  # file nel cwd
                "--top_k", "1",
                "--chunk_s", str(chunk_s),
                "--out", str(path_segments_output),
            ],
            cwd=str(dir_audio_analysis),
            check=True
        )

        if not path_segments_output.exists():
            print(f"ERRORE: segments.json non trovato: {path_segments_output}")
            return

        # --- [3/3] STORY CREATION ---
        print("\n[3/3] Generazione Storia (storyCreation)...")

        # accetta entrambi i nomi possibili
        story_script = None
        for candidate in ["story_from_description.py", "story_from_descriptions.py"]:
            p = dir_story_creation / candidate
            if p.exists():
                story_script = candidate
                break

        if story_script is None:
            print("ERRORE: non trovo lo script story_from_description(s).py in storyCreation.")
            print("Mi aspetto uno di questi file:")
            print(f" - {dir_story_creation / 'story_from_description.py'}")
            print(f" - {dir_story_creation / 'story_from_descriptions.py'}")
            return

        subprocess.run(
            [
                py, story_script,
                "--segments", "segments.json",
                "--out_json", "story.json",
                "--out_txt", "storia.txt",
            ],
            cwd=str(dir_story_creation),
            check=True
        )

        print("\nPIPELINE COMPLETATA ✅")
        print(f"📄 Labelbank -> {labelbank_path}")
        print(f"📄 Segments  -> {path_segments_output}")
        print(f"📄 Story JSON-> {path_story_json_output}")
        print(f"📄 Storia TXT-> {path_story_txt_output}")

    except subprocess.CalledProcessError as e:
        print(f"\nERRORE CRITICO: uno script è fallito (exit code {e.returncode}).")
    except Exception as e:
        print(f"\nErrore imprevisto: {e}")


if __name__ == "__main__":
    run_pipeline("GIOVANNI.mp3")
