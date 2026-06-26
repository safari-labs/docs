// test_gpio_mux.cpp
// Verifies Pt1000 MUX GPIO pins (GPIO0–3) with no external hardware.
// Tests GPIO output-register readback and all 8 MUX channel bit patterns.

#include <Arduino.h>
#include <unity.h>
#include "config.h"

// ── Tests ─────────────────────────────────────────────────────────────────────

// Each MUX address pin can be driven HIGH and read back HIGH, then LOW/LOW.
void test_mux_pins_toggle() {
    const uint8_t mux_pins[] = { PIN_MUX_A0, PIN_MUX_A1, PIN_MUX_A2 };

    for (uint8_t i = 0; i < 3; i++) {
        pinMode(mux_pins[i], OUTPUT);

        digitalWrite(mux_pins[i], HIGH);
        TEST_ASSERT_EQUAL(HIGH, digitalRead(mux_pins[i]));

        digitalWrite(mux_pins[i], LOW);
        TEST_ASSERT_EQUAL(LOW, digitalRead(mux_pins[i]));
    }
}

// Power switch pin toggles correctly
void test_pt1000_switch_toggle() {
    pinMode(PIN_PT1000_SW, OUTPUT);

    digitalWrite(PIN_PT1000_SW, HIGH);
    TEST_ASSERT_EQUAL(HIGH, digitalRead(PIN_PT1000_SW));

    digitalWrite(PIN_PT1000_SW, LOW);
    TEST_ASSERT_EQUAL(LOW, digitalRead(PIN_PT1000_SW));
}

// For each of the 8 MUX channels, A2:A1:A0 bit pattern matches the channel index.
// Mirrors the selectChannel() logic in pt1000.cpp.
void test_channel_select_all() {
    pinMode(PIN_MUX_A0, OUTPUT);
    pinMode(PIN_MUX_A1, OUTPUT);
    pinMode(PIN_MUX_A2, OUTPUT);

    for (uint8_t ch = 0; ch < 8; ch++) {
        digitalWrite(PIN_MUX_A0, (ch >> 0) & 0x01);
        digitalWrite(PIN_MUX_A1, (ch >> 1) & 0x01);
        digitalWrite(PIN_MUX_A2, (ch >> 2) & 0x01);

        TEST_ASSERT_EQUAL((ch >> 0) & 0x01, digitalRead(PIN_MUX_A0));
        TEST_ASSERT_EQUAL((ch >> 1) & 0x01, digitalRead(PIN_MUX_A1));
        TEST_ASSERT_EQUAL((ch >> 2) & 0x01, digitalRead(PIN_MUX_A2));
    }

    // Leave MUX at channel 0 and switch OFF
    digitalWrite(PIN_MUX_A0, LOW);
    digitalWrite(PIN_MUX_A1, LOW);
    digitalWrite(PIN_MUX_A2, LOW);
    digitalWrite(PIN_PT1000_SW, LOW);
}

// ── Unity entry point ─────────────────────────────────────────────────────────

void setUp()    {}
void tearDown() {}

void setup() {
    delay(2000);
    Serial.begin(115200);
    UNITY_BEGIN();
    RUN_TEST(test_mux_pins_toggle);
    RUN_TEST(test_pt1000_switch_toggle);
    RUN_TEST(test_channel_select_all);
    UNITY_END();
}

void loop() {}
