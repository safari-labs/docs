#pragma once
#include <Arduino.h>

class FlightState {
public:
  enum State : uint8_t { BOOT, ASCENT, APOGEE, DESCENT, LANDING };

  void        init();
  State       current() const;
  const char* name()    const;

  // TODO: void update(float altitudeM, float verticalSpeedMs);
  // TODO: void applyProfile();
  // TODO: bool detectApogee();   — utilise _altHistory interne
  // TODO: bool detectLanding(float altM, float vspeedMs, uint32_t durationMs);
  // TODO: void setTelemetryRate();

private:
  State    _state;
  float    _altHistory[16]; // historique d'altitude pour détection apogée (fenêtre glissante)
  uint8_t  _altHead;        // indice d'écriture dans le buffer circulaire
};

extern FlightState flightState;
