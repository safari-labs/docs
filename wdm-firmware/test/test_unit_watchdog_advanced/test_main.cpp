// Scenarios complementaires a test_unit_watchdog/test_main.cpp.
// Prerequis : _mockMillis() (Arduino.h mock) pour injector le temps sans delays reels.
//
// TC-TIME   : re-enable apres expiration du timer, recuperation apres RECOVERY_RESET_MS
// TC-ESC-03 : disable definitif a cnt=10 (deferred dans la suite principale ; possible ici
//             en avancant le temps pour franchir les periodes de disable prolonge)
// TC-FSR    : fullSystemReset() coupe tous les canaux
// TC-DIRECT : faultHandler() appele directement (pas via checkAllFaults)
// TC-MULTI  : deux canaux escaladant independamment
// TC-EDGE   : gardes hors-limites
//
// Commande : pio test -e native

#include <Arduino.h>
#include <unity.h>
#include "behavior/Watchdog.h"
#include "../test_unit_watchdog/MockPowerChannel.h"

static Watchdog         wdt;
static MockPowerChannel ch0("Ch0");
static MockPowerChannel ch1("Ch1");
static MockPowerChannel ch2("Ch2");
static PowerChannel*    channels[] = { &ch0, &ch1, &ch2 };

void setUp() {
  _mockMillis() = 0;
  ch0.setFault(false); ch1.setFault(false); ch2.setFault(false);
  ch0.resetCalls();    ch1.resetCalls();    ch2.resetCalls();
  wdt.init(8000);
  wdt.setChannels(channels, 3);
}

void tearDown() {
  _mockMillis() = 0;
}

// Conduit n cycles faute->clear pour incrementer le compteur du canal.
static void driveFaultCycles(MockPowerChannel& ch, int n) {
  for (int i = 0; i < n; i++) {
    ch.setFault(true);  wdt.checkAllFaults();
    ch.setFault(false); wdt.checkAllFaults();
  }
}

// =============================================================================
// TC-TIME — Comportements dependants du temps (injection via _mockMillis())
// =============================================================================

// Apres expiration du timer de disable prolonge, le canal est re-surveille et
// une nouvelle faute incremente le compteur (de 5 a 6).
void test_reena_channel_monitored_after_timer_expires() {
  driveFaultCycles(ch0, 5);                              // ch0 -> disable prolonge
  TEST_ASSERT_NOT_EQUAL(0, wdt.getDisableUntil(0));

  // Avancer le temps au-dela de EXTENDED_DISABLE_MS.
  _mockMillis() = Watchdog::EXTENDED_DISABLE_MS + 5000; // 35 000 ms

  // Falling edge avec re-enable : disableUntil efface, prevFaults[0] mis a 0.
  ch0.setFault(false);
  wdt.checkAllFaults();
  TEST_ASSERT_EQUAL(0, wdt.getDisableUntil(0));

  // Nouvelle faute : rising edge -> cnt passe de 5 a 6.
  ch0.resetCalls();
  ch0.setFault(true);
  wdt.checkAllFaults();
  TEST_ASSERT_EQUAL(6, wdt.getFaultCount(0));
  TEST_ASSERT_NOT_EQUAL(0, wdt.getDisableUntil(0));  // nouveau disable prolonge
}

// Apres RECOVERY_RESET_MS ms sans faute, checkAllFaults() remet le compteur a 0.
void test_recov_counter_reset_after_healthy_period() {
  driveFaultCycles(ch0, 3);
  TEST_ASSERT_EQUAL(3, wdt.getFaultCount(0));

  _mockMillis() = Watchdog::RECOVERY_RESET_MS + 10000; // 70 000 ms — bien au-dela

  ch0.setFault(false);
  wdt.checkAllFaults(); // declenche la branche RECOVER
  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(0));
}

// La recuperation ne touche pas les autres canaux.
void test_recov_counter_reset_isolated_per_channel() {
  driveFaultCycles(ch0, 2);
  driveFaultCycles(ch1, 3);

  _mockMillis() = Watchdog::RECOVERY_RESET_MS + 10000;

  ch0.setFault(false);
  ch1.setFault(false);
  wdt.checkAllFaults();

  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(0));
  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(1));
  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(2)); // ch2 n'avait pas de compteur
}

// La recuperation ne se declenche pas avant l'expiration du delai.
void test_recov_not_triggered_before_timeout() {
  driveFaultCycles(ch0, 3);
  _mockMillis() = Watchdog::RECOVERY_RESET_MS / 2; // seulement 30 s
  ch0.setFault(false);
  wdt.checkAllFaults();
  TEST_ASSERT_EQUAL(3, wdt.getFaultCount(0)); // compteur intact
}

// =============================================================================
// TC-ESC-03 — Disable definitif apres 10 fautes (impossible en HW reel sans
// injection de temps ; faisable ici en avancant _mockMillis() apres chaque
// periode de disable prolonge pour laisser le canal se re-activer).
// =============================================================================

void test_escalate_permanent_disable_at_10_faults() {
  // A chaque iteration : avancer le temps pour expirer le disable prolonge en
  // cours, puis piloter un cycle faute->clear pour incrementer le compteur.
  for (int i = 0; i < 10; i++) {
    _mockMillis() += Watchdog::EXTENDED_DISABLE_MS + 1;
    ch0.setFault(false); wdt.checkAllFaults(); // re-enable + falling edge si necessaire
    ch0.setFault(true);  wdt.checkAllFaults(); // rising edge : cnt++
    ch0.setFault(false); wdt.checkAllFaults(); // essaie falling edge (ignore si timer actif)
  }

  // Apres 10 fronts montants, escalate() a appele markDisabled(0).
  TEST_ASSERT_NOT_EQUAL(0, wdt.getDisabledMask() & 0x01);
  // ch1 et ch2 non touches.
  TEST_ASSERT_EQUAL(0, wdt.getDisabledMask() & 0x06);
}

// =============================================================================
// TC-FSR — fullSystemReset() coupe tous les canaux avant le reboot
// (watchdog_reboot() est un no-op dans le mock natif)
// =============================================================================

void test_full_system_reset_disables_all_channels() {
  wdt.fullSystemReset();
  TEST_ASSERT_EQUAL(1, ch0.disableCalls());
  TEST_ASSERT_EQUAL(1, ch1.disableCalls());
  TEST_ASSERT_EQUAL(1, ch2.disableCalls());
}

void test_full_system_reset_with_zero_channels_no_crash() {
  wdt.setChannels(channels, 0);
  wdt.fullSystemReset(); // aucun canal -> pas de crash
  TEST_ASSERT_TRUE(true);
}

// =============================================================================
// TC-DIRECT — faultHandler() appele directement (sans checkAllFaults)
//
// Contrat : faultHandler() N'incremente PAS le compteur — c'est checkAllFaults
// qui le fait sur le front montant. Avec cnt=0, escalate() choisit power cycle.
// =============================================================================

void test_faultHandler_direct_triggers_cycle_at_count_zero() {
  wdt.faultHandler(0);
  TEST_ASSERT_EQUAL(1, ch0.cycleCalls());
  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(0)); // compteur inchange par faultHandler
}

// Appels repetes : le compteur reste a 0, on reste au niveau power cycle.
void test_faultHandler_direct_repeated_stays_at_cycle_level() {
  wdt.faultHandler(0);
  wdt.faultHandler(0);
  wdt.faultHandler(0);
  TEST_ASSERT_EQUAL(3, ch0.cycleCalls());
  TEST_ASSERT_EQUAL(0, wdt.getDisableUntil(0)); // jamais passe en disable prolonge
}

// Sur un canal definitivement desactive, faultHandler() ne fait rien.
void test_faultHandler_noop_after_permanent_disable() {
  wdt.markDisabled(0);
  wdt.faultHandler(0);
  TEST_ASSERT_EQUAL(0, ch0.cycleCalls());
  TEST_ASSERT_EQUAL(0, ch0.disableCalls());
}

// Appel avec index >= 5 : retour immediat sans crash.
void test_faultHandler_out_of_bounds_no_crash() {
  wdt.faultHandler(5);
  wdt.faultHandler(255);
  TEST_ASSERT_TRUE(true);
}

// =============================================================================
// TC-MULTI — Deux canaux escaladant independamment
// =============================================================================

// ch0 en disable prolonge, ch1 encore en phase power-cycle : les timers et
// compteurs ne se melangent pas.
void test_multi_channels_escalate_independently() {
  driveFaultCycles(ch0, 5); // ch0 -> disable prolonge
  driveFaultCycles(ch1, 2); // ch1 -> 2 power cycles (cnt=2 < seuil)

  TEST_ASSERT_NOT_EQUAL(0, wdt.getDisableUntil(0)); // ch0 bloque
  TEST_ASSERT_EQUAL(0, wdt.getDisableUntil(1));     // ch1 toujours actif
  TEST_ASSERT_EQUAL(5, wdt.getFaultCount(0));
  TEST_ASSERT_EQUAL(2, wdt.getFaultCount(1));
  TEST_ASSERT_EQUAL(2, ch1.cycleCalls());
}

// Le disable definitif d'un canal ne positionne pas les bits des autres.
void test_perm_disable_bits_do_not_bleed_to_other_channels() {
  wdt.markDisabled(0);
  wdt.markDisabled(2);
  TEST_ASSERT_NOT_EQUAL(0, wdt.getDisabledMask() & 0x01);
  TEST_ASSERT_EQUAL(0,     wdt.getDisabledMask() & 0x02); // ch1 intact
  TEST_ASSERT_NOT_EQUAL(0, wdt.getDisabledMask() & 0x04);
}

// Apres disable prolonge de ch0, une faute sur ch1 est toujours detectee
// et incrementee normalement.
void test_fault_on_ch1_detected_while_ch0_extended_disabled() {
  driveFaultCycles(ch0, 5); // ch0 en disable prolonge
  ch0.resetCalls();

  ch1.setFault(true);
  wdt.checkAllFaults();

  TEST_ASSERT_EQUAL(1, wdt.getFaultCount(1));  // ch1 compte normalement
  TEST_ASSERT_EQUAL(0, ch0.cycleCalls());      // ch0 toujours ignore
}

// =============================================================================
// TC-EDGE — Gardes et cas limites
// =============================================================================

void test_null_channels_checkAllFaults_no_crash() {
  wdt.setChannels(nullptr, 0);
  wdt.checkAllFaults();
  TEST_ASSERT_EQUAL(0, wdt.getPrevFaults());
}

void test_resetFaultCounter_out_of_bounds_no_crash() {
  wdt.resetFaultCounter(5);
  wdt.resetFaultCounter(255);
  TEST_ASSERT_TRUE(true);
}

void test_getFaultCount_out_of_bounds_returns_zero() {
  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(5));
  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(255));
}

void test_getDisableUntil_out_of_bounds_returns_zero() {
  TEST_ASSERT_EQUAL(0, wdt.getDisableUntil(5));
  TEST_ASSERT_EQUAL(0, wdt.getDisableUntil(255));
}

// =============================================================================
// Point d'entree
// =============================================================================

static int runAllTests() {
  UNITY_BEGIN();

  // TC-TIME
  RUN_TEST(test_reena_channel_monitored_after_timer_expires);
  RUN_TEST(test_recov_counter_reset_after_healthy_period);
  RUN_TEST(test_recov_counter_reset_isolated_per_channel);
  RUN_TEST(test_recov_not_triggered_before_timeout);

  // TC-ESC-03
  RUN_TEST(test_escalate_permanent_disable_at_10_faults);

  // TC-FSR
  RUN_TEST(test_full_system_reset_disables_all_channels);
  RUN_TEST(test_full_system_reset_with_zero_channels_no_crash);

  // TC-DIRECT
  RUN_TEST(test_faultHandler_direct_triggers_cycle_at_count_zero);
  RUN_TEST(test_faultHandler_direct_repeated_stays_at_cycle_level);
  RUN_TEST(test_faultHandler_noop_after_permanent_disable);
  RUN_TEST(test_faultHandler_out_of_bounds_no_crash);

  // TC-MULTI
  RUN_TEST(test_multi_channels_escalate_independently);
  RUN_TEST(test_perm_disable_bits_do_not_bleed_to_other_channels);
  RUN_TEST(test_fault_on_ch1_detected_while_ch0_extended_disabled);

  // TC-EDGE
  RUN_TEST(test_null_channels_checkAllFaults_no_crash);
  RUN_TEST(test_resetFaultCounter_out_of_bounds_no_crash);
  RUN_TEST(test_getFaultCount_out_of_bounds_returns_zero);
  RUN_TEST(test_getDisableUntil_out_of_bounds_returns_zero);

  return UNITY_END();
}

#ifdef ARDUINO
void setup() {
  Serial.begin(115200);
  { uint32_t t = millis(); while (!Serial && millis() - t < 3000); }
  runAllTests();
}
void loop() {}
#else
int main() { return runAllTests(); }
#endif
