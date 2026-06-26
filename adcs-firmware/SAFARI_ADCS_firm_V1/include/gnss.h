#ifndef GNSS_H
#define GNSS_H

#include <stdint.h>

// ── UBX dynamic-model constants (CFG-NAVSPG-DYNMODEL, key 0x20110021) ────────
// Sent via UBX-CFG-VALSET (class 0x06, ID 0x8A) — M9N new config interface.
#define UBX_DYNMODEL_PORTABLE      0
#define UBX_DYNMODEL_STATIONARY    2
#define UBX_DYNMODEL_PEDESTRIAN    3
#define UBX_DYNMODEL_AUTOMOTIVE    4
#define UBX_DYNMODEL_SEA           5
#define UBX_DYNMODEL_AIRBORNE_1G   6   // high-alt balloon
#define UBX_DYNMODEL_AIRBORNE_2G   7   // UAV / drone
#define UBX_DYNMODEL_AIRBORNE_4G   8   // rocket / aggressive flight

// ── GPS Data Structure ───────────────────────────────────────────────────────
struct GPSData {
  // Position
  double  latitude   = 0.0;   // decimal degrees, + N / − S
  double  longitude  = 0.0;   // decimal degrees, + E / − W
  double  altitudeM  = 0.0;   // metres above MSL
  // Status
  uint8_t fixQuality = 0;     // GGA: 0=none,1=GPS,2=DGPS …
  uint8_t fixType    = 1;     // GSA: 1=none,2=2D,3=3D
  uint8_t satellites = 0;
  // Motion
  double  speedKnots = 0.0;
  double  courseDeg  = 0.0;
  // Time (UTC from last RMC/GGA)
  uint8_t hour = 0, minute = 0, second = 0;
  // Date (from RMC)
  uint8_t day = 0, month = 0;
  uint16_t year = 0;
  // Raw validity
  bool    valid = false;       // 'A' from RMC or fixQuality > 0 from GGA
};

// ── GNSS Module ─────────────────────────────────────────────────────────────
class GNSS {
public:
  GNSS();
  bool begin();
  void update();
  const GPSData& getData() const;
  bool hasNewFix() const;

private:
  GPSData gps;
  bool newFix;

  bool sendUBX(const uint8_t* msg, uint8_t len);
  bool setDynModel(uint8_t model);
};

#endif // GNSS_H
