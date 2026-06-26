#include "behavior/CommandTerminal.h"
#include "behavior/Watchdog.h"
#include "behavior/FlightState.h"
#include <string.h>
#include <stdio.h>
#include <stdarg.h>

CommandTerminal terminal;

static const char* CH_NAME[5] = { "IbNav", "ADCS", "Jetson", "TTC", "A7Sii" };

void CommandTerminal::init(HardwareSerial& port) {
  _port = &port;
  _len  = 0;
  memset(_buf, 0, sizeof(_buf));
}

// Lecture non-bloquante : accumule les octets jusqu'a '\r' ou '\n' puis dispatch.
void CommandTerminal::poll() {
  if (!_port) return;
  while (_port->available()) {
    char c = (char)_port->read();
    if (c == '\r' || c == '\n') {
      if (_len > 0) {
        _buf[_len] = '\0';
        dispatch();
        _len = 0;
      }
    } else if (_len < CMD_BUF_SIZE - 1) {
      _buf[_len++] = c;
    }
    // Si le buffer est plein sans '\n' : caracteres excess ignores silencieusement.
  }
}

void CommandTerminal::respond(const char* msg) {
  if (_port) _port->println(msg);
}

void CommandTerminal::respondFmt(const char* fmt, ...) {
  char line[80];
  va_list args;
  va_start(args, fmt);
  vsnprintf(line, sizeof(line), fmt, args);
  va_end(args);
  respond(line);
}

// =============================================================================
// Dispatcher — analyse _buf et execute la commande.
// =============================================================================
void CommandTerminal::dispatch() {

  // ── help ────────────────────────────────────────────────────────────────────
  if (strcmp(_buf, "help") == 0) {
    respond("--- Commandes disponibles ---");
    respond("  help                  liste des commandes");
    respond("  status                etat global (faults, mask, uptime)");
    respond("  counters              compteurs de fautes par canal");
    respond("  reset <0-4>           remet a zero le compteur d'un canal");
    respond("  disable <0-4>         desactive definitivement un canal");
    respond("  kick                  nourrit manuellement le WDT");
    respond("  state                 etat de vol actuel");
    respond("  reboot confirm        reset complet du systeme (IRREVERSIBLE)");
    respond("-----------------------------");

  // ── status ──────────────────────────────────────────────────────────────────
  } else if (strcmp(_buf, "status") == 0) {
    respondFmt("faults=0x%02X  mask=0x%02X  alive=%s  uptime=%lus",
               watchdog.getPrevFaults(),
               watchdog.getDisabledMask(),
               watchdog.isCore0Alive() ? "yes" : "NO",
               (unsigned long)(millis() / 1000));

  // ── counters ─────────────────────────────────────────────────────────────────
  } else if (strcmp(_buf, "counters") == 0) {
    for (uint8_t i = 0; i < 5; i++) {
      bool disabled = watchdog.getDisabledMask() & (1 << i);
      uint32_t until = watchdog.getDisableUntil(i);
      respondFmt("  ch%u %-6s  cnt=%-3u  %s",
                 i, CH_NAME[i],
                 watchdog.getFaultCount(i),
                 disabled ? "[DISABLE DEFINITIF]" :
                 until    ? "[disable prolonge]"  : "OK");
    }

  // ── reset <ch> ──────────────────────────────────────────────────────────────
  } else if (strncmp(_buf, "reset ", 6) == 0) {
    int ch = _buf[6] - '0';
    if (ch < 0 || ch > 4) { respond("ERR canal: 0 a 4"); return; }
    watchdog.resetFaultCounter((uint8_t)ch);
    respondFmt("OK: compteur ch%d (%s) remis a zero", ch, CH_NAME[ch]);

  // ── disable <ch> ────────────────────────────────────────────────────────────
  } else if (strncmp(_buf, "disable ", 8) == 0) {
    int ch = _buf[8] - '0';
    if (ch < 0 || ch > 4) { respond("ERR canal: 0 a 4"); return; }
    watchdog.markDisabled((uint8_t)ch);
    respondFmt("OK: ch%d (%s) desactive definitivement", ch, CH_NAME[ch]);

  // ── kick ─────────────────────────────────────────────────────────────────────
  } else if (strcmp(_buf, "kick") == 0) {
    watchdog.kick();
    respond("OK: WDT kicke");

  // ── state ────────────────────────────────────────────────────────────────────
  } else if (strcmp(_buf, "state") == 0) {
    respondFmt("state=%s  uptime=%lus",
               flightState.name(),
               (unsigned long)(millis() / 1000));

  // ── reboot confirm ───────────────────────────────────────────────────────────
  } else if (strcmp(_buf, "reboot confirm") == 0) {
    respond("REBOOT: arret de tous les canaux puis reset RP2040...");
    watchdog.fullSystemReset(); // ne retourne jamais sur materiel reel

  // ── commande inconnue ────────────────────────────────────────────────────────
  } else {
    respondFmt("ERR: commande inconnue \"%s\" (help)", _buf);
  }
}
