// serial_lfr_with_follow.ino
// Combined: original LFR (idle until serial triggers timed runs) + follow-mode live control
// Accepts both text commands (newline-terminated) and single-byte motor commands
// Sends ACK lines like: "ACK: F"

// ===================== LFR pins & config (unchanged) =====================
#define IR_LEFT  A1
#define IR_RIGHT A2

const int ENA = 5;
const int IN1 = 2;
const int IN2 = 3;

const int ENB = 6;
const int IN3 = 4;
const int IN4 = 7;

// ---- Behavior config (same as your working code) ----
int baseSpeed = 110;
int turnSpeed = 90;
int searchSpeed = 160;
int threshold = 500;
bool invertSensors = false;

// ---- STOP AFTER configured time (optional safety) ----
unsigned long startTime;
unsigned long stopAfter = 100000;   // 100 seconds
bool stopped = false;

int lastError = 1;

// ---- Execution control (Serial-driven) ----
bool executingCommand = false;
unsigned long execStartMillis = 0;
unsigned long execRunMs = 0;

// durations in ms for 1..3 (updated per request: 20s, 25s, 15s)
const unsigned long runMsForIndex[4] = {0, 20000UL, 25000UL, 15000UL};

// serial buffer
String serialBuffer = "";

// IDLE mode: robot stays stopped until a command arrives
bool idleMode = true;

// Follow mode: when true, single-byte commands F/B/L/R/S immediately control motors
bool followMode = false;

// =============== helper functions (unchanged semantics) ===============
bool sensorOnLine(int raw) {
  if (!invertSensors) return raw < threshold;
  else return raw > threshold;
}

void setMotorA(int speed, bool forwardDirection) {
  if (speed <= 0) {
    digitalWrite(IN1, LOW);
    digitalWrite(IN2, LOW);
    analogWrite(ENA, 0);
    return;
  }
  analogWrite(ENA, speed);
  digitalWrite(IN1, forwardDirection ? HIGH : LOW);
  digitalWrite(IN2, forwardDirection ? LOW : HIGH);
}

void setMotorB(int speed, bool forwardDirection) {
  if (speed <= 0) {
    digitalWrite(IN3, LOW);
    digitalWrite(IN4, LOW);
    analogWrite(ENB, 0);
    return;
  }
  analogWrite(ENB, speed);
  digitalWrite(IN3, forwardDirection ? HIGH : LOW);
  digitalWrite(IN4, forwardDirection ? LOW : HIGH);
}

void forward(int speed) {
  setMotorA(speed, true);
  setMotorB(speed, true);
}

void stopMotors() {
  setMotorA(0, true);
  setMotorB(0, true);
}

void turnLeft() {
  setMotorA(turnSpeed, false);
  setMotorB(turnSpeed, true);
}

void turnRight() {
  setMotorA(turnSpeed, true);
  setMotorB(turnSpeed, false);
}

void softTurnLeft(int speed) {
  setMotorA(speed/2, true);
  setMotorB(speed, true);
}

void softTurnRight(int speed) {
  setMotorA(speed, true);
  setMotorB(speed/2, true);
}

// ================= Serial command handling =================
void startExecutionForIndex(int idx){
  if(idx < 1 || idx > 3) return;
  if(executingCommand){
    Serial.println("Already executing — ignoring new command.");
    return;
  }
  // entering LFR timed run: stop follow mode if it was on
  followMode = false;
  executingCommand = true;
  idleMode = false;
  execStartMillis = millis();
  execRunMs = runMsForIndex[idx];
  Serial.print("Started serial-run for index ");
  Serial.print(idx);
  Serial.print(" for ");
  Serial.print(execRunMs/1000);
  Serial.println(" s");
}

void processSerialLine(String s){
  s.trim();
  s.toUpperCase();
  if(s.length() == 0) return;

  if(s.equals("1") || s.equals("MILK") || s.equals("GO TO MILK") || s.equals("GOTOMILK")){
    startExecutionForIndex(1);
    return;
  }
  if(s.equals("2") || s.equals("BREAD") || s.equals("GO TO BREAD") || s.equals("GOTOBREAD")){
    startExecutionForIndex(2);
    return;
  }
  if(s.equals("3") || s.equals("PEN") || s.equals("GO TO PEN") || s.equals("GOTOPEN")){
    startExecutionForIndex(3);
    return;
  }
  if(s.equals("CANCEL")){
    // stop early
    if(executingCommand){
      stopMotors();
      executingCommand = false;
      idleMode = true;
      Serial.println("Execution cancelled by serial. Back to idle.");
    } else {
      Serial.println("No active execution to cancel.");
    }
    return;
  }
  if(s.equals("FOLLOW") || s.equals("FOLLOW ME") || s.equals("START FOLLOW")){
    // Activate follow-mode: Arduino will respond to single-byte motor commands
    followMode = true;
    executingCommand = false;
    idleMode = false;
    Serial.println("Follow mode enabled on Arduino.");
    return;
  }
  if(s.equals("STOP FOLLOW") || s.equals("STOPFOLLOW") || s.equals("END FOLLOW")){
    followMode = false;
    stopMotors();
    idleMode = true;
    Serial.println("Follow mode disabled on Arduino. Back to idle.");
    return;
  }

  Serial.print("Unknown cmd (line): ");
  Serial.println(s);
}

// Handle single-byte motor commands (F,B,L,R,S) and also numeric '1','2','3'
void handleSingleByteCommand(char c) {
  if(c == '\n' || c == '\r') return;
  // numeric quick triggers (start timed runs)
  if(c == '1' || c == '2' || c == '3'){
    int idx = c - '0';
    startExecutionForIndex(idx);
    Serial.print("ACK: ");
    Serial.println(c);
    return;
  }

  // Follow-mode motor commands (immediate)
  if(c == 'F' || c == 'B' || c == 'L' || c == 'R' || c == 'S'){
    // entering immediate control; disable timed LFR
    followMode = true;
    executingCommand = false;
    idleMode = false;
    // Execute a single action (no timers here; cmd remains until new cmd)
    if(c == 'F') forward(baseSpeed);
    else if(c == 'B') {
      // go backward by inverting directions
      setMotorA(baseSpeed, false);
      setMotorB(baseSpeed, false);
    }
    else if(c == 'L') {
      turnLeft();
    }
    else if(c == 'R') {
      turnRight();
    }
    else if(c == 'S') {
      stopMotors();
    }
    Serial.print("ACK: ");
    Serial.println(c);
    return;
  }

  // If other ascii text bytes arrive, accumulate into buffer for line processing
  if(c >= 32 && c <= 126) {
    serialBuffer += c;
  }
}

// ================== Setup & Loop ==================
void setup(){
  pinMode(ENA, OUTPUT);
  pinMode(ENB, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  Serial.begin(115200);
  stopMotors();

  delay(200);
  startTime = millis();
  Serial.println("Serial-Fallback LFR + Follow ready.");
  Serial.println("Robot is IDLE. Send 'MILK'/'BREAD'/'PEN' or '1'/'2'/'3' in Serial to trigger runs.");
  Serial.println("Type 'CANCEL' to stop an ongoing run. Send 'FOLLOW' to enable follow-mode (F/B/L/R/S).");
}

void loop(){
  // Serial input non-blocking
  while(Serial.available()){
    char c = Serial.read();
    // If it's a newline, process any buffered line
    if(c == '\n' || c == '\r'){
      if(serialBuffer.length() > 0){
        processSerialLine(serialBuffer);
        serialBuffer = "";
      }
      // also ignore extra newline
    } else {
      // immediate single-byte commands or accumulation
      // If it's a printable char and we want to allow single-byte command handling, handle it
      // handleSingleByteCommand will also append printable characters if not recognized single bytes
      handleSingleByteCommand(c);
    }
  }

  // safety stop after configured time
  if(!stopped && millis() - startTime >= stopAfter){
    stopped = true;
    stopMotors();
    Serial.println("Stopped after configured timeout.");
  }
  if(stopped) return;

  // If idle, don't run LFR; just wait for commands.
  if(idleMode){
    // motors already stopped; nothing else to do
    delay(50);
    return;
  }

  // If followMode is active, we expect live single-byte commands from the Pi/qrFollower.
  // Do NOT run LFR while followMode is enabled.
  if(followMode){
    // just idle here; motor actions are done when single-byte commands arrive.
    delay(20);
    return;
  }

  // If executing timed command, run LFR step (exact original behavior)
  if(executingCommand){
    int rawLeft  = analogRead(IR_LEFT);
    int rawRight = analogRead(IR_RIGHT);

    bool leftOnLine  = sensorOnLine(rawLeft);
    bool rightOnLine = sensorOnLine(rawRight);

    if (leftOnLine && rightOnLine) {
      forward(baseSpeed);
    } 
    else if (leftOnLine && !rightOnLine) {
      turnLeft();
      lastError = -1;
    } 
    else if (!leftOnLine && rightOnLine) {
      turnRight();
      lastError = +1;
    } 
    else {
      // LOST — search in last direction
      if (lastError <= 0)
        softTurnLeft(searchSpeed);
      else
        softTurnRight(searchSpeed);
    }

    // If executing timed command, check timeout and stop when done
    if(millis() - execStartMillis >= execRunMs){
      stopMotors();
      executingCommand = false;
      idleMode = true;
      Serial.println("Timed run finished; now idle and listening for next command.");
    }

    delay(20);
    return;
  }

  // fallback: if we are not executing and not in followMode and not idleMode, ensure motors are stopped
  stopMotors();
  delay(20);
}