#include <Arduino.h>
#include <Wire.h>
#include "config.h"
#include "gnss.h"

GNSS gnss;

void setup() {
    Serial.begin(SERIAL_BAUDRATE);
    delay(2000);

    Wire.begin();
    Wire.setClock(I2C_CLOCK_HZ);

    if (!gnss.begin()) {
        Serial.println("M9N not found on I2C 0x42");
        while (true) delay(1000);
    }
    Serial.println("GNSS OK");
}

void loop() {
    gnss.update();
    if (gnss.hasNewFix()) {
        const GPSData& d = gnss.getData();
        Serial.printf("%.6f, %.6f  alt=%.1fm  sats=%d\n",
                      d.latitude, d.longitude, d.altitudeM, d.satellites);
    }
    delay(10);
}
