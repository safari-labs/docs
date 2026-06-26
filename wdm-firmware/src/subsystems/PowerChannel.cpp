#include "subsystems/PowerChannel.h"

PowerChannel::PowerChannel(uint8_t pinEN, uint8_t pinFault, const char* name)
  : _pinEN(pinEN), _pinFault(pinFault), _name(name) {}

void PowerChannel::enable()  { digitalWrite(_pinEN, HIGH); }
void PowerChannel::disable() { digitalWrite(_pinEN, LOW);  }

// Coupe l'alimentation, attend ms, puis réalimente.
// Le délai laisse le temps au condensateur de temporisation du TPS1H200
// (0.2 s auto-retry) de se réinitialiser avant le retour de tension.
void PowerChannel::cycle(uint32_t ms) { disable(); delay(ms); enable(); }

// Le TPS1H200 tire la broche FAULT à GND (open-drain) lors d'une faute.
// INPUT_PULLUP la maintient à HIGH en fonctionnement normal → LOW = faute.
bool PowerChannel::isFault() const { return digitalRead(_pinFault) == LOW; }

const char* PowerChannel::getName() const { return _name; }
