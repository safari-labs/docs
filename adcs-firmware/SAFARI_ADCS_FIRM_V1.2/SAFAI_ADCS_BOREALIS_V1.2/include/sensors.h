#pragma once
#include <Arduino.h>
#include "config.h"

// ── Per-module error codes ────────────────────────────────────────────────────
enum class SensorError : uint8_t {
    OK          = 0,
    NOT_FOUND,       // no response on bus (I2C NACK, SPI timeout)
    BAD_ID,          // unexpected WHO_AM_I or invalid PROM CRC
    DATA_INVALID,    // value outside physical range
    READ_FAIL        // partial or corrupted read
};

// ── Common module interface ───────────────────────────────────────────────────
class SensorModule {
public:
    virtual bool        init()           = 0;  // false if sensor absent/faulty; never blocks > 50 ms
    virtual bool        read()           = 0;  // false if read fails; never blocks
    virtual bool        isReady()  const = 0;
    virtual const char* name()     const = 0;
    virtual SensorError lastError() const = 0;
    virtual ~SensorModule() {}
};

// ── Shared data bus (each module writes only its own section) ─────────────────
struct AdcsData {
    struct {
        float ax, ay, az;   // m/s²
        float gx, gy, gz;   // rad/s
        float mx, my, mz;   // µT
        bool  valid;
    } imu;

    struct {
        float pressure;     // hPa
        float temperature;  // °C
        float altitude;     // m
        bool  valid;
    } altimeter;

    struct {
        float   temps[8];   // °C, index 0..7 = S1..S8
        bool    valid[8];
        uint8_t active_count;
    } pt1000;

    struct {
        bool connected;
    } watchdog;
};

extern AdcsData g_adcs;

// ── Sensor orchestrator ───────────────────────────────────────────────────────
class SensorManager {
public:
    SensorManager();
    void registerModule(SensorModule* m);
    void initAll();   // calls init() on each; marks absent ones not-ready
    void readAll();   // silently skips non-ready modules

private:
    SensorModule* _modules[MAX_MODULES];
    uint8_t       _count;
};
