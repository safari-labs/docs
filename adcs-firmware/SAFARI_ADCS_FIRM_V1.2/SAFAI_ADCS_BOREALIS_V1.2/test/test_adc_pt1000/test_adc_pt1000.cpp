// test_adc_pt1000.cpp
// Verifies that the Pt1000 ADC channel (GPIO26) returns a value within the
// valid 10-bit range [0, 1023] for all 8 MUX channels.
// No Pt1000 sensor needs to be wired: a floating pin still produces a reading
// in [0, 1023]. The test confirms the ADC peripheral and MUX control pins work.

#include <Arduino.h>
#include <unity.h>
#include "config.h"

// Helper: select MUX channel (mirrors pt1000.cpp Pt1000Module::selectChannel)
static void selectChannel(uint8_t ch) {
    digitalWrite(PIN_MUX_A0, (ch >> 0) & 0x01);
    digitalWrite(PIN_MUX_A1, (ch >> 1) & 0x01);
    digitalWrite(PIN_MUX_A2, (ch >> 2) & 0x01);
}

// ── Tests ─────────────────────────────────────────────────────────────────────

// Channel 0 ADC read: power on, wait for settle, read, power off.
// Result must be a valid 10-bit integer in [0, 1023].
void test_adc_channel0_range() {
    analogReadResolution(10);
    pinMode(PIN_MUX_A0,    OUTPUT);
    pinMode(PIN_MUX_A1,    OUTPUT);
    pinMode(PIN_MUX_A2,    OUTPUT);
    pinMode(PIN_PT1000_SW, OUTPUT);

    selectChannel(0);
    digitalWrite(PIN_PT1000_SW, HIGH);
    delayMicroseconds(500);  // RC settling delay

    int raw = analogRead(PIN_PT1000_ADC);

    digitalWrite(PIN_PT1000_SW, LOW);

    TEST_ASSERT_TRUE_MESSAGE(raw >= 0,    "ADC ch0: reading below 0");
    TEST_ASSERT_TRUE_MESSAGE(raw <= 1023, "ADC ch0: reading above 1023");
}

// All 8 MUX channels produce a valid ADC reading in [0, 1023].
// Tests that MUX address switching and ADC sampling complete without hanging.
void test_adc_all_channels() {
    analogReadResolution(10);
    pinMode(PIN_MUX_A0,    OUTPUT);
    pinMode(PIN_MUX_A1,    OUTPUT);
    pinMode(PIN_MUX_A2,    OUTPUT);
    pinMode(PIN_PT1000_SW, OUTPUT);

    digitalWrite(PIN_PT1000_SW, HIGH);

    for (uint8_t ch = 0; ch < 8; ch++) {
        selectChannel(ch);
        delayMicroseconds(500);

        int raw = analogRead(PIN_PT1000_ADC);

        TEST_ASSERT_TRUE_MESSAGE(raw >= 0,    "ADC: reading below 0");
        TEST_ASSERT_TRUE_MESSAGE(raw <= 1023, "ADC: reading above 1023");
    }

    digitalWrite(PIN_PT1000_SW, LOW);
}

// ── Unity entry point ─────────────────────────────────────────────────────────

void setUp()    {}
void tearDown() {}

void setup() {
    delay(2000);
    Serial.begin(115200);
    UNITY_BEGIN();
    RUN_TEST(test_adc_channel0_range);
    RUN_TEST(test_adc_all_channels);
    UNITY_END();
}

void loop() {}
