// test_pt1000_sim_gpio.cpp
// Validates the full Pt1000 acquisition chain: GPIO stimulus → ADC → Vout → LUT → °C.
//
// HARDWARE REQUIRED
// -----------------
//   One bare wire bridging two Pico header pins:
//
//       Pico pin 20 (GP15)  ────wire────  Pico pin 31 (GP26 / ADC0)
//
//   GP15 is used as the voltage source (OUTPUT HIGH = 3.3 V, LOW = 0 V).
//   GP26 is the ADC input normally driven by the Pt1000 circuit.
//
// What this tests
// ---------------
//   HIGH → raw ≈ 1023 → Vout ≈ 3.3 V → LUT floor → T ≈ +79 °C (top of range)
//   LOW  → raw ≈ 0    → Vout ≈  0 V  → LUT floor → T ≈ −59 °C (bottom of range)
//
//   test_sim_wire_connected runs first: if the delta between HIGH and LOW reads
//   is < 800 LSB the wire is absent and all remaining tests will fail with a
//   clear message rather than misleading ADC noise failures.

#include <Arduino.h>
#include <unity.h>
#include "config.h"

// GP15 = Pico physical pin 20
static constexpr uint8_t PIN_STIM = 15;

// ── Local copy of calibration constants (must match pt1000.cpp) ──────────────

static constexpr float    T_CAL_MIN   = -60.0f;
static constexpr float    T_CAL_MAX   =  80.0f;
static constexpr float    T_CAL_STEP  = (T_CAL_MAX - T_CAL_MIN) / 199.0f;
static constexpr uint16_t LUT_SIZE    = 200;
static constexpr float    SIM_VREF    = 3.3f;
static constexpr int      SIM_ADC_MAX = 1023;

static const float LUT_V[LUT_SIZE] = {
    -0.0145323133f, -0.0014268930f,  0.0116616706f,  0.0247334224f,  0.0377884069f,
     0.0508266685f,  0.0638482514f,  0.0768531993f,  0.0898415560f,  0.1028133647f,
     0.1157686685f,  0.1287075105f,  0.1416299332f,  0.1545359791f,  0.1674256903f,
     0.1802991087f,  0.1931562762f,  0.2059972340f,  0.2188220236f,  0.2316306858f,
     0.2444232615f,  0.2571997912f,  0.2699603152f,  0.2827048735f,  0.2954335062f,
     0.3081462527f,  0.3208431526f,  0.3335242449f,  0.3461895686f,  0.3588391625f,
     0.3714730651f,  0.3840913147f,  0.3966939493f,  0.4092810068f,  0.4218525249f,
     0.4344085409f,  0.4469490921f,  0.4594742155f,  0.4719839478f,  0.4844783256f,
     0.4969573853f,  0.5094211629f,  0.5218696944f,  0.5343030156f,  0.5467211620f,
     0.5591241687f,  0.5715120710f,  0.5838849038f,  0.5962427017f,  0.6085854991f,
     0.6209133304f,  0.6332262297f,  0.6455242308f,  0.6578073673f,  0.6700756728f,
     0.6823291806f,  0.6945679236f,  0.7067919349f,  0.7190012469f,  0.7311958923f,
     0.7433759034f,  0.7555413121f,  0.7676921505f,  0.7798284502f,  0.7919502428f,
     0.8040575595f,  0.8161504315f,  0.8282288897f,  0.8402929650f,  0.8523426878f,
     0.8643780886f,  0.8763991976f,  0.8884060447f,  0.9003986597f,  0.9123770724f,
     0.9243413122f,  0.9362914084f,  0.9482273900f,  0.9601492860f,  0.9720571250f,
     0.9839509358f,  0.9958307465f,  1.0076965855f,  1.0195484807f,  1.0313864600f,
     1.0432105511f,  1.0550207812f,  1.0668171752f,  1.0785997567f,  1.0903685491f,
     1.1021235759f,  1.1138648604f,  1.1255924261f,  1.1373062960f,  1.1490064935f,
     1.1606930418f,  1.1723659639f,  1.1840252828f,  1.1956710217f,  1.2073032034f,
     1.2189218509f,  1.2305269870f,  1.2421186345f,  1.2536968162f,  1.2652615547f,
     1.2768128727f,  1.2883507928f,  1.2998753375f,  1.3113865293f,  1.3228843907f,
     1.3343689441f,  1.3458402118f,  1.3572982160f,  1.3687429791f,  1.3801745232f,
     1.3915928705f,  1.4029980430f,  1.4143900628f,  1.4257689519f,  1.4371347322f,
     1.4484874256f,  1.4598270540f,  1.4711536392f,  1.4824672028f,  1.4937677667f,
     1.5050553524f,  1.5163299816f,  1.5275916758f,  1.5388404565f,  1.5500763451f,
     1.5612993632f,  1.5725095320f,  1.5837068729f,  1.5948914070f,  1.6060631558f,
     1.6172221402f,  1.6283683815f,  1.6395019008f,  1.6506227189f,  1.6617308571f,
     1.6728263361f,  1.6839091768f,  1.6949794002f,  1.7060370271f,  1.7170820781f,
     1.7281145740f,  1.7391345354f,  1.7501419830f,  1.7611369373f,  1.7721194190f,
     1.7830894483f,  1.7940470459f,  1.8049922320f,  1.8159250270f,  1.8268454513f,
     1.8377535251f,  1.8486492685f,  1.8595327018f,  1.8704038451f,  1.8812627185f,
     1.8921093420f,  1.9029437356f,  1.9137659192f,  1.9245759128f,  1.9353737362f,
     1.9461594093f,  1.9569329517f,  1.9676943833f,  1.9784437237f,  1.9891809926f,
     1.9999062096f,  2.0106193942f,  2.0213205660f,  2.0320097444f,  2.0426869489f,
     2.0533521988f,  2.0640055136f,  2.0746469125f,  2.0852764147f,  2.0958940396f,
     2.1064998062f,  2.1170937338f,  2.1276758414f,  2.1382461481f,  2.1488046728f,
     2.1593514347f,  2.1698864525f,  2.1804097453f,  2.1909213318f,  2.2014212309f,
     2.2119094614f,  2.2223860419f,  2.2328509911f,  2.2433043278f,  2.2537460705f,
     2.2641762378f,  2.2745948482f,  2.2850019202f,  2.2953974723f,  2.3057815229f
};

static float lutLookup(float v) {
    uint16_t lo = 0, hi = LUT_SIZE - 1;
    while (hi - lo > 1) {
        uint16_t mid = lo + (hi - lo) / 2;
        if (LUT_V[mid] <= v) lo = mid;
        else                 hi = mid;
    }
    return T_CAL_MIN + lo * T_CAL_STEP;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

// Verify the wire is physically present before running the chain tests.
// HIGH then LOW on PIN_STIM must produce a delta >= 800 LSB on the ADC.
// If the wire is absent, GPIO26 floats and the delta will be near zero.
void test_sim_wire_connected() {
    analogReadResolution(10);
    pinMode(PIN_STIM, OUTPUT);
    pinMode(PIN_PT1000_SW, OUTPUT);
    digitalWrite(PIN_PT1000_SW, LOW);   // disable Pt1000 circuit power

    digitalWrite(PIN_STIM, HIGH);
    delayMicroseconds(200);
    int raw_high = analogRead(PIN_PT1000_ADC);

    digitalWrite(PIN_STIM, LOW);
    delayMicroseconds(200);
    int raw_low = analogRead(PIN_PT1000_ADC);

    int delta = raw_high - raw_low;
    char msg[80];
    snprintf(msg, sizeof(msg),
        "Wire absent? HIGH=%d LOW=%d delta=%d (need>=800) — bridge pin20 to pin31",
        raw_high, raw_low, delta);
    TEST_ASSERT_TRUE_MESSAGE(delta >= 800, msg);
}

// PIN_STIM HIGH (3.3 V) → raw ADC > 900 → LUT returns T in upper range (> 70 °C)
void test_sim_high_stimulus() {
    analogReadResolution(10);
    pinMode(PIN_STIM, OUTPUT);
    digitalWrite(PIN_STIM, HIGH);
    delayMicroseconds(200);

    int raw = analogRead(PIN_PT1000_ADC);
    float v = raw * (SIM_VREF / (float)SIM_ADC_MAX);
    float T = lutLookup(v);

    char msg_raw[48], msg_T[48];
    snprintf(msg_raw, sizeof(msg_raw), "HIGH: raw=%d (need>900)", raw);
    snprintf(msg_T,   sizeof(msg_T),   "HIGH: T=%.1f °C (need>70)", T);

    TEST_ASSERT_TRUE_MESSAGE(raw > 900, msg_raw);
    TEST_ASSERT_TRUE_MESSAGE(T   > 70.0f, msg_T);
}

// PIN_STIM LOW (0 V) → raw ADC < 50 → LUT returns T in lower range (< -50 °C)
void test_sim_low_stimulus() {
    analogReadResolution(10);
    pinMode(PIN_STIM, OUTPUT);
    digitalWrite(PIN_STIM, LOW);
    delayMicroseconds(200);

    int raw = analogRead(PIN_PT1000_ADC);
    float v = raw * (SIM_VREF / (float)SIM_ADC_MAX);
    float T = lutLookup(v);

    char msg_raw[48], msg_T[48];
    snprintf(msg_raw, sizeof(msg_raw), "LOW: raw=%d (need<50)", raw);
    snprintf(msg_T,   sizeof(msg_T),   "LOW: T=%.1f °C (need<-50)", T);

    TEST_ASSERT_TRUE_MESSAGE(raw < 50, msg_raw);
    TEST_ASSERT_TRUE_MESSAGE(T   < -50.0f, msg_T);
}

// Two consecutive ADC reads of the same driven voltage must agree within 5 LSB.
void test_sim_adc_stability() {
    analogReadResolution(10);
    pinMode(PIN_STIM, OUTPUT);
    digitalWrite(PIN_STIM, HIGH);
    delayMicroseconds(200);

    int raw1 = analogRead(PIN_PT1000_ADC);
    int raw2 = analogRead(PIN_PT1000_ADC);
    int diff = raw1 - raw2;
    if (diff < 0) diff = -diff;

    char msg[64];
    snprintf(msg, sizeof(msg), "ADC noise: |r1-r2|=%d > 5 LSB (r1=%d r2=%d)", diff, raw1, raw2);
    TEST_ASSERT_TRUE_MESSAGE(diff <= 5, msg);
}

// ── Unity entry point ─────────────────────────────────────────────────────────

void setUp() {
    // Release PIN_STIM between tests to avoid driving the ADC pin with undefined state
    pinMode(PIN_STIM, INPUT);
    delayMicroseconds(100);
}

void tearDown() {}

void setup() {
    delay(2000);
    Serial.begin(115200);
    Serial.println("--- test_pt1000_sim_gpio ---");
    Serial.println("Wire Pico pin 20 (GP15) to pin 31 (GP26) before running.");
    UNITY_BEGIN();
    RUN_TEST(test_sim_wire_connected);  // connectivity check first
    RUN_TEST(test_sim_high_stimulus);
    RUN_TEST(test_sim_low_stimulus);
    RUN_TEST(test_sim_adc_stability);
    UNITY_END();
}

void loop() {}
