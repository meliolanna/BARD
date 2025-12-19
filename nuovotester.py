import time
from pythonosc import udp_client


ip = "127.0.0.1"
port = 5005
client = udp_client.SimpleUDPClient(ip, port)

timing = 15

data = {
  "fragments": [
    {
      "id": 1,
      "mood": "CALM",
      "text": "The sun sets over the bustling city of New York, 1920. Protagonist, a weary jazz singer named Etta, finishes her last performance at the smoky speakeasy. Side character, an aging pianist named Charlie, packs up his belongings, his eyes filled with sadness. Their connection, once electric, now"
    },
    {
      "id": 2,
      "mood": "ANXIOUS",
      "text": "MOOD: ANXIOUS\n\nEtta's voice trembled as she gathered her belongings, her eyes darting around the dimly lit room. The once vibrant speakeasy now felt like an empty shell, the laughter and music long silenced. The air was thick with uncertainty, the tension in the room palpable. Etta could sense the weight of their past, the unspoken"
    },
    {
      "id": 3,
      "mood": "CALM",
      "text": "Etta's heart raced as she clutched the incriminating evidence, her mind racing with thoughts. The room seemed to close in around her, the shadows growing longer and more menacing. But then, a voice broke through the silence. It was Big Al, his tone steady and firm. He revealed the truth –"
    }
  ],
  "full_story": "The sun sets over the bustling city of New York, 1920. Protagonist, a weary jazz singer named Etta, finishes her last performance at the smoky speakeasy. Side character, an aging pianist named Charlie, packs up his belongings, his eyes filled with sadness. Their connection, once electric, now\n\nMOOD: ANXIOUS\n\nEtta's voice trembled as she gathered her belongings, her eyes darting around the dimly lit room. The once vibrant speakeasy now felt like an empty shell, the laughter and music long silenced. The air was thick with uncertainty, the tension in the room palpable. Etta could sense the weight of their past, the unspoken\n\nEtta's heart raced as she clutched the incriminating evidence, her mind racing with thoughts. The room seemed to close in around her, the shadows growing longer and more menacing. But then, a voice broke through the silence. It was Big Al, his tone steady and firm. He revealed the truth –"
}


time.sleep(60) # lo sto usando ora solo per dare il tempo di runnare su processing le cose così dopo vedo quando gli arrivano i dati
print(f"Invio dati a {ip}:{port}...")


client.send_message("/config/duration", timing) 
print(f"Inviata durata: {timing}s")

# 2. Invio i segmenti uno alla volta
# Pattern: /segment -> [categoria (int), storia (string)]
for item in data["fragments"]:
    cat = item["mood"]
    txt = item["text"]
    client.send_message("/segment", [cat, txt])
    print(f"Inviato segmento cat {cat}")
    time.sleep(0.05) # Piccola pausa per non intasare la rete (buona pratica)

print("Trasmissione completata.")