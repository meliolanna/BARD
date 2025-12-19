import asyncio
import edge_tts
import pygame
import os
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

# --- CONFIGURAZIONE VOCE ---
# Voci Maschili Inglesi consigliate:
# "en-US-ChristopherNeural" (Narrativo, profondo, ottimo per storie)
# "en-US-GuyNeural" (Più casual, standard)
# "en-US-EricNeural" (Energico)
# "en-GB-RyanNeural" (Britannico)
VOICE = "en-US-ChristopherNeural" 
OUTPUT_FILE = "temp_voice.mp3"

# Inizializza audio background
pygame.mixer.init()

# Funzione asincrona per generare l'audio con Edge
async def generate_edge_audio(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_file)

def speak_handler(address, *args):
    text_to_read = args[0]
    print(f"🗣️  [Christopher]: {text_to_read}")
    
    try:
        # 1. Ferma e libera l'audio precedente
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        
        # 2. Cancella il vecchio file se esiste (per sicurezza su Windows)
        if os.path.exists(OUTPUT_FILE):
            try:
                os.remove(OUTPUT_FILE)
            except PermissionError:
                print("⚠️  Impossibile rimuovere il file precedente (ancora in uso?)")

        # 3. Genera il nuovo audio (chiamata asincrona dentro codice sincrono)
        asyncio.run(generate_edge_audio(text_to_read, OUTPUT_FILE))
        
        # 4. Riproduci
        pygame.mixer.music.load(OUTPUT_FILE)
        pygame.mixer.music.play()
        
    except Exception as e:
        print(f"❌ Errore Audio: {e}")

# Configurazione Server OSC
dispatcher = Dispatcher()
dispatcher.map("/speak", speak_handler)

ip = "127.0.0.1"
port = 5006

print(f"🎤 Server Vocale EDGE (Maschile) in ascolto su {ip}:{port}")
print(f"🔊 Voce selezionata: {VOICE}")

# Avvio server
server = BlockingOSCUDPServer((ip, port), dispatcher)
server.serve_forever()