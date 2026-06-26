// Mock minimal de HardwareSerial pour les tests NATIFS (env:native).
// Permet a TTC.h / IbNav.h / ADCS.h de compiler sur PC. Les methodes qui
// tireraient du vrai UART sont eliminees au link par --gc-sections.
#pragma once
#include <stdint.h>
#include <stddef.h>

// Les methodes sont virtuelles pour permettre aux tests de les surcharger
// via TestHardwareSerial. En production, le compilateur devirtualise les appels
// sur des objets concrets (pas de cout a l'execution).
class HardwareSerial {
public:
  virtual ~HardwareSerial() {}
  virtual void   begin(unsigned long) {}
  virtual int    available() { return 0; }
  virtual int    read() { return -1; }
  virtual size_t write(uint8_t) { return 0; }
  virtual size_t write(const uint8_t*, size_t n) { return n; }
  virtual void   print(const char*) {}
  virtual void   println(const char*) {}
  virtual void   println() {}
  template<typename T> void print(const T&) {}
  template<typename T> void println(const T&) {}
};
