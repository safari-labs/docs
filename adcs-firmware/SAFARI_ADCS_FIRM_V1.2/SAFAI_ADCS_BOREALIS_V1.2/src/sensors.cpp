#include "sensors.h"

// ── Global shared data bus ────────────────────────────────────────────────────
AdcsData g_adcs = {};

// ── SensorManager ─────────────────────────────────────────────────────────────
SensorManager::SensorManager() : _count(0) {}

void SensorManager::registerModule(SensorModule* m) {
    if (_count < MAX_MODULES) {
        _modules[_count++] = m;
    }
}

void SensorManager::initAll() {
    for (uint8_t i = 0; i < _count; i++) {
        bool ok = _modules[i]->init();
        if (!ok) {
            Serial.print("[SensorManager] disabled: ");
            Serial.println(_modules[i]->name());
        }
    }
}

void SensorManager::readAll() {
    for (uint8_t i = 0; i < _count; i++) {
        if (_modules[i]->isReady()) {
            _modules[i]->read();
        }
    }
}
