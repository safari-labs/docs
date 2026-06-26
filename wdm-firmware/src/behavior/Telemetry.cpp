#include "behavior/Telemetry.h"
#include "behavior/Watchdog.h"
#include "behavior/FlightState.h"
#include "subsystems/TTC.h"

Telemetry telemetry;

// CRC-16-CCITT : polynôme 0x1021, valeur initiale 0xFFFF, bit de poids fort traité en premier.
// Algorithme standard pour les liaisons série et les protocoles de télémétrie.
uint16_t Telemetry::computeCRC16(const uint8_t* buf, size_t len) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < len; i++) {
    crc ^= (uint16_t)buf[i] << 8; // injecte l'octet dans les bits hauts
    for (uint8_t j = 0; j < 8; j++)
      crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : (crc << 1);
  }
  return crc;
}

// Remplit les champs de sante de l'OBC (RP2040). Les sources GPS/ADCS/Jetson
// sont collectees separement (collectGPS/ADCS/Jetson, encore TODO).
void Telemetry::collectOBCHealth(TelemetryPacket& pkt) {
  pkt.flightState = (uint8_t)flightState.current();
  pkt.uptime      = millis();
  pkt.faultFlags  = watchdog.getPrevFaults(); // 1 bit par canal en faute active
  // TODO: lecture batterie via ADC dedie (broche + pont diviseur a definir).
  pkt.battVoltage = 0.0f;
}

void Telemetry::buildPacket(TelemetryPacket& pkt) {
  pkt.sync[0] = 0xAA;  // en-tête de synchronisation pour le récepteur RFD900x
  pkt.sync[1] = 0x55;
  pkt.version = 0x01;
  // CRC calculé sur TOUS les champs sauf le champ crc16 lui-même (2 derniers octets)
  pkt.crc16   = computeCRC16(reinterpret_cast<const uint8_t*>(&pkt),
                              sizeof(pkt) - sizeof(pkt.crc16));
}

// Envoi du paquet complet au sol via le lien TT&C (RFD900x).
void Telemetry::transmit(TelemetryPacket& pkt) {
  ttc.transmit(reinterpret_cast<const uint8_t*>(&pkt), sizeof(pkt));
}
