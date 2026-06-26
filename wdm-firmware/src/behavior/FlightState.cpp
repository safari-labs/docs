#include "behavior/FlightState.h"

FlightState flightState;

void FlightState::init() {
  _state   = BOOT;
  _altHead = 0;
  memset(_altHistory, 0, sizeof(_altHistory));
}

FlightState::State FlightState::current() const {
  return _state;
}

const char* FlightState::name() const {
  switch (_state) {
    case BOOT:    return "BOOT";
    case ASCENT:  return "ASCENT";
    case APOGEE:  return "APOGEE";
    case DESCENT: return "DESCENT";
    case LANDING: return "LANDING";
    default:      return "UNKNOWN";
  }
}
