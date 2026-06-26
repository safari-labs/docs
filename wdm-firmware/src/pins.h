#pragma once

// --- IbNav (I2C0, flux NMEA via DDC) ---
#define PIN_SDA_IBNAV  0   // I2C0 SDA <-> IbNav (GPS)
#define PIN_SCL_IBNAV  1   // I2C0 SCL
// GPIO 2 libre (ancien UART TX IbNav)
#define PIN_CLK_IBNAV  3
#define PIN_PPS_IBNAV  4
#define PIN_F1_IBNAV   5
#define PIN_EN_IBNAV   6

// --- ADCS ---
#define PIN_CLK_ADCS   7   // sync/interrupt from ADCS
#define PIN_TX_ADCS    8   // UART1 TX — RP2040 → ADCS
#define PIN_RX_ADCS    9   // UART1 RX — ADCS → RP2040
#define PIN_RUN_ADCS   10
#define PIN_F1_ADCS    11
#define PIN_EN_ADCS    12

// --- Jetson ---
#define PIN_CLK_JETSON 13
#define PIN_SDA_JETSON 14
#define PIN_SCL_JETSON 15
#define PIN_CLK_A7SII  16
#define PIN_F1_JETSON  17
#define PIN_EN_JETSON  18

// --- TT&C ---
#define PIN_CLK_TTC    20
#define PIN_RUN_TTC    21
#define PIN_F1_TTC     22
#define PIN_EN_TTC     23
#define PIN_TX_TTC     28  // UART0 TX -> RFD900x (telemetrie descendante)
#define PIN_RX_TTC     29  // UART0 RX <- RFD900x (commandes sol)
// IbNav etant passe sur I2C0, UART0 est libre : TT&C l'utilise sans conflit.
// Allocation finale : I2C0=IbNav, I2C1=Jetson, UART0=TT&C, UART1=ADCS.

// --- A7Sii ---
#define PIN_EN_A7SII   24
#define PIN_F1_A7SII   26
