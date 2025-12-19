import java.util.HashMap;
import oscP5.*;
import netP5.*;

// --- CONFIGURAZIONE DI RETE ---
OscP5 oscP5;
// IP: Se Python gira sullo stesso computer usa "127.0.0.1". 
// Se è un altro computer, metti l'IP di quel computer qui solo se devi inviare, 
// ma per RICEVERE basta che la porta sia giusta.
String ip = "127.0.0.1"; 
int port = 5005; // Assicurati che Python mandi a questa porta
NetAddress pythonVoiceLocation;

// --- STRUTTURA DATI PER I SEGMENTI ---
ArrayList<Segmento> playlist = new ArrayList<Segmento>();

// --- VARIABILI GLOBALI ---
float slideDuration = 10.0; // Durata di default (sarà sovrascritta da Python)
boolean isPlaying = false;  // Diventa true quando riceve il segnale /start
int currentSegmentIndex = -1;
int lastSegmentTime = 0;

// Variabili Grafiche Originali
int fontSize = 40;
float leading = fontSize * 1.4;
float margin = 200;

// Stati Animazione Parole
int wordSpawnRate = 100;
float flightSpeed = 6;

final int STATE_WRITING = 0;
final int STATE_WAITING_ARRIVAL = 1;
final int STATE_READING = 2; 

int currentState = STATE_WRITING;
ArrayList<FlyingWord> wordsObjects;
int currentWordIndex = 0;
ArrayList<ArrayList<FlyingWord>> pages; 
int currentPageIndex = 0;

int lastWordSpawnTime = 0;
int pauseStartTime = 0;

ArrayList<BgParticle> bgParticles;
HashMap<String, Atmosphere> moods;

PGraphics nebulaCanvas; 
float noiseScale = 0.003f;
float timeZ = 0; 

Atmosphere startMood;   
Atmosphere targetMood;  
Atmosphere currentVals; 
float transitionDuration = 2000; 
float transitionStartTime = -9999; 

PFont myFont;
String fullText = ""; 

// --------------------------------------------------------
// SETUP
// --------------------------------------------------------
void setup() {
  fullScreen(P2D); 
  
  // Inizializza OSC sulla porta di ascolto
  oscP5 = new OscP5(this, port);
  pythonVoiceLocation = new NetAddress("127.0.0.1", 5006);
  
  myFont = createFont("Georgia", fontSize); 
  textFont(myFont);
  textSize(fontSize);
  textAlign(LEFT, CENTER);
  
  wordsObjects = new ArrayList<FlyingWord>();
  bgParticles = new ArrayList<BgParticle>();
  
  nebulaCanvas = createGraphics(width/4, height/4, P2D);
  
  setupMoods();
  
  // Impostiamo un mood di default per l'attesa
  setMood("ENERGETIC"); 
  currentVals = targetMood.copy();
  startMood = targetMood.copy();
  
  // Inizializziamo particelle base
  for(int i=0; i<currentVals.particleCount; i++) {
    bgParticles.add(new BgParticle());
  }
}

// --------------------------------------------------------
// DRAW
// --------------------------------------------------------
void draw() {
  // 1. Calcolo transizioni grafiche
  float elapsed = millis() - transitionStartTime;
  float t = constrain(elapsed / transitionDuration, 0, 1);
  float smoothT = t * t * (3 - 2 * t); 
  
  updateCurrentAtmosphere(smoothT);
  
  // Gestione numero particelle
  int targetCount = (int)lerp(startMood.particleCount, targetMood.particleCount, smoothT);
  if (bgParticles.size() < targetCount) bgParticles.add(new BgParticle());
  else if (bgParticles.size() > targetCount) bgParticles.remove(0);

  // 2. Disegno Sfondo e Atmosfera
  background(currentVals.bgColor);
  generateNebula(currentVals.nebulaColor, currentVals.nebulaAlphaMax, currentVals.nebulaSpeed);
  blendMode(ADD);  
  image(nebulaCanvas, 0, 0, width, height); 
  blendMode(BLEND);
  
  for(BgParticle p : bgParticles){
    p.update(currentVals.particleSpeedY, currentVals.chaos);
    p.display(currentVals.particleColor);
  }

  // 3. LOGICA PRINCIPALE
  if (!isPlaying) {
    // SCHERMATA DI ATTESA DATI
    fill(255);
    textAlign(CENTER, CENTER);
    textSize(fontSize+20);
    text("BARD", width/2, height/2-30);
    textSize(fontSize-10);
    text("I'll tell you a story...", width/2, height/2+40);
    textAlign(LEFT, CENTER); 
  } 
  else {
    // A. Controllo Timer Generale
    if (millis() - lastSegmentTime > slideDuration * 1000) {
      loadNextSegment();
    }
    
    // B. Aggiorna logica parole
    updateWordLogic();
    drawWords();
  }
}

// --------------------------------------------------------
// GESTIONE CAMBIO SEGMENTO
// --------------------------------------------------------

void loadNextSegment() {
  currentSegmentIndex++;
  
  if (currentSegmentIndex >= playlist.size()) {
    currentSegmentIndex = 0;
  }
  
  Segmento seg = playlist.get(currentSegmentIndex);
  
  // DEBUG: Stampa cosa sta caricando
  println(">>> CARICAMENTO SEGMENTO " + currentSegmentIndex);
  println(">>> TESTO: " + seg.testo);
  
  setMood(seg.categoria);
  
  fullText = seg.testo;
  calculatePages(); 
  loadPage(0);    
  
  OscMessage msgVoce = new OscMessage("/speak");
  msgVoce.add(seg.testo); // Aggiunge il testo al messaggio
  oscP5.send(msgVoce, pythonVoiceLocation); // Spedisce a Python (porta 12001)
  println(">>> COMANDO VOCALE INVIATO PER: " + seg.testo);
  
  // DEBUG: Controlliamo se ha creato le parole volanti
  println(">>> PAROLE CREATE: " + wordsObjects.size());
  
  lastSegmentTime = millis();
}

// --------------------------------------------------------
// LOGICA PAROLE
// --------------------------------------------------------
void updateWordLogic() {
  int now = millis();
  
  if (currentState == STATE_WRITING) {
    if (now - lastWordSpawnTime > wordSpawnRate && currentWordIndex < wordsObjects.size()) {
      FlyingWord w = wordsObjects.get(currentWordIndex); 
      w.active = true; 
      lastWordSpawnTime = now;
      currentWordIndex++;
      
      if (currentWordIndex >= wordsObjects.size()) {
        currentState = STATE_WAITING_ARRIVAL;
      }
    }
  }
  else if (currentState == STATE_WAITING_ARRIVAL) {
    if (wordsObjects.size() > 0) {
      FlyingWord lastWord = wordsObjects.get(wordsObjects.size() - 1);
      if (lastWord.locked) { 
        currentState = STATE_READING;
        for(FlyingWord w : wordsObjects) w.targetGlow = 255;
      }
    } else {
       currentState = STATE_READING; 
    }
  }
}

void calculatePages() {
  textSize(fontSize); 
  pages = new ArrayList<ArrayList<FlyingWord>>();
  
  String[] rawWords = split(fullText, ' ');
  float x = margin;
  float y = margin; 
  float maxWidth = width - (margin * 2);
  int currentSentenceId = 0; 
  ArrayList<FlyingWord> currentPageList = new ArrayList<FlyingWord>();
  
  for (String str : rawWords) {
    float w = textWidth(str + " ");
    
    if (x + w > margin + maxWidth) { 
      x = margin;
      y += leading; 
    }
    
    currentPageList.add(new FlyingWord(str, x, y, currentSentenceId));
    x += w; 
  }
  
  if (currentPageList.size() > 0) {
    pages.add(currentPageList);
  }
}

void loadPage(int index) {
  if (pages.size() > 0) {
    wordsObjects = pages.get(0); 
    currentWordIndex = 0;
    currentState = STATE_WRITING;
    lastWordSpawnTime = millis();
  } else {
    wordsObjects.clear();
  }
}

void drawWords() {
  blendMode(BLEND); 
  
  // Contatore per vedere quante parole sono attive
  int attive = 0;
  
  for (FlyingWord w : wordsObjects) {
    if (w.active) { 
      w.update(); 
      w.displayBase(currentVals.textColor, currentVals.glowColor); 
      attive++;
    }
  }
  
  // Se non ci sono parole attive mentre siamo in PLAY, c'è un problema
  if (isPlaying && attive == 0 && wordsObjects.size() > 0) {
    // println("Allerta: Nessuna parola attiva!"); // Scommenta se vuoi spam nella console
  }

  blendMode(ADD);
  for (FlyingWord w : wordsObjects) {
    if (w.active && w.currentGlow > 1) { w.displayGlowingOnly(currentVals.glowColor); }
  }
  blendMode(BLEND);
}

// --------------------------------------------------------
// OSC EVENT
// --------------------------------------------------------
void oscEvent(OscMessage msg) {
  println("ricevuto qualcosa");
  if (msg.checkAddrPattern("/config/duration")) {
    if(msg.checkTypetag("f")) slideDuration = msg.get(0).floatValue();
    else if(msg.checkTypetag("i")) slideDuration = msg.get(0).intValue();
    println(">>> Durata slide: " + slideDuration);
    return;
  }
  
  if (msg.checkAddrPattern("/segment")) {
    /*int cat = 0;
    String txt = "";
    if (msg.checkTypetag("is")) {
      cat = msg.get(0).intValue();
      txt = msg.get(1).stringValue();
      println(" -> Letto (Int/String): Cat " + cat + ", Txt: " + txt);
    } 
    // CASO COMUNE: Float e Stringa ("fs")
    else if (msg.checkTypetag("fs")) {
      cat = (int)msg.get(0).floatValue(); // Convertiamo il float in int
      txt = msg.get(1).stringValue();
      println(" -> Letto (Float/String): Cat " + cat + ", Txt: " + txt);
    }*/
    String cat = msg.get(0).stringValue();
    String txt = msg.get(1).stringValue();
    playlist.add(new Segmento(cat, txt));
    println(">>> Ricevuto: " + txt);     
    
    return;
  }
  
  if (msg.checkAddrPattern("/start")) {
    if (playlist.size() > 0) {
      println(">>> START!");
      isPlaying = true;
      lastSegmentTime = millis() - (int)(slideDuration*1000); 
    }
    return;
  }
}

// --------------------------------------------------------
// GESTIONE ATMOSFERE
// --------------------------------------------------------

void updateCurrentAtmosphere(float smoothT) {
  currentVals.bgColor = lerpColor(startMood.bgColor, targetMood.bgColor, smoothT);
  currentVals.textColor = lerpColor(startMood.textColor, targetMood.textColor, smoothT);
  currentVals.glowColor = lerpColor(startMood.glowColor, targetMood.glowColor, smoothT);
  currentVals.particleColor = lerpColor(startMood.particleColor, targetMood.particleColor, smoothT);
  currentVals.particleSpeedY = lerp(startMood.particleSpeedY, targetMood.particleSpeedY, smoothT);
  currentVals.chaos = lerp(startMood.chaos, targetMood.chaos, smoothT);
  currentVals.nebulaColor = lerpColor(startMood.nebulaColor, targetMood.nebulaColor, smoothT);
  currentVals.nebulaAlphaMax = lerp(startMood.nebulaAlphaMax, targetMood.nebulaAlphaMax, smoothT);
  currentVals.nebulaSpeed = lerp(startMood.nebulaSpeed, targetMood.nebulaSpeed, smoothT);
}

void setMood(String name) {
  if (moods.containsKey(name)) {
    if (currentVals != null) startMood = currentVals.copy();
    targetMood = moods.get(name);
    transitionStartTime = millis();
  }
}

void mapClassToMood(int val) {
    switch(val) {
      case 1: setMood("ENERGETIC"); break;
      case 2: setMood("SOLO"); break;
      case 3: setMood("CALM"); break;
      case 4: setMood("DEEP"); break;
      case 5: setMood("DISSONANT"); break;
      case 6: setMood("ANXIOUS"); break;
      default: setMood("CALM"); break;
    }
}

void setupMoods() {
  moods = new HashMap<String, Atmosphere>();
  
  moods.put("ENERGETIC", new Atmosphere(color(40, 10, 5), color(240, 220, 180), color(255, 160, 20), color(255, 100, 50), -3.0f, 250.0f, 5.0f, color(255, 80, 20), 200.0f, 0.03f));
  moods.put("SOLO", new Atmosphere(color(15, 15, 18), color(210, 210, 215), color(180, 180, 200), color(0,0,0,0), 0f, 0f, 0f, color(50, 50, 60), 60.0f, 0.002f));
  moods.put("CALM", new Atmosphere(color(20, 15, 35), color(170, 180, 210), color(100, 150, 255), color(150, 100, 200), -0.3f, 60.0f, 0.2f, color(80, 100, 220), 150.0f, 0.008f));
  moods.put("DEEP", new Atmosphere(color(2, 5, 15), color(110, 130, 150), color(0, 100, 200), color(0, 50, 100), 0.1f, 100.0f, 0.5f, color(0, 40, 120), 180.0f, 0.005f));
  moods.put("DISSONANT", new Atmosphere(color(15, 20, 18), color(190, 210, 190), color(50, 255, 50), color(100, 255, 100), 1.0f, 150.0f, 2.0f, color(40, 200, 40), 160.0f, 0.015f));
  moods.put("ANXIOUS", new Atmosphere(color(30, 5, 0), color(220, 150, 150), color(255, 20, 20), color(150, 50, 0), 4.0f, 300.0f, 1.5f, color(200, 20, 20), 220.0f, 0.025f));
}

void generateNebula(color c, float maxAlpha, float speed) {
  timeZ += speed;
  nebulaCanvas.beginDraw();
  nebulaCanvas.loadPixels();
  float r = red(c); float g = green(c); float b = blue(c);
  for (int x = 0; x < nebulaCanvas.width; x++) {
    for (int y = 0; y < nebulaCanvas.height; y++) {
      float n1 = noise(x * noiseScale, y * noiseScale, timeZ);
      float n2 = noise(x * noiseScale * 2.5f + 100, y * noiseScale * 2.5f + 100, timeZ * 1.5f);
      float finalNoise = pow(lerp(n1, n2, 0.4f), 3.0f);
      float alphaVal = constrain(map(finalNoise, 0, 0.8f, 0, maxAlpha), 0, maxAlpha);
      nebulaCanvas.pixels[x + y * nebulaCanvas.width] = color(r, g, b, alphaVal);
    }
  }
  nebulaCanvas.updatePixels();
  nebulaCanvas.endDraw();
}

void drawGUI(float smoothT) {
  fill(255, 150); textSize(14);
  text("Segmento " + (currentSegmentIndex+1) + "/" + playlist.size(), 20, height - 30);
}
