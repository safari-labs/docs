#include <Arduino.h>
#include "hardware/watchdog.h"
#include "pins.h"
#include "behavior/Watchdog.h"
#include "behavior/FlightState.h"

// Les canaux de production sont injectes par main.cpp via setChannels() (DI).
// Watchdog ne reference donc aucun global de sous-systeme : il reste testable
// en isolation (mocks) et compilable nativement (sans UART/Wire).

Watchdog watchdog;

void Watchdog::init(uint32_t timeout_ms) {
  _prevFaults    = 0;
  _disabledMask  = 0;
  _channels      = nullptr;
  _channelCount  = 0;
  _core0AliveAt  = millis(); // considéré vivant dès le boot
  memset(_faultCounters,  0, sizeof(_faultCounters));
  memset(_faultStartTime, 0, sizeof(_faultStartTime));
  memset(_disableUntil,   0, sizeof(_disableUntil));
  memset(_heartbeatLast,  0, sizeof(_heartbeatLast));
  for (uint8_t i = 0; i < 5; i++) _heartbeatSeen[i] = millis();
  watchdog_enable(timeout_ms, true); // pause_on_debug = true
}

// Core 0 appelle notifyAlive() a chaque tour de loop() pour prouver sa vitalité.
void Watchdog::notifyAlive() {
  _core0AliveAt = millis();
}

// Retourne vrai si Core 0 a signalé dans la fenêtre CORE0_ALIVE_TIMEOUT_MS.
bool Watchdog::isCore0Alive() const {
  return (millis() - _core0AliveAt) < CORE0_ALIVE_TIMEOUT_MS;
}

// Nourrit le WDT hardware si Core 0 est vivant.
// Si Core 0 est silencieux, appelle fullSystemReset() — point de reboot unique.
void Watchdog::kick() {
  if (isCore0Alive()) {
    watchdog_update();
  } else {
    fullSystemReset(); // coupe les canaux + watchdog_reboot()
  }
}

void Watchdog::setChannels(PowerChannel** ch, uint8_t n) {
  _channels     = ch;
  _channelCount = n;
}

void Watchdog::markDisabled(uint8_t channel) {
  _disabledMask |= (1 << channel);
}

// Renvoie le canal i parmi ceux injectes par setChannels() (nullptr sinon).
PowerChannel* Watchdog::channelAt(uint8_t i) {
  if (!_channels) return nullptr;
  return (i < _channelCount) ? _channels[i] : nullptr;
}

void Watchdog::checkAllFaults() {
  for (uint8_t i = 0; i < _channelCount; i++) {
    PowerChannel* c = channelAt(i);
    if (!c) continue;

    // Canal hors service définitif : ignoré.
    if (_disabledMask & (1 << i)) continue;

    // Disable prolongé non bloquant : ré-activation à l'expiration du timer.
    if (_disableUntil[i]) {
      if ((int32_t)(millis() - _disableUntil[i]) >= 0) {
        _disableUntil[i] = 0;
        c->enable();
        Serial.print("[REENABLE] t="); Serial.print(millis() / 1000);
        Serial.print("s ch="); Serial.println(c->getName());
      } else {
        continue; // toujours en disable prolongé
      }
    }

    bool fault     = c->isFault();
    bool wasActive = _prevFaults & (1 << i);

    if (fault && !wasActive) {
      // Front montant : horodatage, incrément compteur, log, réponse graduée.
      _faultStartTime[i] = millis();
      _faultCounters[i]++;
      Serial.print("[FAULT] t=");
      Serial.print(millis() / 1000);
      Serial.print("s ch=");
      Serial.print(c->getName());
      Serial.print(" cnt=");
      Serial.print(_faultCounters[i]);
      Serial.print(" state=");
      Serial.println(flightState.name());
      _prevFaults |= (1 << i);
      faultHandler(i);
    } else if (!fault && wasActive) {
      // Front descendant : durée de la faute, log.
      uint32_t dur = millis() - _faultStartTime[i];
      Serial.print("[CLEAR] t=");
      Serial.print(millis() / 1000);
      Serial.print("s ch=");
      Serial.print(c->getName());
      Serial.print(" dur=");
      Serial.print(dur);
      Serial.println("ms");
      _prevFaults &= ~(1 << i);
    } else if (!fault && _faultCounters[i] > 0 &&
               (millis() - _faultStartTime[i]) > RECOVERY_RESET_MS) {
      // Récupération durable (sain depuis RECOVERY_RESET_MS) : RAZ de l'escalade.
      resetFaultCounter(i);
      Serial.print("[RECOVER] t=");
      Serial.print(millis() / 1000);
      Serial.print("s ch=");
      Serial.println(c->getName());
    }
  }
}

// Point d'entrée unique sur une faute confirmée : applique la réponse graduée.
void Watchdog::faultHandler(uint8_t channel) {
  if (channel >= 5) return;
  if (_disabledMask & (1 << channel)) return; // déjà hors service
  escalate(channel);
}

// Réponse graduée selon le nombre de fautes accumulées (cf. section 5).
void Watchdog::escalate(uint8_t channel) {
  PowerChannel* c = channelAt(channel);
  if (!c) return;
  uint8_t n = _faultCounters[channel];

  if (n >= FAULT_PERM_THRESHOLD) {
    // Niveau 3 : coupure définitive + alerte sol.
    c->disable();
    _disableUntil[channel] = 0;
    markDisabled(channel);
    Serial.print("[ESCALATE] ch=");
    Serial.print(c->getName());
    Serial.print(" cnt=");
    Serial.print(n);
    Serial.println(" -> PERMANENT DISABLE (alert TT&C)");
    // TODO: telemetry.alert("<ch> permanently disabled") une fois alert() prêt.
  } else if (n >= FAULT_EXT_THRESHOLD) {
    // Niveau 2 : disable prolongé NON bloquant (re-enable géré par checkAllFaults).
    c->disable();
    _disableUntil[channel] = millis() + EXTENDED_DISABLE_MS;
    if (_disableUntil[channel] == 0) _disableUntil[channel] = 1; // évite la valeur "actif"
    Serial.print("[ESCALATE] ch=");
    Serial.print(c->getName());
    Serial.print(" cnt=");
    Serial.print(n);
    Serial.print(" -> extended disable ");
    Serial.print(EXTENDED_DISABLE_MS / 1000);
    Serial.println("s");
  } else {
    // Niveau 1 : power cycle (tentative de récupération).
    c->cycle(POWER_CYCLE_MS);
    Serial.print("[ESCALATE] ch=");
    Serial.print(c->getName());
    Serial.print(" cnt=");
    Serial.print(n);
    Serial.println(" -> power cycle");
  }
}

// Remet à zéro le compteur d'escalade d'un canal (récupération ou commande sol).
void Watchdog::resetFaultCounter(uint8_t channel) {
  if (channel >= 5) return;
  _faultCounters[channel]  = 0;
  _faultStartTime[channel] = 0;
}

// Coupe tous les canaux puis force un reboot propre du RP2040 via le WDT.
void Watchdog::fullSystemReset() {
  Serial.println("[RESET] full system reset -> reboot RP2040");
  Serial.flush();
  for (uint8_t i = 0; i < 5; i++) {
    PowerChannel* c = channelAt(i);
    if (c) c->disable();
  }
  delay(200);               // laisse les rails se décharger
  watchdog_reboot(0, 0, 0); // reboot normal (pc=sp=0) — ne retourne jamais sur materiel reel
}

// Détecte l'activité sur la broche CLK du canal (battement = toggle).
// Pertinent pour les canaux à CLK en entrée (ADCS, Jetson). Pour les canaux
// dont la CLK est pilotée en sortie (IbNav, TT&C), le résultat n'est pas
// significatif. Retourne true si un battement a eu lieu < HEARTBEAT_TIMEOUT_MS.
bool Watchdog::monitorHeartbeat(uint8_t channel) {
  if (channel >= 5) return false;

  // IbNav (0) et TTC (3) n'ont pas de CLK en entree generee par le sous-module.
  // Consideres toujours vivants du point de vue heartbeat CLK.
  if (channel == 0 || channel == 3) return true;

  // Indices alignes sur prodChannels : 1=ADCS, 2=Jetson, 4=A7Sii.
  static const uint8_t clkPin[5] = {
    0,             // 0 IbNav  — non utilise (bypass ci-dessus)
    PIN_CLK_ADCS,  // 1 ADCS
    PIN_CLK_JETSON,// 2 Jetson
    0,             // 3 TTC    — non utilise (bypass ci-dessus)
    PIN_CLK_A7SII  // 4 A7Sii
  };
  bool level = digitalRead(clkPin[channel]);
  if (level != _heartbeatLast[channel]) {
    _heartbeatLast[channel] = level;
    _heartbeatSeen[channel] = millis();
  }
  return (millis() - _heartbeatSeen[channel]) < HEARTBEAT_TIMEOUT_MS;
}
