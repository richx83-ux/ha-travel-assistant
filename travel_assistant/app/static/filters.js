/**
 * Cascading filters. Selecting any filter rebuilds the options of the others
 * from the records that match the current selection.
 *
 * Usage:
 *   TAFilters.bind({
 *     records: [{ theme: 'English Heritage', region: 'South West', county: 'Devon' }, ...],
 *     selects: { theme: el, region: el, county: el },
 *     labels: { theme: 'All themes', region: 'All regions', county: 'All counties' },
 *     fields: ['theme', 'region', 'county'],
 *     onChange: function () {}
 *   });
 */
(function (global) {
  function esc(v) {
    return String(v).replace(/&/g, '&').replace(/"/g, '"').replace(/</g, '<');
  }

  function bind(opts) {
    const records = opts.records || [];
    const selects = opts.selects || {};
    const labels = opts.labels || {};
    const fields = (opts.fields || Object.keys(selects)).filter(function (f) { return selects[f]; });

    function optionsFor(field) {
      const set = new Set();
      records.forEach(function (r) {
        for (let i = 0; i < fields.length; i++) {
          const f = fields[i];
          if (f === field) continue;
          const sel = selects[f];
          if (!sel || !sel.value || sel.value === 'all') continue;
          if (String(r[f] == null ? '' : r[f]) !== sel.value) return;
        }
        const v = r[field] == null ? '' : String(r[field]).trim();
        if (v) set.add(v);
      });
      return Array.from(set).sort(function (a, b) { return a.localeCompare(b); });
    }

    function rebuild(field) {
      const sel = selects[field];
      if (!sel) return;
      const current = sel.value;
      const values = optionsFor(field);
      const label = labels[field] || 'All';
      sel.innerHTML = '<option value="all">' + esc(label) + '</option>' +
        values.map(function (v) { return '<option value="' + esc(v) + '">' + esc(v) + '</option>'; }).join('');
      sel.value = values.indexOf(current) !== -1 ? current : 'all';
    }

    function refresh() {
      fields.forEach(rebuild);
      if (typeof opts.onChange === 'function') opts.onChange();
    }

    fields.forEach(function (f) {
      selects[f].addEventListener('change', refresh);
    });
    refresh();
    return { refresh: refresh };
  }

  global.TAFilters = { bind: bind };
})(window);
