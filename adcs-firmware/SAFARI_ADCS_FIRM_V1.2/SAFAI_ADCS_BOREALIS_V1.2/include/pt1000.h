#pragma once
#include "sensors.h"

class Pt1000Module : public SensorModule {
public:
    bool        init()           override;
    bool        read()           override;
    bool        isReady()  const override { return _ready; }
    const char* name()     const override { return "Pt1000"; }
    SensorError lastError() const override { return _error; }

private:
    bool        _ready = false;
    SensorError _error = SensorError::OK;

    void  selectChannel(uint8_t ch);
    float lutLookup(float v) const;         // binary search, floor entry — resolution ≈ 0.7 °C
};
