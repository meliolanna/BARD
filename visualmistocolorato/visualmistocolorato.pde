import java.util.HashMap;
import oscP5.*;
import netP5.*;

String fullText = "C'era una volta, in una terra lontana e silenziosa, un piccolo villaggio dimenticato dal tempo. " +
                  "Le case erano fatte di pietra antica e i tetti coperti di muschio smeraldo. " +
                  "Nessuno ricordava quando l'ultimo viaggiatore fosse passato di lì, ma il vento raccontava storie " +
                  "che solo gli alberi sapevano ascoltare. Una notte, una luce misteriosa apparve all'orizzonte, " +
                  "pulsando come un cuore fatto di stelle. Gli abitanti si svegliarono, richiamati da un canto dolce " +
                  "e incomprensibile.";

// Testo
int fontSize = 40;
float leading = fontSize*1.4;
float margin = 200;

// Tempi
int wordSpawnRate = 100;
int readingPause = 3500; 
float flightSpeed = 6;

// Stati
final int STATE_WRITING = 0;
final int STATE_WAITING_ARRIVAL = 1;
final int STATE_READING = 2;

int currentState = STATE_WRITING;
ArrayList<FlyingWord> wordsObjects;
int currentWordIndex = 0;
ArrayList<ArrayList<FlyingWord>> pages; // Lista di Pagine 
int currentPageIndex = 0;

int lastTime = 0;
int pauseStartTime = 0;

ArrayList<BgParticle> bgParticles;
HashMap<String, Atmosphere> moods;

PGraphics nebulaCanvas; // Tela off-screen per disegnare il fumo
float noiseScale = 0.003f; // Quanto "zoomato" è il noise
float timeZ = 0; // Tempo per animare il noise

Atmosphere startMood;   
Atmosphere targetMood;  
Atmosphere currentVals; 

float transitionDuration = 5000; 
float transitionStartTime = -9999; 

PFont myFont;
OscP5 oscP5;


// ---------- setup ----------
void setup() {
  fullScreen(P2D); 
  oscP5 = new OscP5(this, 5005);
  
  myFont = createFont("Georgia", fontSize); 
  textFont(myFont);
  textSize(fontSize);
  textAlign(LEFT, CENTER);
  
  wordsObjects = new ArrayList<FlyingWord>();
  bgParticles = new ArrayList<BgParticle>();
  
  // La creiamo 4 volte più piccola dello schermo per velocità e per l'effetto blur naturale quando viene ingrandita
  nebulaCanvas = createGraphics(width/4, height/4, P2D);
  
  setupMoods();
  
  setMood("CALM"); 
  currentVals = targetMood.copy();
  startMood = targetMood.copy();
  
  calculatePages();
  loadPage(0);
    
  // Inizializziamo particelle
  for(int i=0; i<currentVals.particleCount; i++) {
    bgParticles.add(new BgParticle());
  }
  
  lastTime = millis();
}


// ---------- draw ----------
void draw() {
 
  float elapsed = millis() - transitionStartTime; //calcolo trasnizione
  float t = constrain(elapsed / transitionDuration, 0, 1);
  float smoothT = t * t * (3 - 2 * t); 
  
  updateCurrentAtmosphere(smoothT);

  // Gestione numero particelle
  int targetCount = (int)lerp(startMood.particleCount, targetMood.particleCount, smoothT);
  if (bgParticles.size() < targetCount) {
    bgParticles.add(new BgParticle());
  }
  else if (bgParticles.size() > targetCount) {
    bgParticles.remove(0);
  }

  /* sfondo */
  background(currentVals.bgColor);
  generateNebula(currentVals.nebulaColor, currentVals.nebulaAlphaMax, currentVals.nebulaSpeed);
  blendMode(ADD);  
  image(nebulaCanvas, 0, 0, width, height); // Disegniamo la tela piccola stirandola a tutto schermo. Questo crea la sfumatura.
  blendMode(BLEND);
  
  /* particelle */
  for(BgParticle p : bgParticles){
    p.update(currentVals.particleSpeedY, currentVals.chaos);
    p.display(currentVals.particleColor);
  }
  
  updateWordLogic();
  drawWords();
  drawGUI(smoothT);
 }
 



/* UN SAAAAAAAAAAAAAAAAACCO DI FUNZIONIIIIIIIIIIIIIIIII */

void updateWordLogic() {
  int now = millis();
  
  if (currentState == STATE_WRITING) {
    if (now - lastTime > wordSpawnRate && currentWordIndex < wordsObjects.size()) {
      FlyingWord w = wordsObjects.get(currentWordIndex); 
      w.active = true; 
      lastTime = now;
      
      char lastChar = w.text.charAt(w.text.length() - 1);
      
      // Se troviamo punteggiatura O se siamo all'ultima parola della pagina
      boolean isLastWord = (currentWordIndex == wordsObjects.size() - 1);
      
      if (lastChar == '.' || lastChar == '!' || lastChar == '?' || isLastWord) {
        currentState = STATE_WAITING_ARRIVAL;
      } else {
        currentWordIndex++;
      }
    }
  }
  else if (currentState == STATE_WAITING_ARRIVAL) {
    FlyingWord lastWord = wordsObjects.get(currentWordIndex);
    if (lastWord.locked) { 
      triggerSentenceGlow(lastWord.sentenceId); 
      pauseStartTime = now; 
      currentState = STATE_READING; 
    }
  }
  else if (currentState == STATE_READING) {
    if (now - pauseStartTime > readingPause) { 
      dimSentenceGlow(wordsObjects.get(currentWordIndex).sentenceId); 
      
      // Abbiamo finito di leggere. C'è un'altra parola in QUESTA pagina?
      if (currentWordIndex < wordsObjects.size() - 1) {
        // SI: Andiamo avanti nella stessa pagina
        currentWordIndex++; 
        currentState = STATE_WRITING; 
        lastTime = now;
      } else {
        nextPage();
      }
    }
  }
}


// funzioni per la paginazione
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
    
    if (y > height - margin) {
      pages.add(currentPageList);
      currentPageList = new ArrayList<FlyingWord>();
      x = margin;
      y = margin; 
    }
    
    char lastChar = str.charAt(str.length() - 1);
    currentPageList.add(new FlyingWord(str, x, y, currentSentenceId));
    
    if (lastChar == '.' || lastChar == '!' || lastChar == '?') {
      currentSentenceId++;
    }
    x += w;
  }
  
  if (currentPageList.size() > 0) {
    pages.add(currentPageList);
  }
}


void loadPage(int index) {
  if (index >= 0 && index < pages.size()) {
    currentPageIndex = index;
    // Copiamo la pagina salvata dentro wordsObjects che è quello che viene disegnato
    wordsObjects = pages.get(currentPageIndex);
    
    currentWordIndex = 0;
    currentState = STATE_WRITING;
    lastTime = millis();
    
    println(">>> Caricata Pagina " + (index + 1) + " di " + pages.size());
  }
}

void nextPage() {
  if (currentPageIndex + 1 < pages.size()) {
    loadPage(currentPageIndex + 1);
  } else {
    // Finito tutto il testo! Ricominciamo da capo?
    println("Storia finita. Ricomincio.");
    loadPage(0);
    // Oppure potresti mettere un setMood("FINALE");
  }
}
  
 void drawWords() {
  blendMode(BLEND); 
  for (FlyingWord w : wordsObjects) {
    if (w.active) { w.update(); w.displayBase(currentVals.textColor, currentVals.glowColor); }
  }
  blendMode(ADD);
  for (FlyingWord w : wordsObjects) {
    if (w.active && w.currentGlow > 1) { w.displayGlowingOnly(currentVals.glowColor); }
  }
  blendMode(BLEND);
}
  


// funzione oer cambiare le atmosfere

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
    println(">>> Mood transition to: " + name);
  }
}

void setupMoods() {
  moods = new HashMap<String, Atmosphere>();
  
  // Parametri Atmosphere AGGIORNATI: 
  // (BgColor, TextColor, GlowColor, ParticleColor, SpeedY, PartCount, Chaos, 
  //  NEBULA_COLOR, NEBULA_MAX_ALPHA (0-255), NEBULA_SPEED)
  
  // 1. ENERGETIC: Nebulosa arancione/rossa intensa e veloce
  moods.put("ENERGETIC", new Atmosphere(
    color(40, 10, 5), color(240, 220, 180), color(255, 160, 20), color(255, 100, 50), -3.0f, 250.0f, 5.0f,
    color(255, 80, 20), 200.0f, 0.03f 
  ));

  // 2. SOLO: Nebulosa quasi invisibile, grigio scuro, lentissima
  moods.put("SOLO", new Atmosphere(
    color(15, 15, 18), color(210, 210, 215), color(180, 180, 200), color(0,0,0,0), 0f, 0f, 0f,
    color(50, 50, 60), 60.0f, 0.002f
  ));

  // 3. CALM: Nebulosa blu/viola morbida, velocità media
  moods.put("CALM", new Atmosphere(
    color(20, 15, 35), color(170, 180, 210), color(100, 150, 255), color(150, 100, 200), -0.3f, 60.0f, 0.2f,
    color(80, 100, 220), 150.0f, 0.008f
  ));

  // 4. DEEP: Nebulosa blu scuro profondo, lenta
  moods.put("DEEP", new Atmosphere(
    color(2, 5, 15), color(110, 130, 150), color(0, 100, 200), color(0, 50, 100), 0.1f, 100.0f, 0.5f,
    color(0, 40, 120), 180.0f, 0.005f
  ));
  
  // 5. DISSONANT: Nebulosa verde acido tossico, velocità media
  moods.put("DISSONANT", new Atmosphere(
    color(15, 20, 18), color(190, 210, 190), color(50, 255, 50), color(100, 255, 100), 1.0f, 150.0f, 2.0f,
    color(40, 200, 40), 160.0f, 0.015f
  ));
  
  // 6. ANXIOUS: Nebulosa rosso sangue densa, veloce
  moods.put("ANXIOUS", new Atmosphere(
    color(30, 5, 0), color(220, 150, 150), color(255, 20, 20), color(150, 50, 0), 4.0f, 300.0f, 1.5f,
    color(200, 20, 20), 220.0f, 0.025f
  ));
}


// roba da togliere in futuro
void drawGUI(float smoothT) {
  fill(255, 150); textSize(14);
  text("Pagina " + (currentPageIndex+1) + "/" + pages.size() + " - Moods: 1-6", 20, height - 30);
  stroke(255, 50); noFill(); rect(20, height-50, 100, 5);
  noStroke(); fill(255, 100); rect(20, height-50, 100 * smoothT, 5);
}


// roba per lo sfondo che fa blup blop
void generateNebula(color c, float maxAlpha, float speed) {
  timeZ += speed; // Avanzamento nel tempo del noise
  
  nebulaCanvas.beginDraw();
  nebulaCanvas.loadPixels(); // Iniziamo a manipolare i pixel
  
  float r = red(c);
  float g = green(c);
  float b = blue(c);
  
  // Cicliamo su ogni pixel della tela piccola
  for (int x = 0; x < nebulaCanvas.width; x++) {
    for (int y = 0; y < nebulaCanvas.height; y++) {
      
      // Calcoliamo due strati di noise per avere dettagli grandi e piccoli
      // Strato 1: Grandi nuvole lente
      float n1 = noise(x * noiseScale, y * noiseScale, timeZ);
      // Strato 2: Dettagli più piccoli e veloci (spostati un po')
      float n2 = noise(x * noiseScale * 2.5f + 100, y * noiseScale * 2.5f + 100, timeZ * 1.5f);
      
      // Mixiamo i due noise (il secondo strato aggiunge dettagli)
      float finalNoise = lerp(n1, n2, 0.4f);
      
      // Usiamo pow() per aumentare il contrasto: rende le zone scure più scure e le chiare più definite
      finalNoise = pow(finalNoise, 3.0f); 

      // Mappiamo il noise sull'alpha (trasparenza)
      float alphaVal = map(finalNoise, 0, 0.8f, 0, maxAlpha);
      alphaVal = constrain(alphaVal, 0, maxAlpha);
      
      // Impostiamo il colore del pixel nella tela piccola
      int index = x + y * nebulaCanvas.width;
      // Usiamo un colore con l'alpha calcolato. Quando questo canvas verrà disegnato in ADD, creerà la luce.
      nebulaCanvas.pixels[index] = color(r, g, b, alphaVal);
    }
  }
  nebulaCanvas.updatePixels(); // Applichiamo le modifiche
  nebulaCanvas.endDraw();
}


// frasi che compaiono e cambiano glow etc

void triggerSentenceGlow(int sId) { 
  for (FlyingWord w : wordsObjects) {
    if (w.sentenceId == sId) {
      w.targetGlow = 255; 
    }
  }
}

void dimSentenceGlow(int sId) { 
  for (FlyingWord w : wordsObjects){ 
    if (w.sentenceId == sId){ 
      w.targetGlow = 0; 
    }
  }
}

// questa funzione forse non serve più
void calculateLayoutAndGroups() {
  String[] rawWords = split(fullText, ' '); 
  float x = margin; 
  float y = 0; 
  float maxWidth = width - (margin * 2); 
  float tempY = 0;
  int currentSentenceId = 0; 
  ArrayList<TempWord> tempLayout = new ArrayList<TempWord>();
  
  for (String str : rawWords) {
    float w = textWidth(str + " "); 
    
    if (x + w > margin + maxWidth) { 
      x = margin; 
      y += leading; 
    }
    
    char lastChar = str.charAt(str.length() - 1); 
    tempLayout.add(new TempWord(str, x, y, currentSentenceId));
    
    if (lastChar == '.' || lastChar == '!' || lastChar == '?') {
      currentSentenceId++; 
    }
    
    x += w; 
    tempY = y;
  }
  
  float totalHeight = tempY + leading; 
  float startY = (height - totalHeight) / 2;
  wordsObjects.clear(); 
  
  for (TempWord item : tempLayout) {
    wordsObjects.add(new FlyingWord(item.text, item.x, item.y + startY, item.sId));
  }
}


///* ------------------ COMANDI ------------------*/

void keyPressed() {
  if (key == '1') setMood("ENERGETIC");
  if (key == '2') setMood("SOLO");
  if (key == '3') setMood("CALM");
  if (key == '4') setMood("DEEP");
  if (key == '5') setMood("DISSONANT");
  if (key == '6') setMood("ANXIOUS");
}


void oscEvent(OscMessage msg) {
  // Esempio Python: client.send_message("/generate", [1, "C'era una volta..."])
  print(" Ricevuto qualcosa! ");
  print(" Pattern: " + msg.addrPattern());
  print(" | Typetag: " + msg.typetag());
  if(msg.checkTypetag("is")) {
    int moodVal = msg.get(0).intValue();
    String newStory = msg.get(1).stringValue();
    
    //println("OSC RICEVUTO -> Mood: " + moodVal + " | Storia: " + newStory);
    
    mapClassToMood(moodVal);
    updateStory(newStory);
    return;
  }

  // Caso solo Intero (Vecchio metodo, solo cambio colori)
  if(msg.checkTypetag("i")) {
    int moodVal = msg.get(0).intValue();
    mapClassToMood(moodVal);
    return;
  }
  if(msg.checkTypetag("f")) {
    int moodVal = (int)msg.get(0).floatValue();
    mapClassToMood(moodVal);
    return;
  }
}

void updateStory(String textReceived) {
  if (textReceived != null && textReceived.length() > 0) {
    fullText = textReceived; // Sostituisce il testo globale
    calculatePages();        // Ricalcola il layout e le pagine
    loadPage(0);             // Riparte dalla prima pagina
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
      default: println("Classe ignota: " + val); break;
    }
}
