class BgParticle {
  float x, y, size, alphaOffset, t;
  
  BgParticle() { 
    x = random(width); 
    y = random(height); 
    size = random(1.0f, 3.0f); 
    alphaOffset = random(50.0f, 150.0f); 
    t = random(1000.0f); 
  }
  
  void update(float currentSpeedY, float currentChaos) {
    y += currentSpeedY;
    
    if (currentChaos > 0.01f) { 
      x += random(-currentChaos, currentChaos); 
      y += random(-currentChaos, currentChaos); 
    }
    
    if (y < -10) {
      y = height + 10; 
    }
    if (y > height + 10) { 
      y = -10;
    }
    if (x < -10) {
      x = width + 10; 
    }
    if (x > width + 10) {
      x = -10;
    }
    
    t += 0.05f;
  }
  
  
  void display(color cPart) {
    float currentAlpha = alpha(cPart) * (0.6f + 0.4f * sin(t)); 
    fill(red(cPart), green(cPart), blue(cPart), min(currentAlpha, alphaOffset)); noStroke(); ellipse(x, y, size, size);
  }
}
