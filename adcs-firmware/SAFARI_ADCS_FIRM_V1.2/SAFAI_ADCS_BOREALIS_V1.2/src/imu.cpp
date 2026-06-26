#include "imu.h"

// Wire1 is not exported by this Mbed variant — create an I2C1 instance on GPIO6/7
static TwoWire _wire1(PIN_IMU_SDA, PIN_IMU_SCL);

bool ImuModule::init() {
    _ready     = false;
    _failCount = 0;

    // AD0 pulled LOW → fixed I2C address 0x68, never changes at runtime
    pinMode(PIN_IMU_AD0, OUTPUT);
    digitalWrite(PIN_IMU_AD0, LOW);

    _wire1.begin();
    _wire1.setClock(IMU_I2C_FREQ);

    if (!_icm.begin_I2C(IMU_I2C_ADDR, &_wire1)) {
        _error = SensorError::NOT_FOUND;
        Serial.println("[IMU] not found");
        return false;
    }

    _icm.setAccelRange(ICM20948_ACCEL_RANGE_4_G);
    _icm.setGyroRange(ICM20948_GYRO_RANGE_500_DPS);
    _icm.setMagDataRate(AK09916_MAG_DATARATE_10_HZ);

    _error = SensorError::OK;
    _ready = true;
    Serial.println("[IMU] OK");
    return true;
}

bool ImuModule::read() {
    if (!_ready) return false;

    sensors_event_t accel, gyro, temp, mag;
    _icm.getEvent(&accel, &gyro, &temp, &mag);

    // All-zero acceleration is a reliable sentinel for a failed read on ICM-20948
    float amag2 = accel.acceleration.x * accel.acceleration.x
                + accel.acceleration.y * accel.acceleration.y
                + accel.acceleration.z * accel.acceleration.z;

    if (amag2 == 0.0f) {
        _error = SensorError::DATA_INVALID;
        g_adcs.imu.valid = false;
        if (++_failCount >= 3) {
            // Recovery policy: 3 consecutive failures → notify watchdog
            // WatchdogComm::sendStatus() called from SensorManager after this returns false
        }
        return false;
    }

    _failCount       = 0;
    _error           = SensorError::OK;
    g_adcs.imu.ax    = accel.acceleration.x;
    g_adcs.imu.ay    = accel.acceleration.y;
    g_adcs.imu.az    = accel.acceleration.z;
    g_adcs.imu.gx    = gyro.gyro.x;
    g_adcs.imu.gy    = gyro.gyro.y;
    g_adcs.imu.gz    = gyro.gyro.z;
    g_adcs.imu.mx    = mag.magnetic.x;
    g_adcs.imu.my    = mag.magnetic.y;
    g_adcs.imu.mz    = mag.magnetic.z;
    g_adcs.imu.valid = true;
    return true;
}
