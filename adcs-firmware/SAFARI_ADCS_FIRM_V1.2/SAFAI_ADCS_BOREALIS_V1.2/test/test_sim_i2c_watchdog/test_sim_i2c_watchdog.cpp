// test_sim_i2c_watchdog.cpp
// Validates the I2C0 SDA line (GPIO4) and CLK output (GPIO19) wired to the
// external Watchdog by injecting known logic levels via bare wires.
//
// HARDWARE REQUIRED
// -----------------
//   Wire A (SDA test):
//       Pico pin 20 (GP15 / stimulus)  ────wire────  Pico pin 6 (GP4 / I2C0 SDA)
//
//   Wire B (CLK readback — optional, independent of wire A):
//       Pico pin 25 (GP19 / WD_CLK)   ────wire────  Pico pin 21 (GP16 / monitor)
//
// CRITICAL: Wire.begin() (I2C0) is NEVER called in this file.
// The Mbed I2C driver on I2C0 blocks indefinitely on Wire.endTransmission()
// when no device responds — this would hang the board for 20+ minutes.
// GPIO4 is tested as a plain digital input only.
//
// What this tests
// ---------------
//   Wire A: confirms GP4 (SDA) is electrically intact and responds to an
//           external driver — same role the Watchdog chip plays on the bus.
//   Wire B: confirms the CLK pulse exits pin 25 on the physical header
//           (tests actual pin drive, not just internal register readback).

#include <Arduino.h>
#include <unity.h>
#include "config.h"
#include "watchdog.h"   // WD_CLK_HALF_US

static constexpr uint8_t PIN_STIM    = 15;   // GP15 — Pico pin 20 (SDA stimulus)
static constexpr uint8_t PIN_MONITOR = 16;   // GP16 — Pico pin 21 (CLK readback)

// ── SDA line tests (Wire A) ───────────────────────────────────────────────────

// Connectivity check: HIGH/LOW transitions on stimulus must appear on SDA.
void test_sim_sda_wire_connected() {
    pinMode(PIN_STIM,   OUTPUT);
    pinMode(PIN_WD_SDA, INPUT);

    digitalWrite(PIN_STIM, HIGH);
    delayMicroseconds(100);
    int rd_high = digitalRead(PIN_WD_SDA);

    digitalWrite(PIN_STIM, LOW);
    delayMicroseconds(100);
    int rd_low = digitalRead(PIN_WD_SDA);

    char msg[80];
    snprintf(msg, sizeof(msg),
        "Wire absent? HIGH=%d LOW=%d (need 1,0) — bridge pin20 to pin6", rd_high, rd_low);
    TEST_ASSERT_EQUAL_MESSAGE(HIGH, rd_high, "WD SDA HIGH: wire absent or GP15 not driving");
    TEST_ASSERT_EQUAL_MESSAGE(LOW,  rd_low,  msg);
}

// Stimulus LOW → WD_SDA reads LOW (Watchdog pulling bus down simulation)
void test_sim_sda_driven_low() {
    pinMode(PIN_STIM,   OUTPUT);
    pinMode(PIN_WD_SDA, INPUT);
    digitalWrite(PIN_STIM, LOW);
    delayMicroseconds(100);
    TEST_ASSERT_EQUAL_MESSAGE(LOW, digitalRead(PIN_WD_SDA),
        "WD SDA driven LOW: pin did not follow stimulus");
}

// Stimulus HIGH → WD_SDA reads HIGH (bus release)
void test_sim_sda_driven_high() {
    pinMode(PIN_STIM,   OUTPUT);
    pinMode(PIN_WD_SDA, INPUT);
    digitalWrite(PIN_STIM, HIGH);
    delayMicroseconds(100);
    TEST_ASSERT_EQUAL_MESSAGE(HIGH, digitalRead(PIN_WD_SDA),
        "WD SDA driven HIGH: pin did not follow stimulus");
}

// ── CLK output tests (Wire B — requires second wire GP19→GP16) ───────────────

// CLK HIGH pulse: GP16 must read HIGH while GP19 is HIGH
void test_sim_clk_external_high() {
    pinMode(PIN_WD_CLK,  OUTPUT);
    pinMode(PIN_MONITOR, INPUT);

    digitalWrite(PIN_WD_CLK, HIGH);
    delayMicroseconds(WD_CLK_HALF_US);

    char msg[80];
    int rd = digitalRead(PIN_MONITOR);
    snprintf(msg, sizeof(msg),
        "CLK wire absent? GP19 HIGH but GP16=%d — bridge pin25 to pin21", rd);
    TEST_ASSERT_EQUAL_MESSAGE(HIGH, rd, msg);

    digitalWrite(PIN_WD_CLK, LOW);
}

// Full CLK pulse seen on monitor pin: HIGH half then LOW half
void test_sim_clk_pulse_external() {
    pinMode(PIN_WD_CLK,  OUTPUT);
    pinMode(PIN_MONITOR, INPUT);

    digitalWrite(PIN_WD_CLK, LOW);
    delayMicroseconds(WD_CLK_HALF_US);

    digitalWrite(PIN_WD_CLK, HIGH);
    delayMicroseconds(WD_CLK_HALF_US);
    TEST_ASSERT_EQUAL_MESSAGE(HIGH, digitalRead(PIN_MONITOR),
        "CLK pulse HIGH half not seen on GP16");

    digitalWrite(PIN_WD_CLK, LOW);
    delayMicroseconds(WD_CLK_HALF_US);
    TEST_ASSERT_EQUAL_MESSAGE(LOW, digitalRead(PIN_MONITOR),
        "CLK pulse LOW half not seen on GP16");
}

// ── Unity entry point ─────────────────────────────────────────────────────────

void setUp() {
    pinMode(PIN_STIM, INPUT);    // release SDA stimulus
    delayMicroseconds(100);
}

void tearDown() {}

void setup() {
    delay(2000);
    Serial.begin(115200);
    Serial.println("--- test_sim_i2c_watchdog ---");
    Serial.println("Wire A: pin20 (GP15) -> pin6  (GP4 / WD SDA)");
    Serial.println("Wire B: pin25 (GP19) -> pin21 (GP16 / CLK monitor)  [optional]");
    Serial.println("Run SDA tests with wire A only; CLK tests need wire B.");
    UNITY_BEGIN();
    // SDA line tests (wire A)
    RUN_TEST(test_sim_sda_wire_connected);
    RUN_TEST(test_sim_sda_driven_low);
    RUN_TEST(test_sim_sda_driven_high);
    // CLK external readback tests (wire B)
    RUN_TEST(test_sim_clk_external_high);
    RUN_TEST(test_sim_clk_pulse_external);
    UNITY_END();
}

void loop() {}
