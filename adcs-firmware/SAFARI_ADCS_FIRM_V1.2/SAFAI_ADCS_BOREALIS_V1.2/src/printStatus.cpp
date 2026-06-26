#include "printStatus.h"
#include <Arduino.h>

void printAdcsStatus() {
    Serial.println("=== ADCS DATA ===");

    // ── IMU ──────────────────────────────────────────────────────────────────
    if (g_adcs.imu.valid) {
        Serial.print("IMU  accel [m/s2] : ");
        Serial.print(g_adcs.imu.ax, 3); Serial.print("  ");
        Serial.print(g_adcs.imu.ay, 3); Serial.print("  ");
        Serial.println(g_adcs.imu.az, 3);

        Serial.print("IMU  gyro  [rad/s]: ");
        Serial.print(g_adcs.imu.gx, 4); Serial.print("  ");
        Serial.print(g_adcs.imu.gy, 4); Serial.print("  ");
        Serial.println(g_adcs.imu.gz, 4);

        Serial.print("IMU  mag   [uT]   : ");
        Serial.print(g_adcs.imu.mx, 2); Serial.print("  ");
        Serial.print(g_adcs.imu.my, 2); Serial.print("  ");
        Serial.println(g_adcs.imu.mz, 2);
    } else {
        Serial.println("IMU  --- no data ---");
    }

    // ── Altimeter ─────────────────────────────────────────────────────────────
    if (g_adcs.altimeter.valid) {
        Serial.print("Alt  pressure  [hPa]: "); Serial.println(g_adcs.altimeter.pressure,    2);
        Serial.print("Alt  temp      [°C] : "); Serial.println(g_adcs.altimeter.temperature, 2);
        Serial.print("Alt  altitude  [m]  : "); Serial.println(g_adcs.altimeter.altitude,    2);
    } else {
        Serial.println("Alt  --- no data ---");
    }

    // ── Pt1000 ────────────────────────────────────────────────────────────────
    Serial.print("Pt1000 active: ");
    Serial.print(g_adcs.pt1000.active_count);
    Serial.print("/");
    Serial.println(PT1000_COUNT);

    for (uint8_t i = 0; i < PT1000_COUNT; i++) {
        Serial.print("  S");
        Serial.print(i + 1);
        Serial.print(": ");
        if (g_adcs.pt1000.valid[i]) {
            Serial.print(g_adcs.pt1000.temps[i], 2);
            Serial.println(" C");
        } else {
            Serial.println("invalid");
        }
    }

    // ── Watchdog ──────────────────────────────────────────────────────────────
    Serial.print("Watchdog: ");
    Serial.println(g_adcs.watchdog.connected ? "connected" : "disconnected");

    Serial.println("=================");
}
