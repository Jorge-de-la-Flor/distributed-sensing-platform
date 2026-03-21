/**
 * distributed-sensing-platform
 * Sensing Node Firmware — Arduino Uno R3
 *
 * Responsibilities:
 *   - Acquire distance measurements via HC-SR04 ultrasonic sensor
 *   - Detect motion via PIR sensor
 *   - Apply 1D Kalman filter for probabilistic noise reduction
 *   - Execute FSM-based state classification
 *   - Drive servo actuator and buzzer according to system state
 *   - Transmit structured telemetry to Pico W via UART (9600 baud)
 *
 * FSM States:
 *   LIBRE        — no motion, distance > 50 cm
 *   MONITOREANDO — motion detected, distance > 50 cm
 *   CERCA        — object within 20–50 cm
 *   PELIGRO      — object within 20 cm (alarm + actuator)
 *
 * Pins:
 *   TRIG  → 8   HC-SR04 trigger
 *   ECHO  → 7   HC-SR04 echo
 *   PIR   → 4   Passive infrared motion sensor
 *   SERVO → 3   PWM servo signal
 *   BUZZ  → 2   Active buzzer
 *   TX    → 1   UART to Pico W (via HW-221 logic level shifter)
 *
 * Serial output format (newline-terminated):
 *   <dist_raw>,<dist_filtered>,<pir>,<state>
 */

#include <Servo.h>

// ── Pin definitions ──────────────────────────────────────────────────────────
const int TRIG_PIN   = 8;
const int ECHO_PIN   = 7;
const int PIR_PIN    = 4;
const int SERVO_PIN  = 3;
const int BUZZER_PIN = 2;

// ── Kalman filter state ──────────────────────────────────────────────────────
float kf_Q = 0.1f;   // Process noise covariance
float kf_R = 1.0f;   // Measurement noise covariance
float kf_P = 1.0f;   // Estimation error covariance
float kf_X = 0.0f;   // State estimate

// ── FSM ──────────────────────────────────────────────────────────────────────
enum State { LIBRE, MONITOREANDO, CERCA, PELIGRO };
State currentState = LIBRE;
const char* stateLabels[] = { "LIBRE", "MONITOREANDO", "CERCA", "PELIGRO" };

Servo servo;

// ── Kalman filter update ─────────────────────────────────────────────────────
float kalmanUpdate(float measurement) {
  kf_P = kf_P + kf_Q;
  float K = kf_P / (kf_P + kf_R);
  kf_X = kf_X + K * (measurement - kf_X);
  kf_P = (1.0f - K) * kf_P;
  return kf_X;
}

// ── Ultrasonic distance measurement ─────────────────────────────────────────
float measureDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);
  if (duration == 0) return 999.0f;
  return duration * 0.034f / 2.0f;
}

// ── Setup ────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  pinMode(TRIG_PIN,   OUTPUT);
  pinMode(ECHO_PIN,   INPUT);
  pinMode(PIR_PIN,    INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  servo.attach(SERVO_PIN);
  servo.write(90);
}

// ── Main loop ────────────────────────────────────────────────────────────────
void loop() {
  static unsigned long lastTick = 0;
  if (millis() - lastTick < 500) return;
  lastTick = millis();

  bool     pir         = digitalRead(PIR_PIN);
  float    distRaw     = measureDistance();
  float    distFiltered = kalmanUpdate(distRaw);
  State    prevState   = currentState;

  // FSM transition logic
  if (!pir && distFiltered > 50.0f) {
    currentState = LIBRE;
    servo.write(90);
    digitalWrite(BUZZER_PIN, LOW);
  } else if (pir && distFiltered > 50.0f) {
    currentState = MONITOREANDO;
    servo.write(90);
    digitalWrite(BUZZER_PIN, LOW);
  } else if (distFiltered > 20.0f && distFiltered <= 50.0f) {
    currentState = CERCA;
    servo.write(45);
    digitalWrite(BUZZER_PIN, LOW);
  } else if (distFiltered <= 20.0f) {
    currentState = PELIGRO;
    servo.write(0);
    digitalWrite(BUZZER_PIN, HIGH);
  }

  // Transmit telemetry over UART
  Serial.print(distRaw,      2);  Serial.print(',');
  Serial.print(distFiltered, 2);  Serial.print(',');
  Serial.print(pir ? 1 : 0);     Serial.print(',');
  Serial.println(stateLabels[currentState]);
}
