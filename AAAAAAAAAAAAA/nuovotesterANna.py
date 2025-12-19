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
      "text": "The train from Cremona hissed into Milano Lambrate. Three students stepped onto the platform, marching solemnly toward the Politecnico's Campus Leonardo. Today was the final battle: the submission for Creative Programming and Computing."
    },
    {
      "id": 2,
      "mood": "CALM",
      "text": "They seized a table in a chaotic study room and summoned their secret weapon—a fourth teammate connecting remotely from Calabria. 'I'm in', his voice crackled over the laptop speakers."
    },
    {
      "id": 3,
      "mood": "ANXIOUS",
      "text": "Disaster struck immediately. The code refused to compile, sensors remained lifeless, and morale plummeted. 'Nothing works!' one cried out, burying his face in his hands. For hours, they fought against bugs and syntax errors, guided by the calm voice from the south."
    },
    {
      "id": 3,
      "mood": "ENERGETIC",
      "text": "Suddenly, a breakthrough. A single line of code fixed the loop. The prototype finally blinked to life just minutes before the deadline. Breathless, they rushed to the presentation. As the device performed perfectly before the professors, they shared a tired, triumphant glance with the pixelated face on their screen. The war was over; they had won."
    }
  ],
  "full_story": ""
}


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
