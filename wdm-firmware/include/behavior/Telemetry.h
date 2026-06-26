#pragma once
#include <Arduino.h>

// Paquet de télémétrie transmis au sol via RFD900x (TT&C).
// Les champs float sont maintenus à des offsets multiples de 4 pour respecter
// les contraintes d'alignement du Cortex-M0+ (pas d'accès non-aligné).
// Des champs _pad[] explicites assurent cet alignement sous #pragma pack(push,1).
// Le CRC couvre tous les octets SAUF les 2 derniers (champ crc16 lui-même).
//
// Layout (offsets dans le paquet fil) :
//   0   sync[2]       1   version    3   flightState
//   4   uptime        8   lat       12   lon
//  16   altGPS       20   speed     24   heading
//  28   gpsFix       29   gpsSats   30   _pad0[2]
//  32   altBaro      36   pressure
//  40   accelX       44   accelY    48   accelZ
//  52   gyroX        56   gyroY     60   gyroZ
//  64   roll         68   pitch     72   yaw
//  76   temp[8]  (32 B)
// 108   jetsonStatus 109  jetsonCPU 110  _pad1[2]
// 112   jetsonTemp  116   battVoltage
// 120   faultFlags  121   _pad2     122  crc16
// Total : 124 bytes
#pragma pack(push, 1)
struct TelemetryPacket {
  uint8_t  sync[2];      // 0xAA 0x55 — marqueur de début de trame
  uint8_t  version;      // version du format de paquet
  uint8_t  flightState;  // état de vol courant (enum FlightState::State)
  uint32_t uptime;       // millisecondes depuis le démarrage (millis())

  // GPS (IbNav) — offsets 8-29
  float    lat, lon;     // degrés décimaux
  float    altGPS;       // altitude GPS en mètres
  float    speed;        // vitesse sol en m/s
  float    heading;      // cap en degrés
  uint8_t  gpsFix;       // 0 = pas de fix, 1 = fix 2D, 2 = fix 3D
  uint8_t  gpsSats;      // nombre de satellites visibles
  uint8_t  _pad0[2];     // alignement : altBaro → offset 32

  // Baro/IMU (ADCS) — offsets 32-107
  float    altBaro;      // altitude barométrique en mètres   (offset 32 ✓)
  float    pressure;     // pression atmosphérique en hPa
  float    accelX, accelY, accelZ;
  float    gyroX,  gyroY,  gyroZ;
  float    roll, pitch, yaw;
  float    temp[8];      // 8 capteurs de température en °C

  // Jetson — offsets 108-119
  uint8_t  jetsonStatus; // 0 = hors ligne, 1 = actif
  uint8_t  jetsonCPU;    // utilisation CPU en % (0–100)
  uint8_t  _pad1[2];     // alignement : jetsonTemp → offset 112
  float    jetsonTemp;   // température CPU Jetson en °C       (offset 112 ✓)

  // OBC — offsets 116-123
  float    battVoltage;  // tension batterie en V               (offset 116 ✓)
  uint8_t  faultFlags;   // bitmask des fautes actives (1 bit par canal)
  uint8_t  _pad2;        // alignement : crc16 → offset 122
  uint16_t crc16;        // CRC-16-CCITT calculé sur les 122 octets précédents
};
#pragma pack(pop)

class Telemetry {
public:
  uint16_t computeCRC16(const uint8_t* buf, size_t len);
  void     collectOBCHealth(TelemetryPacket& pkt); // etat de vol, uptime, fautes, batterie
  void     buildPacket(TelemetryPacket& pkt);      // sync + version + CRC
  void     transmit(TelemetryPacket& pkt);         // envoi via UART TT&C (RFD900x)

  // TODO: void collectGPS(TelemetryPacket&);
  // TODO: void collectADCS(TelemetryPacket&);
  // TODO: void collectJetson(TelemetryPacket&);
  // TODO: void alert(const char* message);
};

extern Telemetry telemetry;
