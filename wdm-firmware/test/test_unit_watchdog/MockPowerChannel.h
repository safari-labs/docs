#pragma once
#include "subsystems/PowerChannel.h"

// Canal fictif pour les tests unitaires.
//  - isFault() retourne _faultState (pas de hardware).
//  - enable()/disable()/cycle() n'agissent PAS sur le GPIO : ils comptent les
//    appels, ce qui permet de verifier la reponse graduee de escalate().
// Les broches pinEN=0 / pinFault=0 ne sont jamais lues/ecrites.
class MockPowerChannel : public PowerChannel {
public:
  explicit MockPowerChannel(const char* name)
    : PowerChannel(0, 0, name), _faultState(false),
      _enableCalls(0), _disableCalls(0), _cycleCalls(0) {}

  void setFault(bool state) { _faultState = state; }

  bool isFault() const override { return _faultState; }
  void enable()  override { _enableCalls++;  }
  void disable() override { _disableCalls++; }
  void cycle(uint32_t /*ms*/) override { _cycleCalls++; }

  uint8_t enableCalls()  const { return _enableCalls;  }
  uint8_t disableCalls() const { return _disableCalls; }
  uint8_t cycleCalls()   const { return _cycleCalls;   }

  void resetCalls() { _enableCalls = _disableCalls = _cycleCalls = 0; }

private:
  bool    _faultState;
  uint8_t _enableCalls, _disableCalls, _cycleCalls;
};
