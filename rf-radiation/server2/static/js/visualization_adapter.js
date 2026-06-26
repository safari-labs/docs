/**
 * Visualization Adapter — Color mapping and display-only transforms.
 *
 * STRICT RULE: This module handles ONLY cosmetic/visual concerns.
 * It must NEVER modify physics data or feed back into the simulation.
 *
 * Consumers: Cesium entity coloring, Plotly trace styling, heatmap colors.
 */

const VizAdapter = (() => {

    // ── Status → Color ────────────────────────────────────────────

    const STATUS_COLORS = {
        'NOMINAL':   { hex: '#00ff00', rgba: [0, 255, 0, 200] },
        'WARNING':   { hex: '#ffff00', rgba: [255, 255, 0, 200] },
        'MARGINAL':  { hex: '#ff8800', rgba: [255, 136, 0, 200] },
        'LINK_LOST': { hex: '#ff0000', rgba: [255, 0, 0, 200] },
    };

    function statusToColor(status) {
        return (STATUS_COLORS[status] || STATUS_COLORS['LINK_LOST']).hex;
    }

    function statusToCesiumColor(status) {
        const c = (STATUS_COLORS[status] || STATUS_COLORS['LINK_LOST']).rgba;
        if (typeof Cesium !== 'undefined') {
            return new Cesium.Color(c[0] / 255, c[1] / 255, c[2] / 255, c[3] / 255);
        }
        return c;
    }

    // ── Margin → Gradient Color ───────────────────────────────────

    /**
     * Map link margin (dB) to a smooth gradient color.
     * Green (>15dB) → Yellow (10-15) → Orange (0-10) → Red (<0)
     */
    function marginToColor(margin_db) {
        if (margin_db >= 15) return '#00ff00';
        if (margin_db >= 10) {
            const t = (margin_db - 10) / 5;
            const r = Math.round(255 * (1 - t));
            return `rgb(${r}, 255, 0)`;
        }
        if (margin_db >= 0) {
            const t = margin_db / 10;
            const g = Math.round(136 * t);
            return `rgb(255, ${g}, 0)`;
        }
        return '#ff0000';
    }

    function marginToCesiumColor(margin_db) {
        if (typeof Cesium === 'undefined') return marginToColor(margin_db);
        if (margin_db >= 15) return Cesium.Color.LIME;
        if (margin_db >= 10) {
            const t = (margin_db - 10) / 5;
            return Cesium.Color.fromCssColorString(marginToColor(margin_db));
        }
        if (margin_db >= 0) {
            return Cesium.Color.fromCssColorString(marginToColor(margin_db));
        }
        return Cesium.Color.RED;
    }

    // ── RSSI → Heatmap Color ─────────────────────────────────────

    /**
     * Map RSSI (dBm) to heatmap RGBA for canvas rendering.
     * Returns [r, g, b, a] array.
     */
    function rssiToHeatColor(rssi_dbm, sensitivity = -110, max_rssi = -40) {
        const range = max_rssi - sensitivity;
        const normalized = Math.max(0, Math.min(1, (rssi_dbm - sensitivity) / range));

        if (normalized < 0.25) {
            const t = normalized / 0.25;
            return [Math.round(255 * t), 0, 0, 180];
        }
        if (normalized < 0.5) {
            const t = (normalized - 0.25) / 0.25;
            return [255, Math.round(255 * t), 0, 180];
        }
        if (normalized < 0.75) {
            const t = (normalized - 0.5) / 0.25;
            return [Math.round(255 * (1 - t)), 255, 0, 180];
        }
        const t = (normalized - 0.75) / 0.25;
        return [0, 255, Math.round(255 * t), 180];
    }

    // ── EMA Smoothing (display only) ─────────────────────────────

    /**
     * Apply EMA smoothing to an array of values.
     * WARNING: For display only. Result must not feed back into physics.
     */
    function smoothEMA(values, alpha = 0.15) {
        if (!values || values.length === 0) return [];
        const result = new Float64Array(values.length);
        result[0] = values[0];
        for (let i = 1; i < values.length; i++) {
            result[i] = alpha * values[i] + (1 - alpha) * result[i - 1];
        }
        return Array.from(result);
    }

    // ── Loss Breakdown Labels ────────────────────────────────────

    const LOSS_LABELS = {
        fspl_db:                 'Free Space Path Loss',
        atmospheric_loss_db:     'Atmospheric',
        polarization_loss_db:    'Polarization Mismatch',
        body_shadow_loss_db:     'Body Shadowing',
        fresnel_loss_db:         'Fresnel Zone',
        ground_reflection_loss_db: '2-Ray Ground Reflection',
        low_elevation_loss_db:   'Low Elevation Excess',
        horizon_loss_db:         'Horizon Diffraction',
        clutter_loss_db:         'Environment Clutter',
        pendulum_loss_db:        'Pendulum Swing',
        jitter_loss_db:          'Pointing Jitter',
    };

    function getLossLabel(key) {
        return LOSS_LABELS[key] || key;
    }

    // ── Public API ────────────────────────────────────────────────
    return {
        statusToColor,
        statusToCesiumColor,
        marginToColor,
        marginToCesiumColor,
        rssiToHeatColor,
        smoothEMA,
        getLossLabel,
        STATUS_COLORS,
        LOSS_LABELS,
    };
})();

if (typeof window !== 'undefined') {
    window.VizAdapter = VizAdapter;
}
