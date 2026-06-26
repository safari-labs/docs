// Tests unitaires pour CommandTerminal.
// TestHardwareSerial permet d'injecter des commandes et de capturer les reponses
// sans aucun materiel physique.
//
// Commande : pio test -e native

#include <Arduino.h>
#include <unity.h>
#include <string.h>
#include <stdio.h>
#include "subsystems/PowerChannel.h"
#include "behavior/Watchdog.h"
#include "behavior/CommandTerminal.h"

// =============================================================================
// MockPowerChannel minimal pour cette suite
// =============================================================================
class MockPowerChannel : public PowerChannel {
public:
  explicit MockPowerChannel(const char* n)
    : PowerChannel(0, 0, n), _fault(false), _dis(0), _cyc(0), _en(0) {}
  void setFault(bool f) { _fault = f; }
  bool isFault()  const override { return _fault; }
  void disable()        override { _dis++; }
  void cycle(uint32_t)  override { _cyc++; }
  void enable()         override { _en++;  }
  int  disableCalls()   const { return _dis; }
private:
  bool _fault;
  int  _dis, _cyc, _en;
};

// =============================================================================
// TestHardwareSerial — port serie injectable
// pushInput() enfile des octets que poll() lira via available()/read().
// Les reponses (println) sont capturees dans _out.
// =============================================================================
class TestHardwareSerial : public HardwareSerial {
public:
  void pushInput(const char* s) {
    for (size_t i = 0; s[i] && _inLen < (int)sizeof(_in) - 1; i++)
      _in[_inLen++] = s[i];
  }

  bool outputContains(const char* s) const { return strstr(_out, s) != nullptr; }
  const char* output() const { return _out; }

  void clearAll() {
    memset(_in,  0, sizeof(_in));
    memset(_out, 0, sizeof(_out));
    _inLen = _inPos = _outLen = 0;
  }

  int  available() override { return (_inPos < _inLen) ? 1 : 0; }
  int  read()      override { return (_inPos < _inLen) ? (uint8_t)_in[_inPos++] : -1; }

  void println(const char* s) override {
    int room = (int)sizeof(_out) - _outLen - 2;
    if (room > 0) {
      int n = snprintf(_out + _outLen, room, "%s\n", s);
      if (n > 0) _outLen += n;
    }
  }
  void println() override {
    if (_outLen < (int)sizeof(_out) - 1) _out[_outLen++] = '\n';
  }

private:
  char _in[256]    = {};
  char _out[2048]  = {};
  int  _inLen = 0, _inPos = 0, _outLen = 0;
};

// =============================================================================
// Fixtures globales
// =============================================================================
static TestHardwareSerial  port;
static CommandTerminal      term;
static MockPowerChannel     ch0("IbNav"), ch1("ADCS"),   ch2("Jetson"),
                            ch3("TTC"),   ch4("A7Sii");
static PowerChannel* chs[] = { &ch0, &ch1, &ch2, &ch3, &ch4 };

void setUp() {
  port.clearAll();
  _mockMillis() = 0;
  ch0.setFault(false); ch1.setFault(false); ch2.setFault(false);
  ch3.setFault(false); ch4.setFault(false);
  watchdog.init(8000);
  watchdog.setChannels(chs, 5);
  term.init(port);
}

void tearDown() {}

// Helper : efface le tampon, enfile la commande + '\n', execute poll().
static void send(const char* cmd) {
  port.clearAll();
  port.pushInput(cmd);
  port.pushInput("\n");
  term.poll();
}

// =============================================================================
// TC-TERM-POLL — comportement de base
// =============================================================================

void test_poll_empty_no_crash() {
  term.poll();
  TEST_ASSERT_TRUE(true);
}

void test_poll_partial_no_dispatch() {
  port.pushInput("hel"); // pas de '\n' -> pas de dispatch
  term.poll();
  TEST_ASSERT_FALSE(port.outputContains("---"));
}

// =============================================================================
// TC-TERM-CMD — commandes connues
// =============================================================================

void test_help_responds() {
  send("help");
  TEST_ASSERT_TRUE(port.outputContains("help"));
  TEST_ASSERT_TRUE(port.outputContains("status"));
  TEST_ASSERT_TRUE(port.outputContains("reboot"));
}

void test_status_contains_fields() {
  send("status");
  TEST_ASSERT_TRUE(port.outputContains("faults="));
  TEST_ASSERT_TRUE(port.outputContains("mask="));
  TEST_ASSERT_TRUE(port.outputContains("uptime="));
}

void test_counters_lists_all_channels() {
  send("counters");
  TEST_ASSERT_TRUE(port.outputContains("IbNav"));
  TEST_ASSERT_TRUE(port.outputContains("ADCS"));
  TEST_ASSERT_TRUE(port.outputContains("Jetson"));
  TEST_ASSERT_TRUE(port.outputContains("TTC"));
  TEST_ASSERT_TRUE(port.outputContains("A7Sii"));
}

void test_state_responds() {
  send("state");
  TEST_ASSERT_TRUE(port.outputContains("state="));
  TEST_ASSERT_TRUE(port.outputContains("BOOT"));
}

void test_kick_responds_ok() {
  send("kick");
  TEST_ASSERT_TRUE(port.outputContains("OK"));
}

// =============================================================================
// TC-TERM-RESET — reset <ch>
// =============================================================================

void test_reset_valid_clears_counter() {
  ch0.setFault(true);  watchdog.checkAllFaults();
  ch0.setFault(false); watchdog.checkAllFaults();
  ch0.setFault(true);  watchdog.checkAllFaults();
  ch0.setFault(false); watchdog.checkAllFaults();
  TEST_ASSERT_EQUAL(2, watchdog.getFaultCount(0));

  send("reset 0");
  TEST_ASSERT_EQUAL(0, watchdog.getFaultCount(0));
  TEST_ASSERT_TRUE(port.outputContains("OK"));
}

void test_reset_invalid_channel_returns_error() {
  send("reset 5");
  TEST_ASSERT_TRUE(port.outputContains("ERR"));
}

void test_reset_each_valid_channel_accepted() {
  for (int i = 0; i <= 4; i++) {
    char cmd[10];
    port.clearAll();
    snprintf(cmd, sizeof(cmd), "reset %d", i);
    send(cmd);
    TEST_ASSERT_FALSE_MESSAGE(port.outputContains("ERR"), cmd);
  }
}

// =============================================================================
// TC-TERM-DISABLE — disable <ch>
// =============================================================================

void test_disable_valid_sets_mask() {
  send("disable 2");
  TEST_ASSERT_NOT_EQUAL(0, watchdog.getDisabledMask() & (1 << 2));
  TEST_ASSERT_TRUE(port.outputContains("OK"));
}

void test_disable_invalid_channel_returns_error() {
  send("disable 5");
  TEST_ASSERT_TRUE(port.outputContains("ERR"));
}

void test_disabled_channel_shown_in_counters() {
  watchdog.markDisabled(1); // ADCS
  send("counters");
  TEST_ASSERT_TRUE(port.outputContains("DEFINITIF"));
}

// =============================================================================
// TC-TERM-ERR — commandes inconnues / mal formees
// =============================================================================

void test_unknown_command_returns_error() {
  send("foo");
  TEST_ASSERT_TRUE(port.outputContains("ERR"));
  TEST_ASSERT_TRUE(port.outputContains("inconnue"));
}

void test_reboot_without_confirm_is_unknown() {
  send("reboot");
  TEST_ASSERT_TRUE(port.outputContains("ERR")); // "confirm" manquant
}

void test_empty_line_no_response() {
  port.pushInput("\n");
  term.poll();
  TEST_ASSERT_FALSE(port.outputContains("OK"));
  TEST_ASSERT_FALSE(port.outputContains("ERR"));
}

// =============================================================================
// TC-TERM-ROBUSTNESS
// =============================================================================

void test_very_long_input_no_crash() {
  char big[201];
  memset(big, 'x', 200);
  big[200] = '\0';
  port.pushInput(big);
  port.pushInput("\n");
  term.poll(); // ne doit pas crasher ni deborder
  TEST_ASSERT_TRUE(true);
}

void test_multiple_commands_in_sequence() {
  port.pushInput("help\nstatus\nstate\n");
  term.poll();
  TEST_ASSERT_TRUE(port.outputContains("faults="));
  TEST_ASSERT_TRUE(port.outputContains("BOOT"));
}

void test_cr_lf_terminates_command() {
  port.pushInput("kick\r\n");
  term.poll();
  TEST_ASSERT_TRUE(port.outputContains("OK"));
}

// =============================================================================
// Point d'entree
// =============================================================================
static int runAllTests() {
  UNITY_BEGIN();
  RUN_TEST(test_poll_empty_no_crash);
  RUN_TEST(test_poll_partial_no_dispatch);
  RUN_TEST(test_help_responds);
  RUN_TEST(test_status_contains_fields);
  RUN_TEST(test_counters_lists_all_channels);
  RUN_TEST(test_state_responds);
  RUN_TEST(test_kick_responds_ok);
  RUN_TEST(test_reset_valid_clears_counter);
  RUN_TEST(test_reset_invalid_channel_returns_error);
  RUN_TEST(test_reset_each_valid_channel_accepted);
  RUN_TEST(test_disable_valid_sets_mask);
  RUN_TEST(test_disable_invalid_channel_returns_error);
  RUN_TEST(test_disabled_channel_shown_in_counters);
  RUN_TEST(test_unknown_command_returns_error);
  RUN_TEST(test_reboot_without_confirm_is_unknown);
  RUN_TEST(test_empty_line_no_response);
  RUN_TEST(test_very_long_input_no_crash);
  RUN_TEST(test_multiple_commands_in_sequence);
  RUN_TEST(test_cr_lf_terminates_command);
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
