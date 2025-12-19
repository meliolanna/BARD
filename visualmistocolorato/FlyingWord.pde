class FlyingWord {
  String text; 
  PVector target, pos, vel, acc; 
  int sentenceId; 
  boolean active = false; 
  boolean locked = false;
  float angle; 
  float currentGlow = 0; 
  float targetGlow = 0; 
  float colorVariation;
  
  
  FlyingWord(String text, float targetX, float targetY, int sentenceId) {
    this.text = text; 
    this.target = new PVector(targetX, targetY); 
    this.sentenceId = sentenceId; 
    this.colorVariation = random(0.0f, 0.4f); 
    
    int side = floor(random(4)); 
    float dist = 300;
    
    if (side == 0) {
      pos = new PVector(random(width), -dist); 
    } 
    else if (side == 1) {
      pos = new PVector(width + dist, random(height));
    }
    else if (side == 2) {
      pos = new PVector(random(width), height + dist); 
    }
    else {
      pos = new PVector(-dist, random(height));
    }
    
    vel = new PVector(0,0); acc = new PVector(0,0); angle = random(-0.5f, 0.5f);
  }
  
  
  void update() {
    currentGlow = lerp(currentGlow, targetGlow, 0.1f); 
    if (locked) {
      return;
    }
    
    PVector desired = PVector.sub(target, pos); 
    float d = desired.mag();
    if (d < 1) { 
      pos = target.copy(); 
      angle = 0; 
      locked = true; 
      return; 
     }
     
    float speed = flightSpeed; 
    if (d < 150) {
      speed = map(d, 0, 150, 0.5f, flightSpeed);
    }
    
    desired.setMag(speed); 
    PVector steer = PVector.sub(desired, vel); 
    steer.limit(0.25f);
    acc.add(steer); 
    vel.add(acc); 
    pos.add(vel); 
    acc.mult(0); 
    angle = lerp(angle, 0, 0.08f);
  }
  
  void displayBase(color cBase, color cAccent) {
    textSize(fontSize);
    pushMatrix(); 
    translate(pos.x, pos.y); 
    rotate(angle); 
    color finalColor = lerpColor(cBase, cAccent, colorVariation); 
    fill(finalColor); 
    text(text, 0, 0); 
    popMatrix();
  }
  
  void displayGlowingOnly(color cGlow) {
    textSize(fontSize);
    pushMatrix(); 
    translate(pos.x, pos.y);     
    float intensity = currentGlow / 255.0f; 
    float pulse = 1.0f + 0.15f * sin(millis() / 250.0f); 
    fill(red(cGlow), green(cGlow), blue(cGlow), 40.0f * intensity * pulse); 
    for(int i=-2; i<=2; i+=2) { 
      text(text, i, 0); 
      text(text, 0, i); 
    }
    fill(red(cGlow), green(cGlow), blue(cGlow), 100.0f * intensity); 
    text(text, 0, 0); 
    fill(255, 255, 255, 150.0f * intensity); 
    text(text, 0, 0); 
    popMatrix();
  }
}
