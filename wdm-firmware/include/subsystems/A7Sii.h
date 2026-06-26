#pragma once
#include "subsystems/PowerChannel.h"

class A7Sii : public PowerChannel {
public:
  A7Sii();
  void init();

  // TODO: void startRecording();
  // TODO: void stopRecording();
};

extern A7Sii a7sii;
