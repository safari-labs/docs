// test_sim_i2c_imu.cpp
// Validates the I2C1 SDA line (GPIO6) wired to the ICM-20948 IMU
// by injecting a known logic level from a free GPIO via a bare wire.
//
// HARDWARE REQUIRED
// -----------------
//   One wire:
//       Pico pin 20 (GP15 / stimulus)  ────wire────  Pico pin 9 (GP6 / I2C1 SDA)
//
// Wire.begin() is NOT called — GPIO6 is operated as a plain digital input.
// This avoids any I2C peripheral state and tests the physical SDA line only.
// SCL (GPIO7 / Pico pin 10) can be tested the same way with a second wire to
// any free output pin if needed.
//
// What this tests
// ---------------
//   Confirms that an external agent (here, GP15) can drive the SDA line HIGH
//   and LOW, which is exactly what the ICM-20948 does when responding.
//   Passing → SDA pin is electrically intact and reachable from the header.

#include <Arduino.h>
#include <unity.h>
#include "config.h"

static constexpr uint8_t PIN_STIM = 15;   // GP15 — Pico pin 20

// ── Tests ─────────────────────────────────────────────────────────────────────

// Connectivity check: stimulus HIGH then LOW must produce opposite levels on SDA.
// If the wire is absent, SDA floats and both reads may be identical.
void test_sim_sda_wire_connected() {
    pinMode(PIN_STIM,    OUTPUT);
    pinMode(PIN_IMU_SDA, INPUT);

    digitalWrite(PIN_STIM, HIGH);
    delayMicroseconds(100);
    int rd_high = digitalRead(PIN_IMU_SDA);

    digitalWrite(PIN_STIM, LOW);
    delayMicroseconds(100);
    int rd_low = digitalRead(PIN_IMU_SDA);

    char msg[80];
    snprintf(msg, sizeof(msg),
        "Wire absent? HIGH=%d LOW=%d (need 1,0) — bridge pin20 to pin9", rd_high, rd_low);
    TEST_ASSERT_EQUAL_MESSAGE(HIGH, rd_high, "SDA HIGH: wire absent or GP15 not driving");
    TEST_ASSERT_EQUAL_MESSAGE(LOW,  rd_low,  msg);
}

// Stimulus LOW → SDA reads LOW (simulates sensor or master pulling SDA down)
void test_sim_sda_driven_low() {
    pinMode(PIN_STIM,    OUTPUT);
    pinMode(PIN_IMU_SDA, INPUT);
    digitalWrite(PIN_STIM, LOW);
    delayMicroseconds(100);
    TEST_ASSERT_EQUAL_MESSAGE(LOW, digitalRead(PIN_IMU_SDA),
        "SDA driven LOW: pin did not follow stimulus");
}

// Stimulus HIGH → SDA reads HIGH (simulates bus release)
void test_sim_sda_driven_high() {
    pinMode(PIN_STIM,    OUTPUT);
    pinMode(PIN_IMU_SDA, INPUT);
    digitalWrite(PIN_STIM, HIGH);
    delayMicroseconds(100);
    TEST_ASSERT_EQUAL_MESSAGE(HIGH, digitalRead(PIN_IMU_SDA),
        "SDA driven HIGH: pin did not follow stimulus");
}

// Toggle: alternate 5 times, SDA must follow each transition
void test_sim_sda_toggle() {
    pinMode(PIN_STIM,    OUTPUT);
    pinMode(PIN_IMU_SDA, INPUT);

    for (uint8_t i = 0; i < 5; i++) {
        int level = (i % 2 == 0) ? HIGH : LOW;
        digitalWrite(PIN_STIM, level);
        delayMicroseconds(50);
        char msg[48];
        snprintf(msg, sizeof(msg), "toggle[%u]: expected %d", i, level);
        TEST_ASSERT_EQUAL_MESSAGE(level, digitalRead(PIN_IMU_SDA), msg);
    }
}

// ── Unity entry point ─────────────────────────────────────────────────────────

void setUp() {
    pinMode(PIN_STIM, INPUT);   // release stimulus between tests
    delayMicroseconds(100);
}

void tearDown() {}

void setup() {
    delay(2000);
    Serial.begin(115200);
    Serial.println("--- test_sim_i2c_imu ---");
    Serial.println("REQUIRES: wire Pico pin20 (GP15) -> pin9 (GP6/IMU SDA)");
    UNITY_BEGIN();
    RUN_TEST(test_sim_sda_wire_connected);   // connectivity first
    RUN_TEST(test_sim_sda_driven_low);
    RUN_TEST(test_sim_sda_driven_high);
    RUN_TEST(test_sim_sda_toggle);
    UNITY_END();
}

void loop() {}
