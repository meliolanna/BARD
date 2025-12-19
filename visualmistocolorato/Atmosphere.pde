class Atmosphere {
  color bgColor, textColor, glowColor, particleColor;
  float particleSpeedY, particleCount, chaos;
  
  color nebulaColor;
  float nebulaAlphaMax, nebulaSpeed;
  
  Atmosphere(color bg, color txt, color gl, color pt, float spd, float cnt, float ch,
             color nebCol, float nebAlpha, float nebSpd) {
    bgColor=bg; 
    textColor=txt; 
    glowColor=gl; 
    particleColor=pt; 
    particleSpeedY=spd; 
    particleCount=cnt; 
    chaos=ch;
    nebulaColor = nebCol; 
    nebulaAlphaMax = nebAlpha; 
    nebulaSpeed = nebSpd;
  }
  
  Atmosphere copy() {
    return new Atmosphere(bgColor, textColor, glowColor, particleColor, particleSpeedY, particleCount, chaos,
                          nebulaColor, nebulaAlphaMax, nebulaSpeed);
  }
}
