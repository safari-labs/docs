#pragma once
#include <Arduino.h>
#include "subsystems/PowerChannel.h"

// Surveille les 5 canaux d'alimentation et détecte les fautes des TPS1H200.
// _prevFaults      : bitmask de l'état au dernier appel (détection de front)
// _faultCounters   : nombre de fautes par canal depuis le boot (escalade)
// _faultStartTime  : millis() au front descendant de chaque fault (durée fault)
// _disabledMask    : canaux exclus définitivement (échec au boot ou fautes répétées)
class Watchdog {
public:
  void init(uint32_t timeout_ms);

  // Core 0 appelle notifyAlive() a chaque tour de loop() pour signaler sa vitalité.
  // kick() (Core 1) ne nourrit le WDT hardware que si Core 0 a signalé dans la
  // fenêtre CORE0_ALIVE_TIMEOUT_MS. Si Core 0 se bloque, kick() cesse de nourrir
  // le WDT → le hardware reset se déclenche après timeout_ms.
  void notifyAlive();
  void kick();           // nourrit le WDT hardware seulement si Core 0 est vivant
  void checkAllFaults(); // à appeler périodiquement dans loop1()

  // Injection pour les tests : remplace les 5 globaux de production par un tableau arbitraire.
  // En production, ne pas appeler → nullptr → fallback sur ibNav/adcs/jetson/ttc/a7sii.
  void setChannels(PowerChannel** channels, uint8_t count);

  // Marque un canal comme définitivement désactivé (échec au boot ou fautes répétées).
  void markDisabled(uint8_t channel);

  // Point d'entrée unique sur une faute confirmée : applique la réponse graduée.
  void faultHandler(uint8_t channel);

  // Réponse graduée selon _faultCounters (cf. section 5 du rapport) :
  //   < FAULT_EXT_THRESHOLD   -> power cycle
  //   >= FAULT_EXT_THRESHOLD   -> disable prolongé non bloquant (EXTENDED_DISABLE_MS)
  //   >= FAULT_PERM_THRESHOLD  -> disable définitif + alerte TT&C
  void escalate(uint8_t channel);

  // Remet à zéro le compteur d'un canal (récupération durable ou commande sol).
  void resetFaultCounter(uint8_t channel);

  // Coupe tous les canaux, attend, puis force un reboot propre du RP2040.
  void fullSystemReset();

  // Lit la broche CLK du canal et détecte une activité (toggle). Retourne true
  // si un battement a été vu depuis moins de HEARTBEAT_TIMEOUT_MS.
  // Pertinent uniquement pour les canaux à CLK en entrée (ADCS, Jetson).
  bool monitorHeartbeat(uint8_t channel);

  // Accesseurs pour la vérification dans les tests.
  uint8_t  getPrevFaults()              const { return _prevFaults; }
  uint8_t  getDisabledMask()            const { return _disabledMask; }
  uint8_t  getFaultCount(uint8_t ch)    const { return ch < 5 ? _faultCounters[ch] : 0; }
  uint32_t getFaultStartTime(uint8_t ch) const { return ch < 5 ? _faultStartTime[ch] : 0; }
  uint32_t getDisableUntil(uint8_t ch)  const { return ch < 5 ? _disableUntil[ch] : 0; }

  // Seuils d'escalade et temporisations (millisecondes / nombre de fautes).
  static constexpr uint8_t  FAULT_EXT_THRESHOLD  = 5;     // disable prolongé
  static constexpr uint8_t  FAULT_PERM_THRESHOLD = 10;    // disable définitif
  static constexpr uint32_t POWER_CYCLE_MS       = 500;   // durée coupure power cycle
  static constexpr uint32_t EXTENDED_DISABLE_MS  = 30000; // 30 s de disable prolongé
  static constexpr uint32_t RECOVERY_RESET_MS    = 60000; // compteur RAZ après 60 s sains
  static constexpr uint32_t HEARTBEAT_TIMEOUT_MS   = 5000;  // silence max avant "mort"
  static constexpr uint32_t CORE0_ALIVE_TIMEOUT_MS = 4000;  // Core 0 doit signaler < 4 s

  bool isCore0Alive() const; // vrai si Core 0 a appelé notifyAlive() recemment

private:

  // Renvoie le canal i (tableau injecté en test, sinon les globaux de production).
  PowerChannel* channelAt(uint8_t i);

  uint8_t        _prevFaults;
  uint8_t        _faultCounters[5];
  uint32_t       _faultStartTime[5];  // millis() au début de chaque fault (IMP-01)
  uint32_t       _disableUntil[5];    // millis() de ré-activation (disable prolongé), 0 = actif
  bool           _heartbeatLast[5];   // dernier niveau CLK lu (détection de toggle)
  uint32_t       _heartbeatSeen[5];   // millis() du dernier battement détecté
  uint8_t          _disabledMask;
  PowerChannel**   _channels;           // nullptr = utilise les 5 globaux de production
  uint8_t          _channelCount;
  volatile uint32_t _core0AliveAt;      // millis() du dernier notifyAlive() (partagé inter-cores)
};

extern Watchdog watchdog;
