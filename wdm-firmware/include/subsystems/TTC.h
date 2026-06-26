#pragma once
#include <api/HardwareSerial.h>
#include "subsystems/PowerChannel.h"

#define TTC_BAUD 57600  // RFD900x en mode serie transparent

class TTC : public PowerChannel {
public:
  TTC();
  void            init();
  HardwareSerial& stream();                              // UART RFD900x
  void            transmit(const uint8_t* buf, size_t len); // envoi binaire au sol

  // TODO: bool ping();
  // TODO: void alert(const char* message);
};

extern TTC ttc;
