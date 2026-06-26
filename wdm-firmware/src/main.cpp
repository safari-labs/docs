#include <Arduino.h>
#include "boot/BootSequence.h"
#include "behavior/Watchdog.h"
#include "behavior/FlightState.h"
#include "behavior/Telemetry.h"
#include "subsystems/IbNav.h"
#include "subsystems/ADCS.h"
#include "subsystems/Jetson.h"
#include "subsystems/TTC.h"
#include "subsystems/A7Sii.h"
#include "behavior/CommandTerminal.h"

// UNIT_TEST est défini automatiquement par PlatformIO lors de 'pio test'.
// Les fonctions setup/loop de production sont exclues : le fichier de test
// les fournit à leur place.
#ifndef UNIT_TEST

// ─────────────────────────────────────────────────────────────────────────────
// Core 0 — initialisation & télémétrie
// ─────────────────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  { uint32_t t = millis(); while (!Serial && millis() - t < 3000); }

  flightState.init();

  // Boot avant le WDT : délai total ~4.5 s, sans risque de timeout.
  bootSeq.run();

  // WDT démarré après le boot pour protéger uniquement la boucle de production.
  // init() remet l'état à zéro : il doit précéder setChannels() et markDisabled().
  // Terminal de commandes : Serial USB au banc, ttc.stream() en vol.
  terminal.init(Serial);

  watchdog.init(8000);

  // Injection des 5 canaux de production (DI) : Watchdog ne connait pas les
  // globaux de sous-systemes, ils sont fournis ici.
  static PowerChannel* prodChannels[] = { &ibNav, &adcs, &jetson, &ttc, &a7sii };
  watchdog.setChannels(prodChannels, 5);

  // Propagation des canaux échoués au boot vers le masque du Watchdog (BUG-02).
  for (uint8_t i = 0; i < 5; i++)
    if (bootSeq.isDisabled(i)) watchdog.markDisabled(i);
}

void loop() {
  watchdog.notifyAlive(); // Core 0 vivant : Core 1 peut nourrir le WDT hardware
  terminal.poll();        // lecture non-bloquante des commandes entrantes

  // Chaque sous-systeme recopie ses donnees raw vers Serial.
  // Liaisons UART en texte brut : aucun parsing ni conversion ici.
  ibNav.forwardRaw();   // trames NMEA (UART0)
  adcs.forwardRaw();    // flux ADCS  (UART1)
  jetson.forwardRaw();  // sondage I2C a 1 Hz

  // -- Telemetrie : assemblage + transmission au sol a 1 Hz --------------------
  // Collecte sante OBC -> build (sync/version/CRC) -> envoi via UART TT&C.
  // Les champs GPS/ADCS/Jetson restent a zero tant que collectGPS/ADCS/Jetson
  // ne sont pas implementes (voir TODO Telemetry).
  {
    static uint32_t lastTx = 0;
    if (millis() - lastTx >= 1000) {
      lastTx = millis();

      TelemetryPacket pkt = {};        // zero-init : champs non collectes = 0
      telemetry.collectOBCHealth(pkt); // etat de vol, uptime, fautes, batterie
      telemetry.buildPacket(pkt);      // sync 0xAA55 + version + CRC-16
      telemetry.transmit(pkt);         // 124 octets vers RFD900x (TT&C)
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Core 1 — surveillance Watchdog, dédié et indépendant de Core 0
// ─────────────────────────────────────────────────────────────────────────────

void setup1() {
  // Démarre après setup() — watchdog et subsystems déjà initialisés.
}

void loop1() {
  watchdog.kick();           // nourrit le WDT si Core 0 vivant, sinon fullSystemReset
  watchdog.checkAllFaults(); // lit les 5 pins FAULT, escalade si necessaire

  // Surveillance CLK : ADCS(1), Jetson(2), A7Sii(4) generent un signal d'activite.
  // IbNav(0) et TTC(3) retournent true immediatemement (pas de CLK en entree).
  for (uint8_t i = 0; i < 5; i++) {
    if (!watchdog.monitorHeartbeat(i)) watchdog.faultHandler(i);
  }

  delay(1000);
}

#endif // UNIT_TEST
