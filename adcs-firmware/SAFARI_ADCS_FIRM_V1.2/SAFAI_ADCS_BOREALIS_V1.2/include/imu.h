#pragma once
#include "sensors.h"
#include <Wire.h>
#include <Adafruit_ICM20948.h>
#include <Adafruit_Sensor.h>

class ImuModule : public SensorModule {
public:
    bool        init()           override;
    bool        read()           override;
    bool        isReady()  const override { return _ready; }
    const char* name()     const override { return "IMU"; }
    SensorError lastError() const override { return _error; }

private:
    Adafruit_ICM20948 _icm;
    bool              _ready     = false;
    SensorError       _error     = SensorError::OK;
    uint8_t           _failCount = 0;
};
