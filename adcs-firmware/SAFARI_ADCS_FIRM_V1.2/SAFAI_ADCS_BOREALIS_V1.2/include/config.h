#pragma once

// ── Compile-time module enable/disable ───────────────────────────────────────
#define ENABLE_IMU        1
#define ENABLE_ALTIMETER  1
#define ENABLE_PT1000     1
#define ENABLE_WATCHDOG   1

// Number of Pt1000 sensors wired to the mux (1–8)
#define PT1000_COUNT      8

// ── GPIO assignments ──────────────────────────────────────────────────────────
// Pt1000 / Analog Mux (8:1)
#define PIN_MUX_A0        0
#define PIN_MUX_A1        1
#define PIN_MUX_A2        2
#define PIN_PT1000_SW     3    // HIGH = Pt1000 circuit ON, LOW = OFF (power save)

// External Watchdog — I2C0 bus + CLK
#define PIN_WD_SDA        4
#define PIN_WD_SCL        5
#define PIN_WD_CLK       19    // CLK output from ADCS to watchdog

// IMU ICM-20948 — I2C1 bus
#define PIN_IMU_SDA       6
#define PIN_IMU_SCL       7
#define PIN_IMU_AD0      12    // Held LOW → I2C address 0x68

// Altimeter MS5607 — SPI bus
#define PIN_ALT_MISO      8    // SDO (sensor → MCU)
#define PIN_ALT_CS        9    // CSB / chip-select
#define PIN_ALT_SCLK     10
#define PIN_ALT_MOSI     11    // SDI (MCU → sensor)

// Pt1000 ADC input (op-amp output)
#define PIN_PT1000_ADC   26    // ADC0

// ── Bus parameters ────────────────────────────────────────────────────────────
#define IMU_I2C_ADDR     0x68
#define IMU_I2C_FREQ     400000UL

// ── SensorManager capacity ────────────────────────────────────────────────────
#define MAX_MODULES       4
