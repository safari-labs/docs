#ifndef CONFIG_H
#define CONFIG_H
#include <stdint.h>

// ── I2C0 — GNSS M9N NMEA data (GPIO 4/5) ─────────────────────────────────────
#define I2C_SDA_PIN       4
#define I2C_SCL_PIN       5
#define I2C_CLOCK_HZ      400000
#define GNSS_I2C_ADDR     0x42

// ── UART1 — GNSS M9N UBX config commands (GPIO 16 TX / 17 RX) ────────────────
#define GNSS_UART_TX_PIN  16
#define GNSS_UART_RX_PIN  17
#define GNSS_UART_BAUD    38400

// ── Serial ────────────────────────────────────────────────────────────────────
#define SERIAL_BAUDRATE   115200

#endif // CONFIG_H
