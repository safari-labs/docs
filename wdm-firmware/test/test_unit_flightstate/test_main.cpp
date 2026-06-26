#include <Arduino.h>
#include <string.h>
#include <unity.h>
#include "behavior/FlightState.h"

// Instance locale, isolee du global de production.
static FlightState fs;

void setUp()    { fs.init(); }
void tearDown() {}

// =============================================================================
// TC-FSM — Etat initial et noms (code present : init / current / name)
// Note : _state est prive et aucun setter public n'existe encore (update() est
// TODO), donc seul l'etat BOOT est atteignable -> TC-FSM-03..06 sont differes.
// =============================================================================

void test_flightstate_init_state_is_boot() {
  TEST_ASSERT_EQUAL(FlightState::BOOT, fs.current());
}

void test_flightstate_name_boot() {
  TEST_ASSERT_EQUAL_STRING("BOOT", fs.name());
}

void test_flightstate_name_not_null() {
  TEST_ASSERT_NOT_NULL(fs.name());
}

void test_flightstate_init_idempotent() {
  fs.init();
  fs.init();
  TEST_ASSERT_EQUAL(FlightState::BOOT, fs.current());
  TEST_ASSERT_EQUAL_STRING("BOOT", fs.name());
}

static int runAllTests() {
  UNITY_BEGIN();
  RUN_TEST(test_flightstate_init_state_is_boot);
  RUN_TEST(test_flightstate_name_boot);
  RUN_TEST(test_flightstate_name_not_null);
  RUN_TEST(test_flightstate_init_idempotent);
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
