/**
 * UI Builder — Dynamically generates sidebar controls from backend parameter schema.
 *
 * STRICT RULE: This module creates UI elements based on the backend-defined schema.
 * No hardcoded parameters. No physics logic. Pure DOM generation.
 *
 * Flow:
 *   1. API.fetchParameterSchema() → schema stored in StateManager
 *   2. UIBuilder.buildSidebar(schema) → generates all controls
 *   3. User changes control → API.updateParameters() → re-fetch budget
 */

const UIBuilder = (() => {

    /** Build the entire sidebar from the backend parameter schema. */
    function buildSidebar(schema, container) {
        if (!schema || !schema.groups || !schema.parameters) {
            console.error('[UIBuilder] Invalid schema');
            return;
        }

        container.innerHTML = '';

        // Sort groups by order
        const groups = [...schema.groups].sort((a, b) => a.order - b.order);

        for (const group of groups) {
            const params = schema.parameters.filter(p => p.group === group.key);
            if (params.length === 0) continue;

            const panel = _createGroupPanel(group, params);
            container.appendChild(panel);
        }
    }

    /** Create a collapsible panel for a parameter group. */
    function _createGroupPanel(group, params) {
        const panel = document.createElement('details');
        panel.className = 'param-group';
        panel.open = group.order <= 3; // first 3 groups open by default

        const summary = document.createElement('summary');
        summary.className = 'param-group-header';
        summary.innerHTML = `<span class="param-group-icon">${group.icon || '⚙️'}</span> ${group.label}`;
        panel.appendChild(summary);

        const body = document.createElement('div');
        body.className = 'param-group-body';

        for (const param of params) {
            const control = _createParamControl(param);
            body.appendChild(control);
        }

        panel.appendChild(body);
        return panel;
    }

    /** Create a single parameter control element. */
    function _createParamControl(param) {
        const wrapper = document.createElement('div');
        wrapper.className = 'param-control';
        wrapper.dataset.paramKey = param.key;
        if (param.description) {
            wrapper.title = param.description;
        }

        switch (param.type) {
            case 'bool':
                wrapper.appendChild(_createBoolControl(param));
                break;
            case 'float':
            case 'int':
                wrapper.appendChild(_createNumberControl(param));
                break;
            case 'select':
                wrapper.appendChild(_createSelectControl(param));
                break;
            case 'string':
                wrapper.appendChild(_createStringControl(param));
                break;
            default:
                wrapper.appendChild(_createStringControl(param));
        }

        return wrapper;
    }

    /** Boolean toggle (checkbox). */
    function _createBoolControl(param) {
        const row = document.createElement('label');
        row.className = 'param-bool';

        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.id = `param-${param.key}`;
        cb.checked = _getCurrentValue(param.key, param.default);
        cb.addEventListener('change', () => _onParamChange(param.key, cb.checked));

        const span = document.createElement('span');
        span.textContent = param.label;

        row.appendChild(cb);
        row.appendChild(span);

        if (param.unit) {
            const unit = document.createElement('span');
            unit.className = 'param-unit';
            unit.textContent = param.unit;
            row.appendChild(unit);
        }

        return row;
    }

    /** Numeric input with range slider. */
    function _createNumberControl(param) {
        const frag = document.createDocumentFragment();

        const labelRow = document.createElement('div');
        labelRow.className = 'param-label-row';

        const label = document.createElement('label');
        label.htmlFor = `param-${param.key}`;
        label.textContent = param.label;

        const valueSpan = document.createElement('span');
        valueSpan.className = 'param-value-display';
        valueSpan.id = `param-val-${param.key}`;
        const currentVal = _getCurrentValue(param.key, param.default);
        valueSpan.textContent = `${currentVal}${param.unit ? ' ' + param.unit : ''}`;

        labelRow.appendChild(label);
        labelRow.appendChild(valueSpan);
        frag.appendChild(labelRow);

        // Slider if range is defined
        if (param.min !== undefined && param.max !== undefined) {
            const slider = document.createElement('input');
            slider.type = 'range';
            slider.id = `param-${param.key}`;
            slider.min = param.min;
            slider.max = param.max;
            slider.step = param.step || (param.type === 'int' ? 1 : 0.01);
            slider.value = currentVal;
            slider.className = 'param-slider';

            slider.addEventListener('input', () => {
                const v = param.type === 'int' ? parseInt(slider.value) : parseFloat(slider.value);
                valueSpan.textContent = `${v}${param.unit ? ' ' + param.unit : ''}`;
            });
            slider.addEventListener('change', () => {
                const v = param.type === 'int' ? parseInt(slider.value) : parseFloat(slider.value);
                _onParamChange(param.key, v);
            });

            frag.appendChild(slider);
        } else {
            // Plain number input
            const input = document.createElement('input');
            input.type = 'number';
            input.id = `param-${param.key}`;
            input.value = currentVal;
            input.step = param.step || (param.type === 'int' ? 1 : 0.01);
            input.className = 'param-input';
            if (param.min !== undefined) input.min = param.min;
            if (param.max !== undefined) input.max = param.max;

            input.addEventListener('change', () => {
                const v = param.type === 'int' ? parseInt(input.value) : parseFloat(input.value);
                valueSpan.textContent = `${v}${param.unit ? ' ' + param.unit : ''}`;
                _onParamChange(param.key, v);
            });

            frag.appendChild(input);
        }

        return frag;
    }

    /** Select dropdown. */
    function _createSelectControl(param) {
        const frag = document.createDocumentFragment();

        const label = document.createElement('label');
        label.htmlFor = `param-${param.key}`;
        label.textContent = param.label;
        label.className = 'param-label';
        frag.appendChild(label);

        const select = document.createElement('select');
        select.id = `param-${param.key}`;
        select.className = 'param-select';
        const currentVal = _getCurrentValue(param.key, param.default);

        for (const opt of (param.options || [])) {
            const option = document.createElement('option');
            option.value = opt;
            option.textContent = opt;
            if (opt === currentVal) option.selected = true;
            select.appendChild(option);
        }

        select.addEventListener('change', () => _onParamChange(param.key, select.value));
        frag.appendChild(select);
        return frag;
    }

    /** String input. */
    function _createStringControl(param) {
        const frag = document.createDocumentFragment();

        const label = document.createElement('label');
        label.htmlFor = `param-${param.key}`;
        label.textContent = param.label;
        label.className = 'param-label';
        frag.appendChild(label);

        const input = document.createElement('input');
        input.type = 'text';
        input.id = `param-${param.key}`;
        input.value = _getCurrentValue(param.key, param.default);
        input.className = 'param-input';

        input.addEventListener('change', () => _onParamChange(param.key, input.value));
        frag.appendChild(input);
        return frag;
    }

    /** Get current value from StateManager or fallback to default. */
    function _getCurrentValue(key, defaultVal) {
        const values = StateManager.get('parameterValues') || {};
        return values[key] !== undefined ? values[key] : defaultVal;
    }

    /** Debounced parameter change handler — pushes to backend then triggers Pipeline. */
    let _changeTimer = null;
    let _pendingChanges = {};

    function _onParamChange(key, value) {
        _pendingChanges[key] = value;
        clearTimeout(_changeTimer);
        _changeTimer = setTimeout(async () => {
            const changes = { ..._pendingChanges };
            _pendingChanges = {};
            try {
                // 1. Push changed values to backend param store
                await API.updateParameters(changes);
                // 2. Trigger full pipeline refresh (singleton handles
                //    fetch → store → render atomically)
                if (typeof Pipeline !== 'undefined') {
                    Pipeline.refresh();
                }
            } catch (err) {
                console.error('[UIBuilder] Parameter update failed:', err);
            }
        }, 150);   // 150ms debounce for responsive feel
    }

    /** Update all control values from StateManager (after backend response). */
    function refreshValues() {
        const values = StateManager.get('parameterValues') || {};
        for (const [key, value] of Object.entries(values)) {
            const el = document.getElementById(`param-${key}`);
            if (!el) continue;
            if (el.type === 'checkbox') {
                el.checked = Boolean(value);
            } else {
                el.value = value;
            }
            const valSpan = document.getElementById(`param-val-${key}`);
            if (valSpan) {
                const schema = StateManager.get('parameterSchema');
                const paramDef = schema?.parameters?.find(p => p.key === key);
                const unit = paramDef?.unit || '';
                valSpan.textContent = `${value}${unit ? ' ' + unit : ''}`;
            }
        }
    }

    // ── Public API ────────────────────────────────────────────────
    return {
        buildSidebar,
        refreshValues,
    };
})();

if (typeof window !== 'undefined') {
    window.UIBuilder = UIBuilder;
}
