#pragma once
#include <Arduino.h>            // expose le HardwareSerial global (namespace arduino) sur Pico
#include <api/HardwareSerial.h> // fournit HardwareSerial en build natif (mock)

#define CMD_BUF_SIZE 64

// Terminal de commandes embarque non-bloquant.
// Lit les commandes caractere par caractere depuis un HardwareSerial (USB ou TT&C).
// Dispatcher appele quand un '\n' ou '\r' est recu.
//
// Utilisation :
//   setup()  : terminal.init(Serial)            // banc USB
//   setup()  : terminal.init(ttc.stream())      // vol RFD900x
//   loop()   : terminal.poll()                  // appel non bloquant
//
// Commandes disponibles : voir dispatch() ou envoyer "help".
class CommandTerminal {
public:
  void init(HardwareSerial& port);
  void poll(); // appeler depuis loop() — ne bloque jamais

private:
  void dispatch();
  void respond(const char* msg);
  void respondFmt(const char* fmt, ...);

  HardwareSerial* _port;
  char    _buf[CMD_BUF_SIZE];
  uint8_t _len;
};

extern CommandTerminal terminal;
