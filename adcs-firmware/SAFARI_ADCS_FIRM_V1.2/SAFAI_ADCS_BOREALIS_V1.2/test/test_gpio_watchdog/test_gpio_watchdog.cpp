// test_gpio_watchdog.cpp
// Verifies the Watchdog CLK output pin (GPIO19).
// Note: I2C0 bus scan (GPIO4/5) is intentionally excluded — the Mbed I2C driver
// blocks indefinitely on Wire.endTransmission() when no device responds (no timeout),
// which would hang the test for 20+ minutes. CLK GPIO tests are sufficient here.

#include <Arduino.h>
#include <unity.h>
#include "config.h"
#include "watchdog.h"    // WD_CLK_HALF_US

// ── Tests ─────────────────────────────────────────────────────────────────────

// CLK output pin can be driven HIGH and read back, then LOW
void test_clk_toggle() {
    pinMode(PIN_WD_CLK, OUTPUT);

    digitalWrite(PIN_WD_CLK, HIGH);
    TEST_ASSERT_EQUAL(HIGH, digitalRead(PIN_WD_CLK));

    digitalWrite(PIN_WD_CLK, LOW);
    TEST_ASSERT_EQUAL(LOW, digitalRead(PIN_WD_CLK));
}

// One full CLK pulse (mirrors WatchdogComm::tickClock)
void test_clk_pulse() {
    pinMode(PIN_WD_CLK, OUTPUT);
    digitalWrite(PIN_WD_CLK, LOW);

    digitalWrite(PIN_WD_CLK, HIGH);
    delayMicroseconds(WD_CLK_HALF_US);
    TEST_ASSERT_EQUAL(HIGH, digitalRead(PIN_WD_CLK));

    digitalWrite(PIN_WD_CLK, LOW);
    delayMicroseconds(WD_CLK_HALF_US);
    TEST_ASSERT_EQUAL(LOW, digitalRead(PIN_WD_CLK));
}

// ── Unity entry point ─────────────────────────────────────────────────────────

void setUp()    {}
void tearDown() {}

void setup() {
    delay(2000);
    Serial.begin(115200);
    UNITY_BEGIN();
    RUN_TEST(test_clk_toggle);
    RUN_TEST(test_clk_pulse);
    UNITY_END();
}

void loop() {}
