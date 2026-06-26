#include <Arduino.h>
#include <stddef.h>
#include <unity.h>
#include "behavior/Telemetry.h"

// Instance locale, isolee du global de production.
static Telemetry tlm;

void setUp()    {}
void tearDown() {}

// =============================================================================
// TC-CRC — CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, pas de reflexion)
// Vecteurs verifies par calcul de reference (Python).
// =============================================================================

void test_crc16_known_vector_123() {
  uint8_t buf[] = { 0x31, 0x32, 0x33 };   // "123"
  TEST_ASSERT_EQUAL_HEX16(0x5BCE, tlm.computeCRC16(buf, 3));
}

void test_crc16_empty_buffer() {
  uint8_t buf[1] = { 0 };
  TEST_ASSERT_EQUAL_HEX16(0xFFFF, tlm.computeCRC16(buf, 0)); // valeur initiale
}

void test_crc16_single_zero_byte() {
  uint8_t buf[] = { 0x00 };
  TEST_ASSERT_EQUAL_HEX16(0xE1F0, tlm.computeCRC16(buf, 1));
}

void test_crc16_vector_aa55() {
  uint8_t buf[] = { 0xAA, 0x55 };
  TEST_ASSERT_EQUAL_HEX16(0xE5EA, tlm.computeCRC16(buf, 2));
}

void test_crc16_changes_when_data_changes() {
  uint8_t a[] = { 0xAA, 0x55 };
  uint8_t b[] = { 0xAA, 0x56 };
  TEST_ASSERT_NOT_EQUAL(tlm.computeCRC16(a, 2), tlm.computeCRC16(b, 2));
}

// =============================================================================
// TC-PKT — Structure et integrite du paquet de telemetrie
// =============================================================================

void test_packet_size_is_124() {
  TEST_ASSERT_EQUAL(124, sizeof(TelemetryPacket));
}

void test_packet_sync_header_set_by_buildPacket() {
  TelemetryPacket pkt = {};
  tlm.buildPacket(pkt);
  TEST_ASSERT_EQUAL_HEX8(0xAA, pkt.sync[0]);
  TEST_ASSERT_EQUAL_HEX8(0x55, pkt.sync[1]);
}

void test_packet_version_set_by_buildPacket() {
  TelemetryPacket pkt = {};
  tlm.buildPacket(pkt);
  TEST_ASSERT_EQUAL_HEX8(0x01, pkt.version);
}

void test_packet_crc_is_valid_after_build() {
  TelemetryPacket pkt = {};
  tlm.buildPacket(pkt);
  uint16_t crc = tlm.computeCRC16(reinterpret_cast<const uint8_t*>(&pkt),
                                  sizeof(pkt) - sizeof(pkt.crc16));
  TEST_ASSERT_EQUAL_HEX16(crc, pkt.crc16);
}

void test_packet_crc_detects_corruption() {
  TelemetryPacket pkt = {};
  tlm.buildPacket(pkt);
  uint16_t stored = pkt.crc16;
  pkt.lat = 42.0f;                    // corruption d'un champ couvert par le CRC
  uint16_t recomputed = tlm.computeCRC16(reinterpret_cast<const uint8_t*>(&pkt),
                                         sizeof(pkt) - sizeof(pkt.crc16));
  TEST_ASSERT_NOT_EQUAL(stored, recomputed);
}

void test_packet_float_fields_4byte_aligned() {
  TEST_ASSERT_EQUAL(0, offsetof(TelemetryPacket, lat)         % 4);
  TEST_ASSERT_EQUAL(0, offsetof(TelemetryPacket, altGPS)      % 4);
  TEST_ASSERT_EQUAL(0, offsetof(TelemetryPacket, altBaro)     % 4);
  TEST_ASSERT_EQUAL(0, offsetof(TelemetryPacket, accelX)      % 4);
  TEST_ASSERT_EQUAL(0, offsetof(TelemetryPacket, gyroX)       % 4);
  TEST_ASSERT_EQUAL(0, offsetof(TelemetryPacket, roll)        % 4);
  TEST_ASSERT_EQUAL(0, offsetof(TelemetryPacket, temp)        % 4);
  TEST_ASSERT_EQUAL(0, offsetof(TelemetryPacket, jetsonTemp)  % 4);
  TEST_ASSERT_EQUAL(0, offsetof(TelemetryPacket, battVoltage) % 4);
}

static int runAllTests() {
  UNITY_BEGIN();
  // TC-CRC
  RUN_TEST(test_crc16_known_vector_123);
  RUN_TEST(test_crc16_empty_buffer);
  RUN_TEST(test_crc16_single_zero_byte);
  RUN_TEST(test_crc16_vector_aa55);
  RUN_TEST(test_crc16_changes_when_data_changes);
  // TC-PKT
  RUN_TEST(test_packet_size_is_124);
  RUN_TEST(test_packet_sync_header_set_by_buildPacket);
  RUN_TEST(test_packet_version_set_by_buildPacket);
  RUN_TEST(test_packet_crc_is_valid_after_build);
  RUN_TEST(test_packet_crc_detects_corruption);
  RUN_TEST(test_packet_float_fields_4byte_aligned);
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
