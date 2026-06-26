#pragma once
#include <Arduino.h>

class BootSequence {
public:
  void run();
  bool isDisabled(uint8_t channel) const;

  // TODO: bool testTTC();
  // TODO: bool testIbNav();
  // TODO: bool testADCS();
  // TODO: bool testJetson();
  // TODO: bool testA7Sii();

private:
  uint8_t _disabledMask;
  void    _bootModule(const char* name, uint8_t channel, uint32_t stabilizeMs);
  void    _markDisabled(uint8_t channel);
};

extern BootSequence bootSeq;
