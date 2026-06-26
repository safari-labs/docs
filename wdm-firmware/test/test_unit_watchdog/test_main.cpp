#include <Arduino.h>
#include <unity.h>
#include "behavior/Watchdog.h"
#include "MockPowerChannel.h"

// Instances locales — isolées du watchdog global de production.
static Watchdog           wdt;
static MockPowerChannel   ch0("Ch0");
static MockPowerChannel   ch1("Ch1");
static MockPowerChannel   ch2("Ch2");
static PowerChannel*      channels[] = { &ch0, &ch1, &ch2 };

void setUp() {
  ch0.setFault(false);
  ch1.setFault(false);
  ch2.setFault(false);
  ch0.resetCalls();
  ch1.resetCalls();
  ch2.resetCalls();
  wdt.init(8000);
  wdt.setChannels(channels, 3);
}

void tearDown() {}

// Helper : enchaine n cycles faute -> clear sur un canal pour faire monter le
// compteur d'escalade. (Au-dela du seuil de disable prolonge, le canal est
// ignore : les cycles suivants n'incrementent plus le compteur.)
static void driveFaultCycles(MockPowerChannel& ch, int n) {
  for (int i = 0; i < n; i++) {
    ch.setFault(true);  wdt.checkAllFaults();
    ch.setFault(false); wdt.checkAllFaults();
  }
}

// --- TC-INIT : état interne après init() ---

void test_init_prevFaults_cleared() {
  ch0.setFault(true);
  wdt.checkAllFaults();                        // enregistre la faute dans _prevFaults
  TEST_ASSERT_NOT_EQUAL(0, wdt.getPrevFaults() & 0x01);
  wdt.init(8000);
  wdt.setChannels(channels, 3);
  TEST_ASSERT_EQUAL(0, wdt.getPrevFaults());   // init() remet à zéro
}

void test_init_faultCounters_cleared() {
  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(0));
  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(1));
  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(2));
}

void test_init_disabledMask_cleared() {
  TEST_ASSERT_EQUAL(0, wdt.getDisabledMask());
}

// --- TC-KICK : appels à kick() sans crash ---

void test_kick_no_crash() {
  wdt.kick();
  TEST_ASSERT_TRUE(true);
}

void test_kick_repeated() {
  for (int i = 0; i < 10; i++) wdt.kick();
  TEST_ASSERT_TRUE(true);
}

// --- TC-CHECK : logique de détection de faute ---

void test_check_no_fault_no_record() {
  wdt.checkAllFaults();
  TEST_ASSERT_EQUAL(0, wdt.getPrevFaults());
}

void test_check_fault_detected() {
  ch0.setFault(true);
  wdt.checkAllFaults();
  TEST_ASSERT_NOT_EQUAL(0, wdt.getPrevFaults() & 0x01);
}

void test_check_fault_cleared() {
  ch0.setFault(true);  wdt.checkAllFaults();  // transition → FAULT
  ch0.setFault(false); wdt.checkAllFaults();  // transition → CLEAR
  TEST_ASSERT_EQUAL(0, wdt.getPrevFaults() & 0x01);
}

void test_check_two_faults_simultaneous() {
  ch0.setFault(true);
  ch1.setFault(true);
  wdt.checkAllFaults();
  TEST_ASSERT_EQUAL(0x03, wdt.getPrevFaults() & 0x03);
}

void test_check_disabled_channel_skipped() {
  wdt.markDisabled(0);
  ch0.setFault(true);   // ch0 est en faute, mais désactivé
  wdt.checkAllFaults();
  TEST_ASSERT_EQUAL(0, wdt.getPrevFaults() & 0x01); // bit 0 non enregistré
}

void test_check_fault_oscillation() {
  for (int i = 0; i < 3; i++) {
    ch0.setFault(true);  wdt.checkAllFaults();
    TEST_ASSERT_NOT_EQUAL(0, wdt.getPrevFaults() & 0x01);
    ch0.setFault(false); wdt.checkAllFaults();
    TEST_ASSERT_EQUAL(0, wdt.getPrevFaults() & 0x01);
  }
}

void test_check_no_duplicate_fault_in_steady_state() {
  ch0.setFault(true);
  wdt.checkAllFaults();           // premier appel : FAULT enregistré
  uint8_t snap = wdt.getPrevFaults();
  wdt.checkAllFaults();           // deuxième appel : état inchangé
  TEST_ASSERT_EQUAL(snap, wdt.getPrevFaults());
}

void test_check_getName_correct() {
  TEST_ASSERT_EQUAL_STRING("Ch0", ch0.getName());
  TEST_ASSERT_EQUAL_STRING("Ch1", ch1.getName());
  TEST_ASSERT_EQUAL_STRING("Ch2", ch2.getName());
}

void test_check_zero_channel_count() {
  wdt.setChannels(channels, 0);   // aucun canal — ne doit pas crasher
  wdt.checkAllFaults();
  TEST_ASSERT_EQUAL(0, wdt.getPrevFaults());
}

// =============================================================================
// TC-COUNT — Compteur de fautes (BUG-01)
// =============================================================================

void test_faultCounter_increments_on_rising_edge() {
  ch0.setFault(true);
  wdt.checkAllFaults();
  TEST_ASSERT_EQUAL(1, wdt.getFaultCount(0));
}

void test_faultCounter_no_increment_in_steady_fault() {
  ch0.setFault(true);
  wdt.checkAllFaults();                 // front montant : compteur = 1
  wdt.checkAllFaults();                 // etat stable : pas de double comptage
  TEST_ASSERT_EQUAL(1, wdt.getFaultCount(0));
}

void test_faultCounter_no_decrement_on_clear() {
  ch0.setFault(true);  wdt.checkAllFaults();
  ch0.setFault(false); wdt.checkAllFaults();   // le clear ne remet pas a zero
  TEST_ASSERT_EQUAL(1, wdt.getFaultCount(0));
}

void test_faultCounter_accumulates_across_cycles() {
  driveFaultCycles(ch0, 3);
  TEST_ASSERT_EQUAL(3, wdt.getFaultCount(0));
}

void test_faultCounter_independent_per_channel() {
  driveFaultCycles(ch0, 2);
  driveFaultCycles(ch1, 1);
  TEST_ASSERT_EQUAL(2, wdt.getFaultCount(0));
  TEST_ASSERT_EQUAL(1, wdt.getFaultCount(1));
  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(2));
}

void test_faultCounter_disabled_channel_not_counted() {
  wdt.markDisabled(0);
  ch0.setFault(true);
  wdt.checkAllFaults();
  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(0));
}

// =============================================================================
// TC-MASK — Propagation du masque desactive (BUG-02)
// =============================================================================

void test_markDisabled_sets_mask_bit() {
  wdt.markDisabled(0);
  TEST_ASSERT_NOT_EQUAL(0, wdt.getDisabledMask() & 0x01);
}

void test_watchdog_skips_channel_from_boot_fail() {
  wdt.markDisabled(2);          // simule un echec de boot Jetson
  ch2.setFault(true);
  wdt.checkAllFaults();
  TEST_ASSERT_EQUAL(0, wdt.getPrevFaults() & (1 << 2));
}

// =============================================================================
// TC-ESC — Reponse graduee : faultHandler / escalate / resetFaultCounter
// Seuils reels : <5 power cycle, >=5 disable prolonge, >=10 disable definitif.
// =============================================================================

void test_escalate_power_cycle_records_cycle_calls() {
  driveFaultCycles(ch0, 4);              // 4 fronts montants, tous < seuil
  TEST_ASSERT_EQUAL(4, ch0.cycleCalls());
  TEST_ASSERT_EQUAL(0, ch0.disableCalls());
  TEST_ASSERT_EQUAL(0, wdt.getDisableUntil(0)); // pas encore de disable prolonge
}

void test_escalate_extended_disable_at_threshold() {
  driveFaultCycles(ch0, 5);              // le 5e front declenche le disable prolonge
  TEST_ASSERT_EQUAL(5, wdt.getFaultCount(0));
  TEST_ASSERT_NOT_EQUAL(0, wdt.getDisableUntil(0));  // timer de re-activation arme
  TEST_ASSERT_TRUE(ch0.disableCalls() >= 1);
}

void test_extended_disabled_channel_skipped() {
  driveFaultCycles(ch0, 5);              // ch0 passe en disable prolonge
  uint8_t before = wdt.getFaultCount(0);
  ch0.setFault(true);                    // la faute persiste...
  wdt.checkAllFaults();                  // ...mais le canal est ignore (timer actif)
  TEST_ASSERT_EQUAL(before, wdt.getFaultCount(0)); // compteur fige
}

void test_resetFaultCounter_clears_counter() {
  driveFaultCycles(ch0, 3);
  TEST_ASSERT_EQUAL(3, wdt.getFaultCount(0));
  wdt.resetFaultCounter(0);
  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(0));
}

void test_resetFaultCounter_isolated_per_channel() {
  driveFaultCycles(ch0, 3);
  driveFaultCycles(ch1, 2);
  wdt.resetFaultCounter(0);
  TEST_ASSERT_EQUAL(0, wdt.getFaultCount(0));
  TEST_ASSERT_EQUAL(2, wdt.getFaultCount(1));  // ch1 intact
}

void test_faultHandler_noop_on_disabled_channel() {
  wdt.markDisabled(0);
  ch0.resetCalls();
  wdt.faultHandler(0);                   // canal hors service : aucune action
  TEST_ASSERT_EQUAL(0, ch0.cycleCalls());
  TEST_ASSERT_EQUAL(0, ch0.disableCalls());
}

// =============================================================================
// TC-HB — monitorHeartbeat : garde sur index invalide (lecture GPIO non testable)
// =============================================================================

void test_monitorHeartbeat_invalid_channel_returns_false() {
  TEST_ASSERT_FALSE(wdt.monitorHeartbeat(5));   // hors limites (5 canaux : 0-4)
  TEST_ASSERT_FALSE(wdt.monitorHeartbeat(99));
}

static int runAllTests() {
  UNITY_BEGIN();

  RUN_TEST(test_init_prevFaults_cleared);
  RUN_TEST(test_init_faultCounters_cleared);
  RUN_TEST(test_init_disabledMask_cleared);
  RUN_TEST(test_kick_no_crash);
  RUN_TEST(test_kick_repeated);
  RUN_TEST(test_check_no_fault_no_record);
  RUN_TEST(test_check_fault_detected);
  RUN_TEST(test_check_fault_cleared);
  RUN_TEST(test_check_two_faults_simultaneous);
  RUN_TEST(test_check_disabled_channel_skipped);
  RUN_TEST(test_check_fault_oscillation);
  RUN_TEST(test_check_no_duplicate_fault_in_steady_state);
  RUN_TEST(test_check_getName_correct);
  RUN_TEST(test_check_zero_channel_count);

  // TC-COUNT — compteur de fautes
  RUN_TEST(test_faultCounter_increments_on_rising_edge);
  RUN_TEST(test_faultCounter_no_increment_in_steady_fault);
  RUN_TEST(test_faultCounter_no_decrement_on_clear);
  RUN_TEST(test_faultCounter_accumulates_across_cycles);
  RUN_TEST(test_faultCounter_independent_per_channel);
  RUN_TEST(test_faultCounter_disabled_channel_not_counted);

  // TC-MASK — masque desactive
  RUN_TEST(test_markDisabled_sets_mask_bit);
  RUN_TEST(test_watchdog_skips_channel_from_boot_fail);

  // TC-ESC — reponse graduee
  RUN_TEST(test_escalate_power_cycle_records_cycle_calls);
  RUN_TEST(test_escalate_extended_disable_at_threshold);
  RUN_TEST(test_extended_disabled_channel_skipped);
  RUN_TEST(test_resetFaultCounter_clears_counter);
  RUN_TEST(test_resetFaultCounter_isolated_per_channel);
  RUN_TEST(test_faultHandler_noop_on_disabled_channel);

  // TC-HB — monitorHeartbeat (garde)
  RUN_TEST(test_monitorHeartbeat_invalid_channel_returns_false);

  return UNITY_END();
}

#ifdef ARDUINO
// Cible Pico : Unity tourne dans setup(), loop() reste vide.
void setup() {
  Serial.begin(115200);
  { uint32_t t = millis(); while (!Serial && millis() - t < 3000); }
  runAllTests();
}
void loop() {}
#else
// Cible native (PC) : point d'entree standard.
int main() { return runAllTests(); }
#endif
