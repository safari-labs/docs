#include "watchdog.h"

bool WatchdogComm::init() {
    _ready = false;

    // CLK line idle LOW
    pinMode(PIN_WD_CLK, OUTPUT);
    digitalWrite(PIN_WD_CLK, LOW);

    // I2C0 on GPIO4/5 — default pins for Wire on the Pico Mbed variant; no pin remapping needed
    Wire.begin();

    // Probe the watchdog address; a NACK (error ≠ 0) means it is absent
    Wire.beginTransmission(WATCHDOG_I2C_ADDR);
    uint8_t err = Wire.endTransmission();

    if (err != 0) {
        _error = SensorError::NOT_FOUND;
        // Watchdog absence is non-fatal: other modules must not be affected
        Serial.println("[Watchdog] not found");
        g_adcs.watchdog.connected = false;
        return false;
    }

    _error = SensorError::OK;
    _ready = true;
    g_adcs.watchdog.connected = true;
    Serial.println("[Watchdog] OK");
    return true;
}

bool WatchdogComm::read() {
    if (!_ready) return false;

    tickClock();

    Wire.beginTransmission(WATCHDOG_I2C_ADDR);
    uint8_t err = Wire.endTransmission();

    if (err != 0) {
        _error = SensorError::NOT_FOUND;
        g_adcs.watchdog.connected = false;
        return false;
    }

    _error = SensorError::OK;
    g_adcs.watchdog.connected = true;
    return true;
}

void WatchdogComm::sendStatus(uint8_t statusByte) {
    if (!_ready) return;
    Wire.beginTransmission(WATCHDOG_I2C_ADDR);
    Wire.write(statusByte);
    Wire.endTransmission();
}

void WatchdogComm::tickClock() {
    // One CLK pulse: HIGH for half-period, then LOW
    digitalWrite(PIN_WD_CLK, HIGH);
    delayMicroseconds(WD_CLK_HALF_US);
    digitalWrite(PIN_WD_CLK, LOW);
    delayMicroseconds(WD_CLK_HALF_US);
}
