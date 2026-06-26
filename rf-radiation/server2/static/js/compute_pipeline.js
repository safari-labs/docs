/**
 * ComputePipeline — Singleton that owns the full compute → store → render cycle.
 *
 * This is the SINGLE ENTRY POINT for triggering recalculations.
 * When any parameter changes, the flow is:
 *
 *   UIBuilder._onParamChange() → Pipeline.refresh()
 *     1. Push changed params to backend  (API.updateParameters)
 *     2. Re-fetch link budget            (API.fetchLinkBudget)
 *     3. Re-fetch statistics             (API.fetchStatistics)
 *     4. Sync global vars                (budgetData, telemetry)
 *     5. Re-render ALL visuals           (plots, stats panel, Cesium, etc.)
 *
 * No other code should call loadBudget() + renderMargin() + renderRSSI()
 * independently.  Everything flows through Pipeline.refresh().
 *
 * Singleton pattern: exactly one instance, globally accessible.
 */

const Pipeline = (() => {

    // ── Guards ────────────────────────────────────────────────────
    let _refreshing = false;       // Prevents concurrent refreshes
    let _pendingRefresh = false;   // Queues one more refresh after current finishes
    let _debounceTimer = null;
    const DEBOUNCE_MS = 200;       // Coalesce rapid-fire param changes
    let _lastPatternTx = null;     // Track antenna for pattern cache
    let _lastPatternRx = null;

    // ── Public: request a full refresh (debounced) ────────────────

    /**
     * Schedule a full pipeline refresh.
     * Multiple calls within DEBOUNCE_MS are coalesced into one fetch.
     * Safe to call from any change handler — will never stack.
     */
    function refresh() {
        clearTimeout(_debounceTimer);
        if (_refreshing) {
            _pendingRefresh = true;   // Will re-run after current finishes
            return;
        }
        _debounceTimer = setTimeout(_doRefresh, DEBOUNCE_MS);
    }

    /**
     * Force an immediate refresh (no debounce).
     * Use for init or explicit user actions (Apply / Reset buttons).
     */
    async function refreshNow() {
        clearTimeout(_debounceTimer);
        if (_refreshing) {
            _pendingRefresh = true;
            return;
        }
        await _doRefresh();
    }

    // ── Core pipeline execution ───────────────────────────────────

    async function _doRefresh() {
        if (_refreshing) { _pendingRefresh = true; return; }
        _refreshing = true;
        _pendingRefresh = false;
        console.log('[Pipeline] ▶ _doRefresh starting…');

        try {
            // 1. Build overrides from current state
            const overrides = _buildOverrides();
            console.log('[Pipeline] overrides:', JSON.stringify(overrides).slice(0, 200));

            // 2. Fetch link budget (backend runs IMU sim + full physics)
            const budgetResp = await API.fetchLinkBudget(overrides);
            console.log('[Pipeline] ✓ fetchLinkBudget done — SM budgetData len:',
                        (StateManager.get('budgetData') || []).length,
                        'resp type:', Array.isArray(budgetResp) ? 'Array('+budgetResp.length+')' : typeof budgetResp);

            // 3. Sync global variables for backward compat with inline code
            _syncGlobals();
            console.log('[Pipeline] ✓ _syncGlobals done — window.budgetData.length=',
                        (window.budgetData || []).length,
                        'window.telemetry.length=', (window.telemetry || []).length);

            // 4. Fetch statistics (uses same pipeline, includes IMU)
            _fetchStatsAndRender(overrides);

            // 5. Load Cesium 3D pattern data (only re-fetch when antenna changes)
            if (typeof loadCesiumPatterns === 'function') {
                const curTx = document.getElementById('sel-tx')?.value;
                const curRx = document.getElementById('sel-rx')?.value;
                if (curTx !== _lastPatternTx || curRx !== _lastPatternRx) {
                    try {
                        await loadCesiumPatterns();
                        _lastPatternTx = curTx;
                        _lastPatternRx = curRx;
                    } catch(e) {
                        console.warn('[Pipeline] loadCesiumPatterns failed:', e);
                    }
                }
            }

            // 6. Render everything
            console.log('[Pipeline] ▶ calling _renderAll…');
            _renderAll();

            // Debug overlay for user visibility
            _showDebugOverlay(
                `Pipeline OK | budget: ${(window.budgetData||[]).length} pts | ` +
                `telem: ${(window.telemetry||[]).length} pts | ` +
                `viewer: ${typeof viewer !== 'undefined' && !!viewer} | ` +
                `margin div: ${!!document.getElementById('plot-margin')}`
            );

        } catch (err) {
            console.error('[Pipeline] refresh failed:', err);
            _showDebugOverlay('Pipeline ERROR: ' + err.message);
        } finally {
            _refreshing = false;
            // If a refresh was requested while we were busy, run again
            if (_pendingRefresh) {
                _pendingRefresh = false;
                setTimeout(_doRefresh, 50);
            }
        }
    }

    // ── Build override params for the API call ────────────────────

    function _buildOverrides() {
        const pv = StateManager.get('parameterValues') || {};
        return {
            tx: document.getElementById('sel-tx')?.value
                || pv.tx_antenna || 'dipole_half_wave',
            rx: document.getElementById('sel-rx')?.value
                || pv.rx_antenna || 'yagi',
            gs_lat: (typeof GROUND_STATION_DATA !== 'undefined')
                ? GROUND_STATION_DATA.lat : 48.5678,
            gs_lon: (typeof GROUND_STATION_DATA !== 'undefined')
                ? GROUND_STATION_DATA.lon : -81.3655,
            gs_alt: (typeof GROUND_STATION_DATA !== 'undefined')
                ? GROUND_STATION_DATA.alt : 285.8,
        };
    }

    // ── Sync StateManager → global variables ──────────────────────

    function _syncGlobals() {
        // Sync budgetData global from StateManager (inline code reads this)
        window.budgetData = StateManager.get('budgetData') || [];

        // Sync telemetry global from StateManager (canonical GPS data)
        // Do NOT derive telemetry from budgetData — that destroys the original.
        const smTelemetry = StateManager.get('telemetry');
        if (smTelemetry && smTelemetry.length > 0) {
            window.telemetry = smTelemetry;
        }
    }

    // ── Fetch statistics & update stats panel ─────────────────────

    async function _fetchStatsAndRender(overrides) {
        try {
            const s = await API.fetchStatistics(overrides);
            if (!s) return;

            // Update stats DOM elements
            const el = (id) => document.getElementById(id);
            if (el('s-min'))  el('s-min').textContent  = s.min_margin_db + ' dB';
            if (el('s-max'))  el('s-max').textContent  = s.max_margin_db + ' dB';
            if (el('s-avg'))  el('s-avg').textContent  = s.avg_margin_db + ' dB';
            if (el('s-rely')) el('s-rely').textContent  = s.link_reliability_pct + '%';
            if (el('h-rely')) {
                el('h-rely').textContent = s.link_reliability_pct + '%';
                el('h-rely').style.color = s.link_reliability_pct >= 95
                    ? 'var(--green)'
                    : s.link_reliability_pct >= 80 ? 'var(--yellow)' : 'var(--red)';
            }

            const sc = s.status_counts, tot = s.total_points;
            if (el('sc-rows') && typeof sColor === 'function') {
                el('sc-rows').innerHTML = [
                    { cls: 'NOMINAL',   label: 'NOMINAL',   c: sc.NOMINAL },
                    { cls: 'WARNING',   label: 'WARNING',   c: sc.WARNING },
                    { cls: 'MARGINAL',  label: 'MARGINAL',  c: sc.MARGINAL },
                    { cls: 'LINK_LOST', label: 'LINK LOST', c: sc.LINK_LOST },
                ].map(r => `
                    <div class="sc-row" style="border-left-color:${sColor(r.cls)}">
                      <span>${r.label}</span>
                      <span style="font-family:'Space Mono',monospace;font-size:9px">
                        ${r.c}pts &nbsp;${(100 * r.c / tot).toFixed(1)}%
                      </span>
                    </div>`).join('');
            }
        } catch (e) {
            console.warn('[Pipeline] stats fetch failed:', e);
        }
    }

    // ── Render all visual outputs ─────────────────────────────────

    function _renderAll() {
        console.log('[Pipeline] _renderAll — budgetData.length=', (window.budgetData||[]).length,
                    'telemetry.length=', (window.telemetry||[]).length,
                    'viewer=', typeof viewer !== 'undefined' ? !!viewer : 'undef');
        // Force full re-render by resetting throttle timestamps
        if (typeof _lastMarginRender !== 'undefined') window._lastMarginRender = 0;
        if (typeof _lastRssiRender !== 'undefined')   window._lastRssiRender = 0;

        if (typeof renderMargin === 'function') {
            console.log('[Pipeline] → renderMargin()');
            renderMargin();
        } else { console.warn('[Pipeline] renderMargin NOT defined'); }
        if (typeof renderRSSI === 'function') {
            console.log('[Pipeline] → renderRSSI()');
            renderRSSI();
        } else { console.warn('[Pipeline] renderRSSI NOT defined'); }
        if (typeof renderAnalysis === 'function')      renderAnalysis();
        if (typeof updateReportSummary === 'function') updateReportSummary();
        if (typeof buildTrajectory === 'function') {
            console.log('[Pipeline] → buildTrajectory()');
            buildTrajectory();
        } else { console.warn('[Pipeline] buildTrajectory NOT defined'); }

        // Update the current frame display if we have data
        if (typeof updateFrame === 'function'
            && typeof currentIdx !== 'undefined'
            && window.budgetData && window.budgetData.length > 0) {
            console.log('[Pipeline] → updateFrame(', currentIdx, ')');
            updateFrame(currentIdx);
        }

        // Update header displays
        const pv = StateManager.get('parameterValues') || {};
        const hFreq = document.getElementById('h-freq');
        const hPower = document.getElementById('h-power');
        if (hFreq && pv.frequency_mhz)  hFreq.textContent  = pv.frequency_mhz + ' MHz';
        if (hPower && pv.tx_power_dbm)   hPower.textContent = pv.tx_power_dbm + ' dBm';
        console.log('[Pipeline] ✅ _renderAll complete');
    }

    /** Small on-page overlay for quick diagnostics (remove after debugging). */
    function _showDebugOverlay(msg) {
        let ov = document.getElementById('_pipeline_debug');
        if (!ov) {
            ov = document.createElement('div');
            ov.id = '_pipeline_debug';
            ov.style.cssText = 'position:fixed;bottom:4px;left:4px;background:rgba(0,0,0,.85);color:#0f0;font:10px monospace;padding:6px 10px;z-index:99999;max-width:500px;border:1px solid #0f0;pointer-events:none;white-space:pre-wrap;';
            document.body.appendChild(ov);
        }
        ov.textContent = msg;
    }

    // ── Public API ────────────────────────────────────────────────
    return {
        refresh,       // debounced — for continuous slider drags
        refreshNow,    // immediate — for init, Apply, Reset, antenna change
    };
})();

if (typeof window !== 'undefined') {
    window.Pipeline = Pipeline;
}
