// test_sim_sensor_manager.cpp
// Simulates a fully-connected ADCS system using stub SensorModule subclasses.
// No real sensor hardware is needed: stubs inject hardcoded data into g_adcs
// exactly as the real modules would. Tests cover SensorManager orchestration
// and g_adcs data integrity for both "all present" and "partial failure" cases.

#include <Arduino.h>
#include <unity.h>
#include "sensors.h"
// Include sensors.cpp to bring in g_adcs and SensorManager implementation.
// test_build_src = no prevents src/ from compiling automatically, so we
// pull in the one file we actually need here.
#include "../src/sensors.cpp"

// ── Stub modules ─────────────────────────────────────────────────────────────

class FakeImuModule : public SensorModule {
    bool _ready = false;
public:
    bool init() override {
        // Inject realistic IMU data: 1 g downward, no rotation, Earth field stub
        g_adcs.imu.ax = 0.0f;  g_adcs.imu.ay = 0.0f;  g_adcs.imu.az = 9.81f;
        g_adcs.imu.gx = 0.0f;  g_adcs.imu.gy = 0.0f;  g_adcs.imu.gz = 0.01f;
        g_adcs.imu.mx = 25.0f; g_adcs.imu.my = 5.0f;  g_adcs.imu.mz = -42.0f;
        g_adcs.imu.valid = true;
        _ready = true;
        return true;
    }
    bool read() override { g_adcs.imu.valid = true; return true; }
    bool isReady()  const override { return _ready; }
    const char* name() const override { return "FakeIMU"; }
    SensorError lastError() const override { return SensorError::OK; }
};

class FakeAltimeterModule : public SensorModule {
    bool _ready = false;
public:
    bool init() override {
        g_adcs.altimeter.pressure    = 1013.25f;  // hPa at sea level
        g_adcs.altimeter.temperature = 22.5f;     // °C
        g_adcs.altimeter.altitude    = 150.0f;    // m
        g_adcs.altimeter.valid       = true;
        _ready = true;
        return true;
    }
    bool read() override { g_adcs.altimeter.valid = true; return true; }
    bool isReady()  const override { return _ready; }
    const char* name() const override { return "FakeAlt"; }
    SensorError lastError() const override { return SensorError::OK; }
};

class FakePt1000Module : public SensorModule {
    bool _ready = false;
public:
    bool init() override {
        for (uint8_t i = 0; i < 8; i++) {
            g_adcs.pt1000.temps[i] = 20.0f + i;  // 20 °C … 27 °C
            g_adcs.pt1000.valid[i] = true;
        }
        g_adcs.pt1000.active_count = 8;
        _ready = true;
        return true;
    }
    bool read() override { g_adcs.pt1000.active_count = 8; return true; }
    bool isReady()  const override { return _ready; }
    const char* name() const override { return "FakePt1000"; }
    SensorError lastError() const override { return SensorError::OK; }
};

class FakeWatchdogModule : public SensorModule {
    bool _ready = false;
public:
    bool init() override {
        g_adcs.watchdog.connected = true;
        _ready = true;
        return true;
    }
    bool read() override { g_adcs.watchdog.connected = true; return true; }
    bool isReady()  const override { return _ready; }
    const char* name() const override { return "FakeWD"; }
    SensorError lastError() const override { return SensorError::OK; }
};

// A module that always fails init() — simulates absent/broken sensor
class AbsentModule : public SensorModule {
public:
    bool init() override { return false; }
    bool read() override { return false; }
    bool isReady()  const override { return false; }
    const char* name() const override { return "Absent"; }
    SensorError lastError() const override { return SensorError::NOT_FOUND; }
};

// ── Tests ─────────────────────────────────────────────────────────────────────

// All 4 stubs init successfully; readAll populates g_adcs without crash
void test_sim_all_modules_present() {
    SensorManager manager;
    FakeImuModule       imu;
    FakeAltimeterModule alt;
    FakePt1000Module    pt;
    FakeWatchdogModule  wd;

    manager.registerModule(&imu);
    manager.registerModule(&alt);
    manager.registerModule(&pt);
    manager.registerModule(&wd);

    manager.initAll();

    TEST_ASSERT_TRUE(imu.isReady());
    TEST_ASSERT_TRUE(alt.isReady());
    TEST_ASSERT_TRUE(pt.isReady());
    TEST_ASSERT_TRUE(wd.isReady());

    manager.readAll();

    TEST_ASSERT_TRUE(g_adcs.imu.valid);
    TEST_ASSERT_TRUE(g_adcs.altimeter.valid);
    TEST_ASSERT_TRUE(g_adcs.watchdog.connected);
}

// g_adcs.imu fields reflect the values injected by FakeImuModule
void test_sim_imu_data_values() {
    SensorManager manager;
    FakeImuModule imu;
    manager.registerModule(&imu);
    manager.initAll();
    manager.readAll();

    TEST_ASSERT_FLOAT_WITHIN(0.01f, 9.81f,  g_adcs.imu.az);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 25.0f,  g_adcs.imu.mx);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, -42.0f, g_adcs.imu.mz);
    TEST_ASSERT_TRUE(g_adcs.imu.valid);
}

// g_adcs.pt1000 reflects 8 injected temperatures and active_count == 8
void test_sim_pt1000_all_channels() {
    SensorManager manager;
    FakePt1000Module pt;
    manager.registerModule(&pt);
    manager.initAll();
    manager.readAll();

    TEST_ASSERT_EQUAL(8, g_adcs.pt1000.active_count);
    for (uint8_t i = 0; i < 8; i++) {
        TEST_ASSERT_TRUE(g_adcs.pt1000.valid[i]);
        TEST_ASSERT_FLOAT_WITHIN(0.01f, 20.0f + i, g_adcs.pt1000.temps[i]);
    }
}

// An absent module does not crash initAll; readAll silently skips it
void test_sim_absent_module_skipped() {
    SensorManager manager;
    AbsentModule  absent;
    FakeImuModule imu;

    manager.registerModule(&absent);
    manager.registerModule(&imu);

    manager.initAll();

    TEST_ASSERT_FALSE(absent.isReady());
    TEST_ASSERT_TRUE(imu.isReady());

    manager.readAll();  // must not crash; absent module is silently skipped
    TEST_ASSERT_TRUE(g_adcs.imu.valid);
}

// 2 present + 2 absent: only the 2 ready modules contribute to g_adcs
void test_sim_partial_failure() {
    SensorManager manager;
    FakeImuModule       imu;
    AbsentModule        absent1;
    FakePt1000Module    pt;
    AbsentModule        absent2;

    manager.registerModule(&imu);
    manager.registerModule(&absent1);
    manager.registerModule(&pt);
    manager.registerModule(&absent2);

    manager.initAll();
    manager.readAll();

    TEST_ASSERT_TRUE(imu.isReady());
    TEST_ASSERT_FALSE(absent1.isReady());
    TEST_ASSERT_TRUE(pt.isReady());
    TEST_ASSERT_FALSE(absent2.isReady());

    TEST_ASSERT_TRUE(g_adcs.imu.valid);
    TEST_ASSERT_EQUAL(8, g_adcs.pt1000.active_count);
}

// ── Unity entry point ─────────────────────────────────────────────────────────

void setUp() {
    // Reset shared data bus before each test to avoid state leaking between tests
    g_adcs = {};
}

void tearDown() {}

void setup() {
    delay(2000);
    Serial.begin(115200);
    UNITY_BEGIN();
    RUN_TEST(test_sim_all_modules_present);
    RUN_TEST(test_sim_imu_data_values);
    RUN_TEST(test_sim_pt1000_all_channels);
    RUN_TEST(test_sim_absent_module_skipped);
    RUN_TEST(test_sim_partial_failure);
    UNITY_END();
}

void loop() {}
