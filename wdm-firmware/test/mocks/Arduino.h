// Mock minimal d'Arduino.h pour les tests NATIFS (env:native, sur PC).
// Fournit juste ce qu'utilisent Watchdog.cpp / FlightState.cpp / PowerChannel.cpp
// et test_main.cpp. Aucun acces materiel : tout est no-op ou valeur fixe.
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#define HIGH 1
#define LOW  0
#define INPUT        0
#define OUTPUT       1
#define INPUT_PULLUP 2
#define DEC 10
#define HEX 16
#define OCT 8
#define BIN 2

// Horloge mockee : controlable par les tests si besoin via _mockMillis().
inline unsigned long& _mockMillis() { static unsigned long v = 0; return v; }
inline unsigned long  millis() { return _mockMillis(); }
inline void           delay(unsigned long) {}

inline void pinMode(int, int) {}
inline void digitalWrite(int, int) {}
inline int  digitalRead(int) { return HIGH; }

// Serial mocke : toutes les sorties sont ignorees.
struct MockSerial {
  void begin(unsigned long) {}
  void flush() {}
  void println() {}
  template <typename T> void print(const T&)        {}
  template <typename T> void print(const T&, int)   {}
  template <typename T> void println(const T&)      {}
  template <typename T> void println(const T&, int) {}
  void write(uint8_t) {}
  void write(const uint8_t*, size_t) {}
  explicit operator bool() const { return true; }
};
inline MockSerial& _mockSerial() { static MockSerial s; return s; }
#define Serial _mockSerial()
