#include "altimeter.h"

bool AltimeterModule::init() {
    _ready     = false;
    _failCount = 0;

    if (!_sensor.begin()) {
        _error = SensorError::NOT_FOUND;
        Serial.println("[Altimeter] not found");
        return false;
    }

    _error = SensorError::OK;
    _ready = true;
    Serial.println("[Altimeter] OK");
    return true;
}

bool AltimeterModule::read() {
    if (!_ready) return false;

    if (!_sensor.readDigitalValue()) {
        _error = SensorError::READ_FAIL;
        g_adcs.altimeter.valid = false;
        if (++_failCount >= 3) {
            // Recovery policy: 3 consecutive failures → notify watchdog (stub)
        }
        return false;
    }

    float t = _sensor.getTemperature();
    float p = _sensor.getPressure();
    float a = _sensor.getAltitude();

    // Datasheet operating ranges: pressure 10–1200 hPa, temperature –40..+85 °C
    if (p < 10.0f || p > 1200.0f || t < -40.0f || t > 85.0f) {
        _error = SensorError::DATA_INVALID;
        g_adcs.altimeter.valid = false;
        return false;
    }

    _failCount                 = 0;
    _error                     = SensorError::OK;
    g_adcs.altimeter.pressure    = p;
    g_adcs.altimeter.temperature = t;
    g_adcs.altimeter.altitude    = a;
    g_adcs.altimeter.valid       = true;
    return true;
}
