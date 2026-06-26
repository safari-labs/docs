#pragma once
#include "sensors.h"
#include <Wire.h>

// I2C0 address of the external watchdog module.
// Confirm this value against the watchdog firmware before deployment.
#define WATCHDOG_I2C_ADDR  0x55

// CLK half-period in microseconds → full CLK period = 2 × WD_CLK_HALF_US
#define WD_CLK_HALF_US     500

// ── Status byte bit-field sent to the watchdog ────────────────────────────────
// Bit 0: IMU valid
// Bit 1: Altimeter valid
// Bit 2: Pt1000 active_count > 0
// Bits 3-7: reserved
#define WD_STATUS_IMU_OK  (1 << 0)
#define WD_STATUS_ALT_OK  (1 << 1)
#define WD_STATUS_PT_OK   (1 << 2)

class WatchdogComm : public SensorModule {
public:
    bool        init()           override;
    bool        read()           override;   // polls bus + ticks CLK
    bool        isReady()  const override { return _ready; }
    const char* name()     const override { return "Watchdog"; }
    SensorError lastError() const override { return _error; }

    // Send an ADCS status byte to the watchdog over I2C0.
    // Called after readAll() once per cycle.
    void sendStatus(uint8_t statusByte);

private:
    bool        _ready     = false;
    SensorError _error     = SensorError::OK;

    void tickClock();  // one CLK pulse on GPIO19
};
