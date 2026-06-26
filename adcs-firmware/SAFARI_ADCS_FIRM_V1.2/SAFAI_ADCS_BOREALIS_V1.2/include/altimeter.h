#pragma once
#include "sensors.h"
#include <MS5607.h>

// NOTE: The architecture GPIO map targets SPI (GPIO8-11), but the MS5607 library
// bundled in Libnexamples uses I2C (Wire.h).  The module below uses that I2C
// library.  If a true SPI driver is later required, replace _sensor with an
// SPI-based MS5607 driver and update begin() accordingly.

class AltimeterModule : public SensorModule {
public:
    bool        init()           override;
    bool        read()           override;
    bool        isReady()  const override { return _ready; }
    const char* name()     const override { return "Altimeter"; }
    SensorError lastError() const override { return _error; }

private:
    MS5607      _sensor;
    bool        _ready     = false;
    SensorError _error     = SensorError::OK;
    uint8_t     _failCount = 0;
};
