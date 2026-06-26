/**
 * API Layer — Clean fetch wrappers for all server endpoints.
 *
 * STRICT RULE: This is the ONLY module that makes HTTP requests.
 * All data flows: API.fetch*() → StateManager.set() → UI listeners.
 *
 * No direct DOM manipulation. No visualization logic.
 * No RF computation. No physics. DISPLAY ONLY.
 */

const API = (() => {
    const BASE = '';  // Same origin

    // ── Helpers ───────────────────────────────────────────────────

    async function _get(url) {
        const resp = await fetch(BASE + url);
        if (!resp.ok) throw new Error(`API ${resp.status}: ${url}`);
        return resp.json();
    }

    async function _post(url, body) {
        const resp = await fetch(BASE + url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!resp.ok) throw new Error(`API ${resp.status}: ${url}`);
        return resp.json();
    }

    // ── Parameter Schema (backend-driven UI) ──────────────────────

    /**
     * Fetch the parameter schema that defines ALL valid simulation parameters.
     * The frontend uses this to dynamically generate the UI.
     */
    async function fetchParameterSchema() {
        const schema = await _get('/api/parameters');
        StateManager.set('parameterSchema', schema);
        return schema;
    }

    /**
     * Fetch current parameter values from backend.
     */
    async function fetchParameterValues() {
        const values = await _get('/api/parameters/values');
        StateManager.set('parameterValues', values);
        return values;
    }

    /**
     * Update parameter values on backend. Validates server-side.
     */
    async function updateParameters(params) {
        const result = await _post('/api/parameters/values', params);
        if (result.warnings && result.warnings.length > 0) {
            console.warn('[API] Parameter warnings:', result.warnings);
        }
        await fetchParameterValues();
        StateManager.set('budgetDirty', true);
        return result;
    }

    // ── Telemetry ─────────────────────────────────────────────────

    async function fetchTelemetry() {
        const data = await _get('/api/telemetry');
        if (Array.isArray(data)) {
            StateManager.set('telemetry', data);
        }
        return data;
    }

    async function uploadTelemetry(formData) {
        const resp = await fetch(BASE + '/api/upload_telemetry', {
            method: 'POST',
            body: formData,
        });
        return resp.json();
    }

    // ── Link Budget ───────────────────────────────────────────────

    /**
     * Fetch full link budget computation.
     * ALL physics params come from the backend parameter store.
     */
    async function fetchLinkBudget(overrides = {}) {
        const params = _buildBudgetParams(overrides);
        const qs = new URLSearchParams(params).toString();

        StateManager.set('isLoading', true);
        try {
            const data = await _get(`/api/link_budget?${qs}`);
            if (Array.isArray(data)) {
                StateManager.set('budgetData', data);
                StateManager.set('budgetDirty', false);
            } else if (data && !data.error) {
                StateManager.set('budgetResult', data);
                StateManager.set('budgetDirty', false);
                if (data.margin_db) {
                    _buildPerPointArray(data);
                }
            }
            return data;
        } finally {
            StateManager.set('isLoading', false);
        }
    }

    /** Build per-point budget data array from flat-arrays result. */
    function _buildPerPointArray(data) {
        const telemetry = StateManager.get('telemetry') || [];
        const n = data.margin_db ? data.margin_db.length : 0;
        const result = [];
        for (let i = 0; i < n; i++) {
            const pt = telemetry[i] ? { ...telemetry[i] } : {};
            for (const key of Object.keys(data)) {
                if (key === 'imu') continue;
                if (Array.isArray(data[key]) && i < data[key].length) {
                    pt[key] = data[key][i];
                }
            }
            if (data.statuses && data.statuses[i]) {
                pt.status = data.statuses[i];
            }
            if (data.imu) {
                pt.imu_roll = data.imu.roll_deg ? data.imu.roll_deg[i] : 0;
                pt.imu_pitch = data.imu.pitch_deg ? data.imu.pitch_deg[i] : 0;
                pt.imu_yaw = data.imu.yaw_deg ? data.imu.yaw_deg[i] : 0;
            }
            result.push(pt);
        }
        StateManager.set('budgetData', result);
    }

    /** Build query params from current StateManager values.
     *  Forwards ALL parameterValues so the backend receives every user change
     *  (RF chain, IMU, propagation, margins — everything).
     */
    function _buildBudgetParams(overrides = {}) {
        const pv = StateManager.get('parameterValues') || {};

        // Start with antenna + ground station defaults
        const params = {
            tx: pv.tx_antenna || StateManager.get('txAntenna') || 'dipole_half_wave',
            rx: pv.rx_antenna || StateManager.get('rxAntenna') || 'yagi',
            gs_lat: 48.5678,
            gs_lon: -81.3655,
            gs_alt: 285.8,
        };

        // Forward every parameter value from the backend store.
        // Keys like tx_antenna / rx_antenna are handled above.
        const SKIP = new Set(['tx_antenna', 'rx_antenna']);
        for (const [k, v] of Object.entries(pv)) {
            if (SKIP.has(k)) continue;
            if (v === null || v === undefined) continue;
            params[k] = v;
        }

        return { ...params, ...overrides };
    }

    // ── RF Budget Config ──────────────────────────────────────────

    async function fetchRFBudget() {
        return _get('/api/rf_budget');
    }

    async function updateRFBudget(params) {
        return _post('/api/rf_budget', params);
    }

    async function resetRFBudget() {
        return _post('/api/rf_budget/reset', {});
    }

    // ── Statistics ────────────────────────────────────────────────

    async function fetchStatistics(overrides = {}) {
        const params = _buildBudgetParams(overrides);
        const qs = new URLSearchParams(params).toString();
        return _get(`/api/statistics?${qs}`);
    }

    // ── Footprint ─────────────────────────────────────────────────

    async function fetchFootprint(lat, lon, alt, pitch, roll, yaw, opts = {}) {
        const pv = StateManager.get('parameterValues') || {};
        const params = {
            lat, lon, alt, pitch, roll, yaw,
            tx: opts.tx || pv.tx_antenna || StateManager.get('txAntenna') || 'dipole_half_wave',
            freq: pv.frequency_mhz || 902,
            grid_n: opts.grid_n || pv.grid_resolution || 25,
            grid_scale: opts.grid_scale || pv.grid_scale || 1.0,
        };
        const qs = new URLSearchParams(params).toString();
        return _get(`/api/footprint?${qs}`);
    }

    // ── Antennas ──────────────────────────────────────────────────

    async function fetchAntennas() {
        return _get('/api/antennas');
    }

    async function fetchPattern(antennaId, resolution = 'medium') {
        return _get(`/api/pattern/${antennaId}?resolution=${resolution}`);
    }

    async function fetchCesiumPattern(antennaId) {
        return _get(`/api/cesium_pattern/${antennaId}`);
    }

    // ── Config ────────────────────────────────────────────────────

    async function fetchConfig() {
        return _get('/api/config');
    }

    // ── Public API ────────────────────────────────────────────────
    return {
        fetchParameterSchema,
        fetchParameterValues,
        updateParameters,
        fetchTelemetry,
        uploadTelemetry,
        fetchLinkBudget,
        fetchRFBudget,
        updateRFBudget,
        resetRFBudget,
        fetchStatistics,
        fetchFootprint,
        fetchAntennas,
        fetchPattern,
        fetchCesiumPattern,
        fetchConfig,
    };
})();

if (typeof window !== 'undefined') {
    window.API = API;
}
