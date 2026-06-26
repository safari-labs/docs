#include "boot/BootSequence.h"
#include "subsystems/IbNav.h"
#include "subsystems/ADCS.h"
#include "subsystems/Jetson.h"
#include "subsystems/TTC.h"
#include "subsystems/A7Sii.h"

BootSequence bootSeq;

// Marque le canal comme définitivement désactivé dans _disabledMask.
// Le Watchdog lit ce masque pour exclure les canaux défaillants de sa surveillance.
void BootSequence::_markDisabled(uint8_t channel) {
  _disabledMask |= (1 << channel);
  Serial.print("[BOOT] Channel ");
  Serial.print(channel);
  Serial.println(" DISABLED");
}

// Affiche le message de démarrage du module et attend le délai de stabilisation
// avant que la comm soit tentée. Le paramètre channel est réservé pour les
// fonctions de test (testTTC, testIbNav…) à implémenter.
void BootSequence::_bootModule(const char* name, uint8_t channel, uint32_t stabilizeMs) {
  Serial.print("[BOOT] Powering ");
  Serial.println(name);
  delay(stabilizeMs);
  (void)channel;
}

bool BootSequence::isDisabled(uint8_t channel) const {
  return _disabledMask & (1 << channel);
}

// Séquence d'allumage ordonnée pour limiter l'appel de courant au démarrage.
// Ordre : TT&C en premier (radio dispo pour les alertes d'urgence dès le boot),
//         puis capteurs de navigation, puis calcul embarqué et caméra.
// Chaque module : init() configure les GPIO → enable() active l'alimentation
//   → délai de stabilisation → test de comm (TODO) → désactivation si échec.
void BootSequence::run() {
  _disabledMask = 0;
  Serial.println("[BOOT] Starting power-on sequence");

  // Canal 3 — TTC/RFD900x : 500 ms suffisent pour l'initialisation radio
  ttc.init();
  ttc.enable();
  _bootModule("TTC", 3, 500);
  // TODO: if (!testTTC()) { ttc.disable(); _markDisabled(3); }
  Serial.println("[BOOT] TTC OK");

  // Canal 0 — IbNav (GPS) : 1000 ms pour l'acquisition de l'horloge UART
  ibNav.init();
  ibNav.enable();
  _bootModule("IbNav", 0, 1000);
  // TODO: if (!testIbNav()) { ibNav.disable(); _markDisabled(0); }
  Serial.println("[BOOT] IbNav OK");

  // Canal 1 — ADCS (IMU + baro) : 500 ms pour la calibration interne
  adcs.init();
  adcs.enable();
  _bootModule("ADCS", 1, 500);
  // TODO: if (!testADCS()) { adcs.disable(); _markDisabled(1); }
  Serial.println("[BOOT] ADCS OK");

  // Canal 2 — Jetson : 2000 ms minimum pour que Linux soit prêt sur I2C
  jetson.init();
  jetson.enable();
  _bootModule("Jetson", 2, 2000);
  // TODO: if (!testJetson()) { jetson.disable(); _markDisabled(2); }
  Serial.println("[BOOT] Jetson OK");

  // Canal 4 — A7Sii (caméra) : 500 ms pour l'initialisation interne
  a7sii.init();
  a7sii.enable();
  _bootModule("A7Sii", 4, 500);
  // TODO: if (!testA7Sii()) { a7sii.disable(); _markDisabled(4); }
  Serial.println("[BOOT] A7Sii OK");

  Serial.println("[BOOT] Sequence complete");
}
