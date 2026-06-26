// Stub TTC pour les tests natifs (env:native).
// Shadowe include/subsystems/TTC.h via -I test/mocks (prioritaire).
// Fournit TTC::transmit() no-op et le global ttc afin que Telemetry.cpp
// compile et link sans le vrai UART.
#pragma once
#include <stdint.h>
#include <stddef.h>
#include "subsystems/PowerChannel.h"

#define TTC_BAUD 57600

class TTC : public PowerChannel {
public:
  TTC() : PowerChannel(255, 255, "TTC") {}
  void init() {}
  void transmit(const uint8_t*, size_t) {}
};

inline TTC ttc;
