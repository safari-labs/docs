// test_sim_spi_altimeter.cpp
// Validates the SPI bus wired to the MS5607 altimeter (SPI1, GPIO8-11)
// using a MOSI→MISO loopback: every byte sent appears back on MISO.
//
// HARDWARE REQUIRED
// -----------------
//   One wire:
//       Pico pin 15 (GP11 / MOSI)  ────wire────  Pico pin 11 (GP8 / MISO)
//
// CS (GPIO9) is driven manually. SCK (GPIO10) and MOSI (GPIO11) are driven
// by the SPI1 peripheral. No MS5607 needed.
//
// What this tests
// ---------------
//   Loopback confirms the SPI1 peripheral clocks correctly, MOSI drives the
//   wire, and MISO samples it back. CS active-LOW timing is also exercised.

#include <Arduino.h>
#include <SPI.h>
#include <unity.h>
#include "config.h"

// SPI1 peripheral on GPIO8 (MISO), GPIO11 (MOSI), GPIO10 (SCK)
static SPIClass altSPI(PIN_ALT_MISO, PIN_ALT_MOSI, PIN_ALT_SCLK);

static inline void csLow()  { digitalWrite(PIN_ALT_CS, LOW);  }
static inline void csHigh() { digitalWrite(PIN_ALT_CS, HIGH); }

// ── Tests ─────────────────────────────────────────────────────────────────────

// Connectivity check: sending 0x00 must return 0x00.
// Without the wire, MISO floats and the received byte is typically 0xFF.
void test_sim_spi_wire_connected() {
    csLow();
    uint8_t rx = altSPI.transfer(0x00);
    csHigh();

    char msg[80];
    snprintf(msg, sizeof(msg),
        "Wire absent? tx=0x00 rx=0x%02X (need 0x00) — bridge pin15 to pin11", rx);
    TEST_ASSERT_EQUAL_MESSAGE(0x00, rx, msg);
}

// Single-byte loopback: 0xAA in → 0xAA out
void test_sim_spi_loopback_byte() {
    csLow();
    uint8_t rx = altSPI.transfer(0xAA);
    csHigh();

    char msg[40];
    snprintf(msg, sizeof(msg), "loopback: tx=0xAA rx=0x%02X", rx);
    TEST_ASSERT_EQUAL_MESSAGE(0xAA, rx, msg);
}

// Six-byte burst: all-zeros, all-ones, alternating patterns, counters
void test_sim_spi_loopback_pattern() {
    static const uint8_t tx[] = { 0x00, 0xFF, 0x5A, 0xA5, 0x01, 0xFE };
    csLow();
    for (uint8_t i = 0; i < sizeof(tx); i++) {
        uint8_t rx = altSPI.transfer(tx[i]);
        char msg[48];
        snprintf(msg, sizeof(msg), "burst[%u]: tx=0x%02X rx=0x%02X", i, tx[i], rx);
        TEST_ASSERT_EQUAL_MESSAGE(tx[i], rx, msg);
    }
    csHigh();
}

// CS line must be HIGH at idle, LOW during a transfer, HIGH again after
void test_sim_spi_cs_timing() {
    TEST_ASSERT_EQUAL_MESSAGE(HIGH, digitalRead(PIN_ALT_CS), "CS: not HIGH at idle");

    csLow();
    TEST_ASSERT_EQUAL_MESSAGE(LOW, digitalRead(PIN_ALT_CS), "CS: not LOW when selected");
    altSPI.transfer(0x00);   // dummy transfer while CS is low
    csHigh();

    TEST_ASSERT_EQUAL_MESSAGE(HIGH, digitalRead(PIN_ALT_CS), "CS: not HIGH after deselect");
}

// ── Unity entry point ─────────────────────────────────────────────────────────

void setUp()    { csHigh(); }   // deselect between tests
void tearDown() { csHigh(); }

void setup() {
    delay(2000);
    Serial.begin(115200);
    Serial.println("--- test_sim_spi_altimeter ---");
    Serial.println("REQUIRES: wire Pico pin15 (GP11/MOSI) -> pin11 (GP8/MISO)");

    pinMode(PIN_ALT_CS, OUTPUT);
    csHigh();
    altSPI.begin();
    altSPI.beginTransaction(SPISettings(1000000UL, MSBFIRST, SPI_MODE0));

    UNITY_BEGIN();
    RUN_TEST(test_sim_spi_wire_connected);   // connectivity check first
    RUN_TEST(test_sim_spi_loopback_byte);
    RUN_TEST(test_sim_spi_loopback_pattern);
    RUN_TEST(test_sim_spi_cs_timing);
    UNITY_END();
}

void loop() {}
