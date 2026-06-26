#include <Arduino.h>
#include "pins.h"
#include "subsystems/ADCS.h"

// arduino-mbed 4.5.0 ne supporte pas UART::setTX()/setRX().
// Il faut déclarer l'instance UART en global statique avec les PinName
// au lieu de reconfigurer les broches après construction.
static UART _adcsUart(digitalPinToPinName(PIN_TX_ADCS),
                      digitalPinToPinName(PIN_RX_ADCS), NC, NC);

ADCS adcs;

ADCS::ADCS() : PowerChannel(PIN_EN_ADCS, PIN_F1_ADCS, "ADCS") {}

void ADCS::init() {
  _adcsUart.begin(ADCS_BAUD);
  pinMode(PIN_CLK_ADCS,  INPUT);   // signal d'horloge/sync envoyé par l'ADCS
  pinMode(PIN_RUN_ADCS,  OUTPUT);
  pinMode(_pinFault,     INPUT_PULLUP);
  pinMode(_pinEN,        OUTPUT);
  digitalWrite(PIN_RUN_ADCS, LOW); // maintient l'ADCS en attente avant la séquence de boot
  disable();
}

HardwareSerial& ADCS::stream() { return _adcsUart; }

// Recopie octet par octet le flux ADCS recu vers Serial, sans conversion.
// Liaison UART en texte brut : pas de parsing, pas de sync bytes.
void ADCS::forwardRaw() {
  while (_adcsUart.available())
    Serial.write((char)_adcsUart.read());
}
