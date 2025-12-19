import subprocess
import os
from pathlib import Path
import shutil

def run_pipeline(audio_file):
    # --- 1. CONFIGURAZIONE PERCORSI ASSOLUTI ---
    # Ottiene la cartella esatta dove si trova BARD.py
    root_dir = Path(__file__).parent.resolve()
    
    # Cartelle di destinazione
    dir_audio_analysis = root_dir / "audioAnalysis"
    dir_story_creation = root_dir / "storyCreation"

    # File Audio (Input)
    audio_path = root_dir / audio_file
    
    # File Output attesi (Percorsi Assoluti per sicurezza)
    # Questi ci servono per dire agli script ESATTAMENTE dove scrivere
    path_segments_output = dir_story_creation / "segments.json"
    path_storia_output = dir_story_creation / "storia.txt"

    # Controllo pre-esecuzione
    if not audio_path.exists():
        print(f"❌ ERRORE: File audio non trovato: {audio_path}")
        return
    
    # Controllo che le cartelle esistano (se no le crea, per evitare errori)
    dir_story_creation.mkdir(exist_ok=True)

    print(f"🚀 Avvio Pipeline BARD (GPU Attiva) | Input: {audio_file}")
    print(f"📂 I file verranno organizzati nelle sottocartelle corrette.\n")

    try:
        # ---------------------------------------------------------
        # FASE 1: Generazione Labelbank
        # Cartella di esecuzione: audioAnalysis
        # Output: clap_unified_labelbank.json (rimane dentro audioAnalysis)
        # ---------------------------------------------------------
        print("[1/3] Generazione labelbank (in audioAnalysis)...")
        subprocess.run([
            "python", "build_label_v2.py", 
            "--max_caps", "300", 
            "--max_chars", "100", 
            "--no-context", 
            "--no-ensemble"
        ], cwd=str(dir_audio_analysis), check=True)

        # ---------------------------------------------------------
        # FASE 2: Analisi Audio CLAP
        # Cartella di esecuzione: audioAnalysis
        # Input: Audio (path assoluto), Labelbank (locale)
        # Output: segments.json (lo forziamo dentro storyCreation)
        # ---------------------------------------------------------
        print(f"\n[2/3] Analisi Audio CLAP (salvataggio in storyCreation)...")
        subprocess.run([
            "python", "clap_local_v2.py",
            "--audio", str(audio_path),           # Path assoluto audio
            "--mode", "embeddings",
            "--labelbank_json", "clap_unified_labelbank.json", # Lo trova qui (cwd)
            "--top_k", "3",
            "--chunk_s", "10",
            "--out", str(path_segments_output)    # <-- FORZIAMO L'USCITA QUI
        ], cwd=str(dir_audio_analysis), check=True)

        # ---------------------------------------------------------
        # FASE 3: Creazione Storia
        # Cartella di esecuzione: storyCreation
        # Input: segments.json (locale, perché l'abbiamo messo lì al punto 2)
        # Output: storia.txt (locale)
        # ---------------------------------------------------------
        print("\n[3/3] Generazione Storia (in storyCreation)...")
        subprocess.run([
            "python", "story_from_descriptions.py",
            "--segments", "segments.json",        # Lo trova qui (cwd)
            "--out", "storia.txt"                 # Salva qui (cwd)
        ], cwd=str(dir_story_creation), check=True)

        print(f"\n✅ PIPELINE COMPLETATA!")
        print(f"📄 Labelbank -> {dir_audio_analysis / 'clap_unified_labelbank.json'}")
        print(f"📄 Segments  -> {path_segments_output}")
        print(f"📄 Storia    -> {path_storia_output}")

    except subprocess.CalledProcessError as e:
        print(f"\n❌ ERRORE CRITICO (Codice {e.returncode}): Uno script è fallito.")
    except Exception as e:
        print(f"\n⚠️ Errore imprevisto: {e}")

if __name__ == "__main__":
    run_pipeline("GIOVANNI.mp3")