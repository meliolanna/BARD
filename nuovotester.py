    

import time
from pythonosc import udp_client
from pathlib import Path

import json

# Percorso al file JSON nella stessa cartella di questo script
json_path = Path(__file__).resolve().parent / "story.json"

with json_path.open("r", encoding="utf-8") as f:
    data = json.load(f)


ip = "127.0.0.1"
port = 5005
client = udp_client.SimpleUDPClient(ip, port)

timing = 50

time.sleep(10) # lo sto usando ora solo per dare il tempo di runnare su processing le cose così dopo vedo quando gli arrivano i dati
print(f"Invio dati a {ip}:{port}...")


client.send_message("/config/duration", timing) 
print(f"Inviata durata: {timing}s")

# 2. Invio i segmenti uno alla volta
# Pattern: /segment -> [categoria (int), storia (string)]
for item in data["fragments"]:
    cat = str(item["mood"])
    txt = str(item["text"])
    client.send_message("/segment", [cat, txt])
    print(f"Inviato segmento cat {txt}")
    time.sleep(0.05) # Piccola pausa per non intasare la rete (buona pratica)

client.send_message("/start", [])

print("Trasmissione completata.")