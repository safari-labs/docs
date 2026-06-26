#include <Arduino.h>
#include "pins.h"
#include "subsystems/TTC.h"

// Meme patron que IbNav/ADCS : UART instancie en global statique avec les
// PinName, faute de UART::setTX()/setRX() dans arduino-mbed 4.5.0.
static UART _ttcUart(digitalPinToPinName(PIN_TX_TTC),
                     digitalPinToPinName(PIN_RX_TTC), NC, NC);

TTC ttc;

TTC::TTC() : PowerChannel(PIN_EN_TTC, PIN_F1_TTC, "TTC") {}

void TTC::init() {
  _ttcUart.begin(TTC_BAUD);
  pinMode(PIN_CLK_TTC, OUTPUT);
  pinMode(PIN_RUN_TTC, OUTPUT);
  pinMode(_pinFault,   INPUT_PULLUP);
  pinMode(_pinEN,      OUTPUT);
  digitalWrite(PIN_RUN_TTC, LOW);
  disable();
}

HardwareSerial& TTC::stream() { return _ttcUart; }

// Envoi binaire brut vers le RFD900x (mode serie transparent).
void TTC::transmit(const uint8_t* buf, size_t len) {
  _ttcUart.write(buf, len);
}
