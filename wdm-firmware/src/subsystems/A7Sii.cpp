#include <Arduino.h>
#include "pins.h"
#include "subsystems/A7Sii.h"

A7Sii a7sii;

A7Sii::A7Sii() : PowerChannel(PIN_EN_A7SII, PIN_F1_A7SII, "A7Sii") {}

void A7Sii::init() {
  pinMode(PIN_CLK_A7SII, OUTPUT);
  pinMode(_pinFault,     INPUT_PULLUP);
  pinMode(_pinEN,        OUTPUT);
  disable();
}
