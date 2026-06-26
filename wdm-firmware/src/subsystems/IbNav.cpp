#include <Arduino.h>
#include <Wire.h>
#include "pins.h"
#include "subsystems/IbNav.h"

// IbNav en I2C0 : le GPS expose son flux NMEA via le bus DDC.
// TwoWire instancie manuellement avec les broches SDA/SCL (meme patron que Jetson).
static TwoWire _ibnavWire(PIN_SDA_IBNAV, PIN_SCL_IBNAV);

IbNav ibNav;

IbNav::IbNav() : PowerChannel(PIN_EN_IBNAV, PIN_F1_IBNAV, "IbNav") {}

void IbNav::init() {
  _ibnavWire.begin();
  pinMode(PIN_CLK_IBNAV, OUTPUT);
  pinMode(PIN_PPS_IBNAV, INPUT);   // 1PPS materiel, independant du bus I2C
  pinMode(_pinFault,     INPUT_PULLUP);
  pinMode(_pinEN,        OUTPUT);
  disable();
}

TwoWire& IbNav::wire() { return _ibnavWire; }

// Sondage I2C0 a 1 Hz : lit le flux NMEA du GPS et le recopie vers Serial.
// Pas de sync bytes ni de parsing : recopie brute.
// TODO: lire d'abord le registre de compte d'octets dispo (u-blox 0xFD/0xFE)
//       pour ne pas tronquer les trames NMEA plus longues que IBNAV_RAW_BYTES.
void IbNav::forwardRaw() {
  static uint32_t lastPoll = 0;
  if (millis() - lastPoll < 1000) return;
  lastPoll = millis();

  _ibnavWire.requestFrom((uint8_t)IBNAV_I2C_ADDR, (uint8_t)IBNAV_RAW_BYTES);
  while (_ibnavWire.available())
    Serial.write((char)_ibnavWire.read());
}
