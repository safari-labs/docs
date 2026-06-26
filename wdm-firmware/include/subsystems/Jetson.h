#pragma once
#include <Wire.h>
#include "subsystems/PowerChannel.h"

#define JETSON_I2C_ADDR 0x42  // TODO: confirmer selon firmware Jetson
#define JETSON_RAW_BYTES 8    // octets demandés par sondage I2C

class Jetson : public PowerChannel {
public:
  Jetson();
  void      init();
  TwoWire&  wire();       // I2C1 sur GPIO 14/15
  void      forwardRaw(); // sondage I2C a 1 Hz, recopie les octets vers Serial

  // TODO: bool ping();
  // TODO: void collectData(struct TelemetryPacket&);
};

extern Jetson jetson;
