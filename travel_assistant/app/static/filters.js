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

  function fieldValue(raw) {
    if (raw && typeof raw === 'object') return String(raw.value == null ? '' : raw.value);
    return raw == null ? '' : String(raw);
  }
  function fieldLabel(raw) {
    if (raw && typeof raw === 'object') return String(raw.label == null ? raw.value : raw.label);
    return raw == null ? '' : String(raw);
  }

  function bind(opts) {
    const records = opts.records || [];
    const selects = opts.selects || {};
    const labels = opts.labels || {};
    const fields = (opts.fields || Object.keys(selects)).filter(function (f) { return selects[f]; });

    function optionsFor(field) {
      const set = new Map();
      records.forEach(function (r) {
        for (let i = 0; i < fields.length; i++) {
          const f = fields[i];
          if (f === field) continue;
          const sel = selects[f];
          if (!sel || !sel.value || sel.value === 'all') continue;
          if (String(fieldValue(r[f])).trim() !== sel.value) return;
        }
        const value = fieldValue(r[field]).trim();
        const label = fieldLabel(r[field]).trim();
        if (value) set.set(value, label || value);
      });
      return Array.from(set.entries()).map(function (pair) {
        return { value: pair[0], label: pair[1] };
      }).sort(function (a, b) { return a.label.localeCompare(b.label); });
    }

    function rebuild(field) {
      const sel = selects[field];
      if (!sel) return;
      const current = sel.value;
      const values = optionsFor(field);
      const label = labels[field] || 'All';
      sel.innerHTML = '<option value="all">' + esc(label) + '</option>' +
        values.map(function (v) {
          return '<option value="' + esc(v.value) + '">' + esc(v.label) + '</option>';
        }).join('');
      sel.value = values.some(function (v) { return v.value === current; }) ? current : 'all';
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

  /**
   * Turn a <select> into a type-to-filter dropdown. The select stays in the
   * DOM (so forms and cascades still work) and is visually replaced.
   */
  function makeSearchable(select, placeholder) {
    if (!select || select.dataset.searchable === '1') return;
    select.dataset.searchable = '1';
    const wrap = document.createElement('div');
    wrap.className = 'relative';
    const input = document.createElement('input');
    input.type = 'text';
    input.autocomplete = 'off';
    input.placeholder = placeholder || 'Type to filter…';
    input.className = select.className || 'w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white';
    const list = document.createElement('ul');
    list.className = 'hidden absolute z-40 mt-1 w-full max-h-56 overflow-y-auto bg-white border border-slate-200 rounded-lg shadow-lg';
    select.classList.add('hidden');
    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(input);
    wrap.appendChild(list);
    wrap.appendChild(select);

    function labelFor(val) {
      const opts = select.options;
      for (let i = 0; i < opts.length; i++) {
        if (opts[i].value === val) return opts[i].textContent;
      }
      return '';
    }
    function syncInput() {
      if (!select.value || select.value === 'all') input.value = '';
      else input.value = labelFor(select.value);
    }
    function render(q) {
      const query = (q || '').toLowerCase().trim();
      list.innerHTML = '';
      Array.from(select.options).forEach(function (opt) {
        if (query && opt.value !== 'all' && opt.textContent.toLowerCase().indexOf(query) === -1) return;
        const li = document.createElement('li');
        li.textContent = opt.textContent;
        li.className = 'px-3 py-2 text-sm cursor-pointer hover:bg-slate-50' +
          (opt.value === select.value ? ' bg-slate-100 font-medium' : '');
        li.addEventListener('mousedown', function (e) {
          e.preventDefault();
          select.value = opt.value;
          syncInput();
          list.classList.add('hidden');
          select.dispatchEvent(new Event('change', { bubbles: true }));
        });
        list.appendChild(li);
      });
      if (!list.children.length) {
        const li = document.createElement('li');
        li.className = 'px-3 py-2 text-sm text-slate-400';
        li.textContent = 'No matches';
        list.appendChild(li);
      }
    }
    input.addEventListener('focus', function () {
      input.select();
      render('');
      list.classList.remove('hidden');
    });
    input.addEventListener('input', function () {
      render(input.value);
      list.classList.remove('hidden');
    });
    input.addEventListener('blur', function () {
      setTimeout(function () { list.classList.add('hidden'); syncInput(); }, 160);
    });
    const obs = new MutationObserver(syncInput);
    obs.observe(select, { childList: true });
    syncInput();
  }

  global.TAFilters = { bind: bind, makeSearchable: makeSearchable };
})(window);
