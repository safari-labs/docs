// Mock du WDT hardware RP2040 pour les tests NATIFS (env:native).
// Les appels sont des no-op : aucun reset reel ne se produit sur PC.
#pragma once
#include <stdint.h>

inline void watchdog_enable(uint32_t, bool) {}
inline void watchdog_update() {}
inline void watchdog_reboot(uint32_t, uint32_t, uint32_t) {}
