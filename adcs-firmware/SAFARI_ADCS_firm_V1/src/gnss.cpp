#include "gnss.h"
#include "config.h"
#include <Wire.h>

// ── Pointers to the active GNSS instance's members ───────────────────────────
// Set by GNSS::begin() so file-scope static parsers can write to the member.
static GPSData* s_gps    = nullptr;
static bool*    s_newFix = nullptr;

// ── NMEA sentence buffer ──────────────────────────────────────────────────────
#define NMEA_MAX_LEN    128
static char    nmeaBuf[NMEA_MAX_LEN];
static uint8_t nmeaIdx = 0;
static bool    inSentence = false;

// ── Helpers ───────────────────────────────────────────────────────────────────

/* Verify NMEA checksum.  Sentence must NOT include leading '$'. */
static bool nmeaChecksum(const char* s) {
  uint8_t calc = 0;
  int i = 0;
  while (s[i] && s[i] != '*') calc ^= (uint8_t)s[i++];
  if (s[i] != '*') return true;   // no checksum field → accept
  uint8_t expected = (uint8_t)strtol(&s[i + 1], nullptr, 16);
  return calc == expected;
}

/* Split a comma-delimited NMEA field by index (0 = talker+sentence type). */
static void nmeaField(const char* sentence, uint8_t idx, char* out, uint8_t outLen) {
  out[0] = '\0';
  uint8_t field = 0;
  const char* p = sentence;
  while (*p && field < idx) {
    if (*p++ == ',') field++;
  }
  if (field < idx || !*p) return;
  uint8_t i = 0;
  while (*p && *p != ',' && *p != '*' && i < outLen - 1) out[i++] = *p++;
  out[i] = '\0';
}

/*
 * Convert raw NMEA lat/lon (DDMM.MMMMM or DDDMM.MMMMM)
 * + hemisphere char ('N','S','E','W') → decimal degrees.
 */
static double nmeaCoord(const char* raw, char hemi) {
  if (!raw || raw[0] == '\0') return 0.0;
  double val = atof(raw);
  int    deg = (int)(val / 100);
  double min = val - deg * 100.0;
  double dec = deg + min / 60.0;
  if (hemi == 'S' || hemi == 'W') dec = -dec;
  return dec;
}

/* Parse $GNGGA / $GPGGA */
static void parseGGA(const char* s) {
  char f[20];

  // Field 1 — UTC time (HHMMSS.ss)
  nmeaField(s, 1, f, sizeof(f));
  if (f[0]) {
    s_gps->hour   = (f[0]-'0')*10 + (f[1]-'0');
    s_gps->minute = (f[2]-'0')*10 + (f[3]-'0');
    s_gps->second = (f[4]-'0')*10 + (f[5]-'0');
  }

  // Fields 2-5 — latitude/longitude
  char lat[14], latH[3], lon[14], lonH[3];
  nmeaField(s, 2, lat,  sizeof(lat));
  nmeaField(s, 3, latH, sizeof(latH));
  nmeaField(s, 4, lon,  sizeof(lon));
  nmeaField(s, 5, lonH, sizeof(lonH));
  s_gps->latitude  = nmeaCoord(lat, latH[0]);
  s_gps->longitude = nmeaCoord(lon, lonH[0]);

  // Field 6 — fix quality
  nmeaField(s, 6, f, sizeof(f));
  s_gps->fixQuality = f[0] ? atoi(f) : 0;
  s_gps->valid = (s_gps->fixQuality > 0);
  if (s_gps->valid && s_newFix) *s_newFix = true;

  // Field 7 — satellites in use
  nmeaField(s, 7, f, sizeof(f));
  s_gps->satellites = f[0] ? atoi(f) : 0;

  // Field 9 — altitude (MSL)
  nmeaField(s, 9, f, sizeof(f));
  s_gps->altitudeM = f[0] ? atof(f) : 0.0;
}

/* Parse $GNRMC / $GPRMC */
static void parseRMC(const char* s) {
  char f[20];

  // Field 1 — UTC time
  nmeaField(s, 1, f, sizeof(f));
  if (f[0]) {
    s_gps->hour   = (f[0]-'0')*10 + (f[1]-'0');
    s_gps->minute = (f[2]-'0')*10 + (f[3]-'0');
    s_gps->second = (f[4]-'0')*10 + (f[5]-'0');
  }

  // Field 2 — status A/V
  nmeaField(s, 2, f, sizeof(f));
  s_gps->valid = (f[0] == 'A');
  if (s_gps->valid && s_newFix) *s_newFix = true;

  // Fields 3-6 — lat/lon
  char lat[14], latH[3], lon[14], lonH[3];
  nmeaField(s, 3, lat,  sizeof(lat));
  nmeaField(s, 4, latH, sizeof(latH));
  nmeaField(s, 5, lon,  sizeof(lon));
  nmeaField(s, 6, lonH, sizeof(lonH));
  s_gps->latitude  = nmeaCoord(lat, latH[0]);
  s_gps->longitude = nmeaCoord(lon, lonH[0]);

  // Field 7 — speed over ground (knots)
  nmeaField(s, 7, f, sizeof(f));
  s_gps->speedKnots = f[0] ? atof(f) : 0.0;

  // Field 8 — course over ground
  nmeaField(s, 8, f, sizeof(f));
  s_gps->courseDeg = f[0] ? atof(f) : 0.0;

  // Field 9 — date DDMMYY
  nmeaField(s, 9, f, sizeof(f));
  if (f[0]) {
    s_gps->day   = (f[0]-'0')*10 + (f[1]-'0');
    s_gps->month = (f[2]-'0')*10 + (f[3]-'0');
    s_gps->year  = 2000 + (f[4]-'0')*10 + (f[5]-'0');
  }
}

/* Parse $GNGSA / $GPGSA */
static void parseGSA(const char* s) {
  char f[6];
  nmeaField(s, 2, f, sizeof(f));   // field 2 = fix type 1/2/3
  if (f[0]) s_gps->fixType = atoi(f);
}

/* Route a complete NMEA sentence (without '$') to the right parser. */
static void dispatchNMEA(const char* s) {
  if (!nmeaChecksum(s)) return;   // drop bad checksums silently

  // The sentence type is always 5 chars after talker id (GPGGA, GNGGA, etc.)
  // We match on the last 3 chars of the type word for talker-agnostic matching.
  const char* type = strchr(s, 'G');   // find first G (start of sentence type)
  if (!type) return;
  // Actually: sentence looks like "GNGGA,..." — advance past talker prefix (2 chars)
  const char* msgType = s + 2;         // skip talker (GN, GP, GL, GA …)

  if      (strncmp(msgType, "GGA", 3) == 0) parseGGA(s);
  else if (strncmp(msgType, "RMC", 3) == 0) parseRMC(s);
  else if (strncmp(msgType, "GSA", 3) == 0) parseGSA(s);
  // GLL, VTG, GSV etc. are ignored — add parsers here if needed
}

/* Feed one byte from the I2C stream into the NMEA sentence builder. */
static void feedByte(uint8_t b) {
  // The M9N fills unused I2C bytes with 0xFF — ignore them
  if (b == 0xFF) return;

  if (b == '$') {
    inSentence = true;
    nmeaIdx    = 0;
    return;
  }

  if (!inSentence) return;

  if (b == '\r' || b == '\n') {
    if (nmeaIdx > 0) {
      nmeaBuf[nmeaIdx] = '\0';
      dispatchNMEA(nmeaBuf);
    }
    inSentence = false;
    nmeaIdx    = 0;
    return;
  }

  if (nmeaIdx < NMEA_MAX_LEN - 1) {
    nmeaBuf[nmeaIdx++] = (char)b;
  } else {
    // Overrun → discard sentence
    inSentence = false;
    nmeaIdx    = 0;
  }
}

// ── GNSS Class Implementation ────────────────────────────────────────────────

GNSS::GNSS() : newFix(false) {}

/*
 * Send a complete UBX frame over UART1 to the M9N's UART config port.
 * NMEA data is still read via I2C — the M9N handles both ports independently.
 */
bool GNSS::sendUBX(const uint8_t* msg, uint8_t len) {
  return Serial1.write(msg, len) == len;
}

/*
 * UBX-CFG-VALSET — set CFG-NAVSPG-DYNMODEL (key 0x20110021) to `model`.
 * Writes to RAM + BBR + Flash so the setting survives power cycles.
 *
 * Frame layout (17 bytes total):
 *   B5 62          — sync chars
 *   06 8A          — class / ID  (UBX-CFG-VALSET)
 *   09 00          — payload length = 9
 *   00             — version
 *   07             — layers: RAM(b0) | BBR(b1) | Flash(b2)
 *   00 00          — reserved
 *   21 00 11 20    — key 0x20110021 little-endian
 *   <model>        — dynModel value (U1)
 *   CK_A CK_B      — 8-bit Fletcher checksum over bytes[2..14]
 */
bool GNSS::setDynModel(uint8_t model) {
  uint8_t msg[17] = {
    0xB5, 0x62,              // sync
    0x06, 0x8A,              // UBX-CFG-VALSET
    0x09, 0x00,              // payload length
    0x00,                    // version
    0x07,                    // layers: RAM + BBR + Flash
    0x00, 0x00,              // reserved
    0x21, 0x00, 0x11, 0x20, // CFG-NAVSPG-DYNMODEL key (LE)
    model,                   // dynModel value
    0x00, 0x00               // checksum placeholder
  };

  uint8_t ck_a = 0, ck_b = 0;
  for (uint8_t i = 2; i < 15; i++) {
    ck_a += msg[i];
    ck_b += ck_a;
  }
  msg[15] = ck_a;
  msg[16] = ck_b;

  return sendUBX(msg, sizeof(msg));
}

bool GNSS::begin() {
  s_gps    = &gps;
  s_newFix = &newFix;

  // I2C presence check
  Wire.beginTransmission(GNSS_I2C_ADDR);
  if (Wire.endTransmission() != 0) {
    return false;
  }

  // UART config port — used only for outgoing UBX commands
  Serial1.setTX(GNSS_UART_TX_PIN);
  Serial1.setRX(GNSS_UART_RX_PIN);
  Serial1.begin(GNSS_UART_BAUD);

  delay(100);   // allow M9N to finish any pending NMEA burst before config
  return setDynModel(UBX_DYNMODEL_AIRBORNE_2G);
}

void GNSS::update() {
  newFix = false;
  // ── Step 1: ask how many bytes are waiting ──────────────────────────────
  // Registers 0xFD (MSB) and 0xFE (LSB) hold the number of available bytes.
  uint16_t available = 0;
  Wire.beginTransmission(GNSS_I2C_ADDR);
  Wire.write(0xFD);
  Wire.endTransmission(false);   // repeated start
  Wire.requestFrom(GNSS_I2C_ADDR, (uint8_t)2);
  if (Wire.available() >= 2) {
    available  = (uint16_t)Wire.read() << 8;
    available |= Wire.read();
  }

  // ── Step 2: read up to 255 bytes at a time until the buffer is drained ──
  while (available > 0) {
    uint8_t chunk = (available > 255) ? 255 : (uint8_t)available;
    Wire.requestFrom(GNSS_I2C_ADDR, chunk);
    while (Wire.available()) feedByte((uint8_t)Wire.read());
    available = (available > chunk) ? available - chunk : 0;
  }
}

const GPSData& GNSS::getData() const {
  return gps;
}

bool GNSS::hasNewFix() const {
  return newFix;
}
