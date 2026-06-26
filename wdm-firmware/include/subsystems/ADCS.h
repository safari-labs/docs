#pragma once
#include <api/HardwareSerial.h>
#include "subsystems/PowerChannel.h"

#define ADCS_BAUD 115200

class ADCS : public PowerChannel {
public:
  ADCS();
  void            init();
  HardwareSerial& stream();     // UART1 sur GPIO 8/9 (texte brut 115200 baud)
  void            forwardRaw(); // recopie le flux ADCS recu vers Serial

  // TODO: void collectData(struct TelemetryPacket&);
};

extern ADCS adcs;
