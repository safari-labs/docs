#pragma once
#include <Wire.h>
#include "subsystems/PowerChannel.h"

#define IBNAV_I2C_ADDR  0x42  // TODO: adresse a confirmer avec le firmware IbNav (GPS)
#define IBNAV_RAW_BYTES 32    // octets demandes par sondage I2C

class IbNav : public PowerChannel {
public:
  IbNav();
  void      init();
  TwoWire&  wire();       // I2C0 sur GPIO 0/1 (flux NMEA via DDC)
  void      forwardRaw(); // sondage I2C, recopie les trames NMEA vers Serial

  // TODO: bool  isPPSActive();
  // TODO: float getAltitude();
  // TODO: float getVerticalSpeed();
  // TODO: void  collectData(struct TelemetryPacket&);
};

extern IbNav ibNav;
