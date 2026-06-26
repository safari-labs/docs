#include <Arduino.h>
#include <Wire.h>
#include "pins.h"
#include "subsystems/Jetson.h"

// Wire1 n'est pas prédéclaré dans arduino-mbed 4.5.0.
// On instancie TwoWire manuellement avec les broches SDA/SCL du Jetson.
static TwoWire _jetsonWire(PIN_SDA_JETSON, PIN_SCL_JETSON);

Jetson jetson;

Jetson::Jetson() : PowerChannel(PIN_EN_JETSON, PIN_F1_JETSON, "Jetson") {}

void Jetson::init() {
  _jetsonWire.begin();
  pinMode(PIN_CLK_JETSON, INPUT);  // signal d'activité envoyé par le Jetson (heartbeat)
  pinMode(_pinFault,      INPUT_PULLUP);
  pinMode(_pinEN,         OUTPUT);
  disable();
}

TwoWire& Jetson::wire() { return _jetsonWire; }

// Sondage I2C a 1 Hz : demande JETSON_RAW_BYTES octets et les recopie vers
// Serial sans conversion. Le timer interne garde le loop() non bloquant.
void Jetson::forwardRaw() {
  static uint32_t lastPoll = 0;
  if (millis() - lastPoll < 1000) return;
  lastPoll = millis();

  _jetsonWire.requestFrom((uint8_t)JETSON_I2C_ADDR, (uint8_t)JETSON_RAW_BYTES);
  while (_jetsonWire.available())
    Serial.write((char)_jetsonWire.read());
}
