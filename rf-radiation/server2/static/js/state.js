/**
 * State Manager — Single source of truth for the RF simulator.
 *
 * STRICT RULE: All state changes go through this module.
 * Components subscribe to state changes via on(). No direct mutation.
 *
 * State flow:
 *   User action → API.updateParameters() → StateManager.set() → UI update
 *   API response → StateManager.set() → notify listeners → UI update
 *
 * IMPORTANT: No physics or RF computation happens here.
 * All physics is computed on the backend.
 */

const StateManager = (() => {
    // ── Private state ─────────────────────────────────────────────
    const _state = {
        // Playback / timeline
        currentTimeIndex: 0,
        isPlaying: false,
        playbackSpeed: 1.0,

        // Telemetry data (raw from API)
        telemetry: [],
        budgetData: [],     // per-point data (merged telemetry + budget)
        budgetResult: null, // raw budget result from backend (dict with arrays)

        // Parameter system (backend-driven)
        parameterSchema: null,   // schema from /api/parameters
        parameterValues: {},     // current values from /api/parameters/values

        // Antenna selections (derived from parameterValues)
        txAntenna: 'dipole_half_wave',
        rxAntenna: 'yagi',

        // View state
        activeTab: 'tab-globe',
        sidebarCollapsed: false,

        // Flags
        budgetDirty: true,    // needs re-fetch from server
        isLoading: false,
    };

    // ── Subscriber registry ───────────────────────────────────────
    const _listeners = {};

    function on(key, callback) {
        if (!_listeners[key]) _listeners[key] = new Set();
        _listeners[key].add(callback);
        return () => _listeners[key].delete(callback);
    }

    function _notify(key, value, oldValue) {
        if (_listeners[key]) {
            for (const cb of _listeners[key]) {
                try { cb(value, oldValue, key); } catch (e) { console.error('[State] listener error:', e); }
            }
        }
        if (_listeners['*']) {
            for (const cb of _listeners['*']) {
                try { cb(value, oldValue, key); } catch (e) { console.error('[State] wildcard listener error:', e); }
            }
        }
    }

    function set(key, value) {
        const old = _state[key];
        _state[key] = value;
        if (typeof value === 'object' || old !== value) {
            _notify(key, value, old);
        }
    }

    function get(key) {
        return _state[key];
    }

    function batch(updates) {
        const changes = [];
        for (const [key, value] of Object.entries(updates)) {
            const old = _state[key];
            _state[key] = value;
            if (typeof value === 'object' || old !== value) {
                changes.push([key, value, old]);
            }
        }
        for (const [key, value, old] of changes) {
            _notify(key, value, old);
        }
    }

    // ── Convenience: timeline navigation ──────────────────────────

    function setTimeIndex(idx) {
        const n = _state.telemetry.length || 1;
        const clamped = Math.max(0, Math.min(idx, n - 1));
        set('currentTimeIndex', clamped);
    }

    function advanceTime(delta = 1) {
        const n = _state.telemetry.length;
        if (n === 0) return;
        const next = _state.currentTimeIndex + delta;
        if (next >= n) {
            set('currentTimeIndex', 0);
            set('isPlaying', false);
        } else {
            set('currentTimeIndex', next);
        }
    }

    function currentPoint() {
        const idx = _state.currentTimeIndex;
        if (_state.budgetData.length === 0) return null;
        return _state.budgetData[idx] || null;
    }

    function currentBudget() {
        const idx = _state.currentTimeIndex;
        if (_state.budgetData.length === 0) return null;
        return _state.budgetData[idx] || null;
    }

    // ── Parameter helpers ─────────────────────────────────────────

    /** Get a specific parameter value. */
    function getParam(key) {
        return (_state.parameterValues || {})[key];
    }

    /** Get the IMU state for current time index (from backend). */
    function currentIMU() {
        const idx = _state.currentTimeIndex;
        const pt = _state.budgetData[idx];
        if (!pt) return null;
        return {
            roll: pt.imu_roll || 0,
            pitch: pt.imu_pitch || 0,
            yaw: pt.imu_yaw || 0,
        };
    }

    // ── Public API ────────────────────────────────────────────────
    return {
        on,
        set,
        get,
        batch,
        setTimeIndex,
        advanceTime,
        currentPoint,
        currentBudget,
        currentIMU,
        getParam,
    };
})();

if (typeof window !== 'undefined') {
    window.StateManager = StateManager;
}
