#include <Arduino.h>
#include <Wire.h>
#include "config.h"
#include "sensors.h"
#include "printStatus.h"

#if ENABLE_IMU
  #include "imu.h"
#endif
#if ENABLE_ALTIMETER
  #include "altimeter.h"
#endif
#if ENABLE_PT1000
  #include "pt1000.h"
#endif
#if ENABLE_WATCHDOG
  #include "watchdog.h"
#endif

// ── Module instances ──────────────────────────────────────────────────────────
static SensorManager manager;

#if ENABLE_IMU
  static ImuModule       imu;
#endif
#if ENABLE_ALTIMETER
  static AltimeterModule altimeter;
#endif
#if ENABLE_PT1000
  static Pt1000Module    pt1000;
#endif
#if ENABLE_WATCHDOG
  static WatchdogComm    watchdog;
#endif

// ── Loop timing ───────────────────────────────────────────────────────────────
static constexpr uint32_t LOOP_PERIOD_MS = 1000;

void setup() {
    Serial.begin(115200);
    // Wait up to 3 s for a USB host; proceed regardless so the board runs headless
    while (!Serial && millis() < 3000) {}

    Serial.println("=== SAFARI ADCS V1.2 ===");

#if ENABLE_IMU
    manager.registerModule(&imu);
#endif
#if ENABLE_ALTIMETER
    manager.registerModule(&altimeter);
#endif
#if ENABLE_PT1000
    manager.registerModule(&pt1000);
#endif
#if ENABLE_WATCHDOG
    manager.registerModule(&watchdog);
#endif

    manager.initAll();
}

void loop() {
    uint32_t t0 = millis();

    manager.readAll();

#if ENABLE_WATCHDOG
    // Build status byte and notify watchdog after every read cycle
    if (watchdog.isReady()) {
        uint8_t status = 0;
        if (g_adcs.imu.valid)                    status |= WD_STATUS_IMU_OK;
        if (g_adcs.altimeter.valid)               status |= WD_STATUS_ALT_OK;
        if (g_adcs.pt1000.active_count > 0)       status |= WD_STATUS_PT_OK;
        watchdog.sendStatus(status);
    }
#endif

    printAdcsStatus();

    // Pace the loop to LOOP_PERIOD_MS regardless of read/print duration
    uint32_t elapsed = millis() - t0;
    if (elapsed < LOOP_PERIOD_MS) {
        delay(LOOP_PERIOD_MS - elapsed);
    }
}