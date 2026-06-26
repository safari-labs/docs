// test_gpio_imu.cpp
// Verifies IMU-related pins: AD0 (GPIO12) and I2C1 bus (GPIO6/7).
// I2C1 scan is non-fatal — passes whether or not the ICM-20948 is connected.
// Uses the same TwoWire instantiation pattern as imu.cpp because Wire1 is not
// exported by the Arduino-Mbed variant for the Pico.

#include <Arduino.h>
#include <unity.h>
#include <Wire.h>
#include "config.h"

// I2C1 instance on GPIO6/7 (mirrors imu.cpp)
static TwoWire _wire1(PIN_IMU_SDA, PIN_IMU_SCL);

// ── Tests ─────────────────────────────────────────────────────────────────────

// AD0 must be held LOW to lock the ICM-20948 I2C address at 0x68.
// Verify the pin can be driven and read back LOW.
void test_ad0_low() {
    pinMode(PIN_IMU_AD0, OUTPUT);
    digitalWrite(PIN_IMU_AD0, LOW);
    TEST_ASSERT_EQUAL(LOW, digitalRead(PIN_IMU_AD0));
}


// Non-fatal I2C1 scan for the ICM-20948 at IMU_I2C_ADDR (0x68).
// Passes regardless of whether the sensor is physically connected.
void test_i2c1_scan() {
    _wire1.begin();
    _wire1.beginTransmission(IMU_I2C_ADDR);
    uint8_t err = _wire1.endTransmission();
    _wire1.end();

    Serial.println(err == 0
        ? "I2C1: ICM-20948 found at 0x68"
        : "I2C1: ICM-20948 not found at 0x68 (no sensor connected)");
    // No assertion — result is informational only
}

// ── Unity entry point ─────────────────────────────────────────────────────────

void setUp()    {}
void tearDown() {}

void setup() {
    delay(2000);
    Serial.begin(115200);
    UNITY_BEGIN();
    RUN_TEST(test_ad0_low);
    RUN_TEST(test_i2c1_scan);
    UNITY_END();
}

void loop() {}
