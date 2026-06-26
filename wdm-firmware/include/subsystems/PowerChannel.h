#pragma once
#include <Arduino.h>

// Abstraction d'un canal alimenté par un TPS1H200AQDGNRQ1.
// EN (OUTPUT) : HIGH = alimentation activée, LOW = coupée.
// FAULT (INPUT_PULLUP) : open-drain actif-bas — la puce tire la broche à GND
//   quand elle détecte surintensité, court-circuit ou surtempérature.
//   INPUT_PULLUP maintient la broche à HIGH en l'absence de faute.
class PowerChannel {
public:
  PowerChannel(uint8_t pinEN, uint8_t pinFault, const char* name);
  // Virtuelles : permettent l'injection de mocks (enregistrement d'appels) en test.
  // En production, les sous-systèmes n'overrident pas → comportement de base.
  virtual void enable();
  virtual void disable();
  virtual void cycle(uint32_t ms); // coupe puis réalimente après ms millisecondes
  virtual bool isFault() const;    // true si la puce signale une faute
  const char* getName() const;

protected:
  uint8_t     _pinEN;
  uint8_t     _pinFault;
  const char* _name;
};
