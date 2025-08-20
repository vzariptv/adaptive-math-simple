// static/js/admin_evaluation.js
// Admin → Evaluation preview page logic
(function(){
  'use strict';

  function qs(sel, root){ return (root||document).querySelector(sel); }
  function qsa(sel, root){ return Array.from((root||document).querySelectorAll(sel)); }

  function fmtDate(d){
    const y = d.getFullYear();
    const m = String(d.getMonth()+1).padStart(2,'0');
    const a = String(d.getDate()).padStart(2,'0');
    return `${y}-${m}-${a}`;
  }

  // ------------------- Heatmaps (weekday activity) -------------------
  function normalizeWeekdayArray(val){
    // Accepts: array[7] or object {mon..sun} or {0..6}
    if (!val) return null;
    if (Array.isArray(val)){
      if (val.length === 7) return val.map(x => Number(x)||0);
      return null;
    }
    if (typeof val === 'object'){
      const keysA = ['mon','tue','wed','thu','fri','sat','sun'];
      const keysB = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
      if (keysA.every(k => k in val) || keysB.every(k => k in val)){
        const src = (keysA.every(k => k in val)) ? keysA : keysB;
        return src.map(k => Number(val[k])||0);
      }
      // Numeric 0..6 (Mon..Sun or Sun..Sat)
      const arr = new Array(7).fill(0);
      let hasAny = false;
      Object.keys(val).forEach(k => {
        const i = parseInt(k,10);
        if (Number.isFinite(i) && i>=0 && i<7){ arr[i]=Number(val[k])||0; hasAny=true; }
      });
      return hasAny ? arr : null;
    }
    return null;
  }

  function renderHeatmaps(rows){
    const wrap = qs('#heatmapsWrap');
    const grid = qs('#heatmapsGrid');
    if (!wrap || !grid) return;
    grid.innerHTML = '';

    const { users = {} } = getMeta();
    const days = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];

    // Collect cards only for rows having activity data
    const cards = [];
    rows.forEach(r => {
      const activity = normalizeWeekdayArray(
        r.activity_by_weekday || r.activity_weekdays || r.daily_activity || null
      );
      const solved = normalizeWeekdayArray(r.solved_by_weekday || null);
      if (!activity && !solved) return;
      const totalAttempts = activity ? activity.reduce((a,b)=>a+(Number(b)||0),0) : 0;
      const totalSolved = solved ? solved.reduce((a,b)=>a+(Number(b)||0),0) : 0;
      const maxVal = Math.max(
        0,
        ...(activity ? activity.map(x => Number(x)||0) : [0]),
        ...(solved ? solved.map(x => Number(x)||0) : [0])
      );
      const name = users[r.user_id] || String(r.user_id);
      const col = document.createElement('div');
      col.className = 'col-12 col-md-6 col-lg-4';
      const card = document.createElement('div');
      card.className = 'border rounded p-3 h-100';
      const title = document.createElement('div');
      title.className = 'fw-semibold mb-2';
      title.textContent = `${name} · попыток: ${totalAttempts}${solved ? ` · решено: ${totalSolved}` : ''}`;
      const mkRow = (label, arr, baseColor) => {
        const rowWrap = document.createElement('div');
        rowWrap.className = 'mb-2';
        const lbl = document.createElement('div');
        lbl.className = 'small text-muted mb-1';
        lbl.textContent = label;
        const gridEl = document.createElement('div');
        gridEl.className = 'd-grid';
        gridEl.style.gridTemplateColumns = 'repeat(7, 1fr)';
        gridEl.style.gap = '4px';
        // headers
        days.forEach(d => {
          const h = document.createElement('div');
          h.textContent = d;
          h.className = 'text-center small text-muted';
          gridEl.appendChild(h);
        });
        // values
        (arr || new Array(7).fill(0)).forEach(v => {
          const intensity = maxVal > 0 ? (Number(v)||0)/maxVal : 0;
          const cell = document.createElement('div');
          cell.className = 'rounded text-center';
          cell.style.aspectRatio = '1 / 1';
          const [r,g,b] = baseColor; // e.g., [13,110,253]
          cell.style.backgroundColor = v ? `rgba(${r}, ${g}, ${b}, ${0.25 + 0.65*intensity})` : '#e9ecef';
          cell.style.color = (v && intensity > 0.5) ? 'white' : '#333';
          cell.style.fontSize = '0.85rem';
          cell.textContent = String(v||0);
          gridEl.appendChild(cell);
        });
        rowWrap.appendChild(lbl);
        rowWrap.appendChild(gridEl);
        return rowWrap;
      };

      card.appendChild(title);
      if (activity) card.appendChild(mkRow('Попытки по дням недели', activity, [13,110,253]));
      if (solved) card.appendChild(mkRow('Решено задач по дням недели', solved, [25,135,84]));
      col.appendChild(card);
      cards.push(col);
    });

    if (!cards.length){
      wrap.classList.add('d-none');
      return;
    }
    cards.forEach(c => grid.appendChild(c));
    wrap.classList.remove('d-none');
  }

  function setInvalid(el, enable){
    if (!el) return;
    if (enable){ el.classList.add('is-invalid'); }
    else { el.classList.remove('is-invalid'); }
  }

  function ensureFeedback(el, msg){
    if (!el) return;
    let fb = el.parentElement && el.parentElement.querySelector('.invalid-feedback');
    if (!fb){
      fb = document.createElement('div');
      fb.className = 'invalid-feedback';
      el.parentElement && el.parentElement.appendChild(fb);
    }
    fb.textContent = msg || '';
  }

  function clearInvalid(){
    ['#studentPicker', '#evalFilters select[name="topic_id"]', '#period_week'].forEach(sel => {
      const el = qs(sel);
      if (el){ setInvalid(el, false); const fb = el.parentElement && el.parentElement.querySelector('.invalid-feedback'); if (fb) fb.textContent = ''; }
    });
  }

  function validateFilters(){
    clearInvalid();
    const usersSel = qs('#evalFilters select[name="user_ids"]');
    const topicSel = qs('#evalFilters select[name="topic_id"]');
    const weekEl = qs('#period_week');
    let ok = true;
    const userIds = toIntArray(usersSel);
    if (!userIds.length){
      const picker = qs('#studentPicker');
      setInvalid(picker, true);
      ensureFeedback(picker, 'Выберите хотя бы одного студента');
      ok = false;
    }
    if (!topicSel || !topicSel.value){
      setInvalid(topicSel, true);
      ensureFeedback(topicSel, 'Выберите тему');
      ok = false;
    }
    // Week is optional; if needed, we could enforce here
    return ok;
  }

  function startOfWeek(d){
    const dt = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const day = dt.getDay(); // 0..6; Sun=0
    const iso = (day === 0 ? 7 : day); // 1..7 Mon..Sun
    dt.setDate(dt.getDate() - (iso - 1));
    return dt;
  }
  function endOfWeek(d){ const s = startOfWeek(d); const e = new Date(s); e.setDate(s.getDate()+6); return e; }
  function startOfMonth(d){ return new Date(d.getFullYear(), d.getMonth(), 1); }
  function endOfMonth(d){ return new Date(d.getFullYear(), d.getMonth()+1, 0); }

  function showFlashMessage(type, msg){
    // Use the global flash messages container from base.html
    const flashContainer = qs('#flash-messages') || qs('.container');
    if (!flashContainer) {
      console.warn('Flash container not found, falling back to console');
      console.log(`${type.toUpperCase()}: ${msg}`);
      return;
    }
    
    const cls = {'error':'danger','warning':'warning','success':'success','info':'info'}[type] || 'secondary';
    const alertEl = document.createElement('div');
    alertEl.className = 'position-relative';
    alertEl.style.zIndex = '1020';
    alertEl.innerHTML = `<div class="alert alert-${cls} alert-dismissible fade show" role="alert">
      ${msg}
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Закрыть"></button>
    </div>`;
    
    // Insert at the beginning of flash container or create container if needed
    if (flashContainer.id === 'flash-messages') {
      flashContainer.querySelector('.position-relative')?.appendChild(alertEl.firstElementChild) || 
      flashContainer.appendChild(alertEl);
    } else {
      // Create flash container if it doesn't exist
      let flashWrap = flashContainer.querySelector('#flash-messages');
      if (!flashWrap) {
        flashWrap = document.createElement('div');
        flashWrap.id = 'flash-messages';
        flashWrap.className = 'mt-3';
        flashWrap.innerHTML = '<div class="position-relative" style="z-index: 1020;"></div>';
        flashContainer.insertBefore(flashWrap, flashContainer.firstChild);
      }
      flashWrap.querySelector('.position-relative').appendChild(alertEl.firstElementChild);
    }
  }

  function buildErrorMessage(status, data, rawText){
    // Prefer structured errors from backend
    if (data && Array.isArray(data.errors) && data.errors.length){
      const items = data.errors.map(e => `<li>${String(e)}</li>`).join('');
      return `<strong>Ошибка запроса (${status})</strong><br><ul class="mb-0">${items}</ul>`;
    }
    // Common auth/permission cases
    if (status === 401) return `<strong>401</strong>: Требуется вход в систему.`;
    if (status === 403) return `<strong>403</strong>: Недостаточно прав (нужно быть администратором).`;
    if (status === 400) return `<strong>400</strong>: Некорректные параметры. Проверьте выбранных студентов, темы и диапазон дат.`;
    if (status >= 500) return `<strong>${status}</strong>: Внутренняя ошибка сервера. Попробуйте позже.`;
    // Fallback to any text
    if (rawText) return `Ошибка запроса (${status}).<br><small class="text-muted">${rawText.substring(0, 400)}</small>`;
    return `Ошибка запроса (${status}).`;
  }

  function toIntArray(selectEl){
    if (!selectEl) return [];
    return Array.from(selectEl.selectedOptions || []).map(o => parseInt(o.value, 10)).filter(Number.isFinite);
  }

  function clear(el){ if (el) el.innerHTML = ''; }

  // ------------------- Charts (Chart.js) -------------------
  let chartGrouped = null;
  let chartRadar = null;

  // Lazy loader for Chart.js if not present (CDN fallback)
  let chartJsLoading = null;
  function ensureChartJsLoaded(){
    if (window.Chart) return Promise.resolve();
    if (chartJsLoading) return chartJsLoading;
    chartJsLoading = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js';
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Chart.js failed to load'));
      document.head.appendChild(script);
    });
    return chartJsLoading;
  }

  function getMeta(){
    try{
      const metaEl = qs('#eval-meta');
      if (metaEl && metaEl.textContent){ return JSON.parse(metaEl.textContent); }
    }catch(e){ /* noop */ }
    return { users: {}, topics: {} };
  }

  function destroyCharts(){
    if (chartGrouped){ chartGrouped.destroy(); chartGrouped = null; }
    if (chartRadar){ chartRadar.destroy(); chartRadar = null; }
  }

  function toPct(v){ return v == null ? null : Math.round((v*100)); }

  function buildChartDatasets(rows){
    const { users = {} } = getMeta();
    // Prepare labels per student and data arrays
    const studentLabels = [];
    const dataAccuracy = [];
    const dataTime = [];
    const dataProg = [];
    const dataMot = [];
    const dataTotal = [];

    rows.forEach(r => {
      const name = users[r.user_id] || String(r.user_id);
      studentLabels.push(name);
      dataAccuracy.push(toPct(r.accuracy) ?? 0);
      dataTime.push(toPct(r.time_score) ?? 0);
      dataProg.push(toPct(r.progress_score) ?? 0);
      dataMot.push(toPct(r.motivation_score) ?? 0);
      dataTotal.push(toPct(r.total_score) ?? 0);
    });

    return { studentLabels, dataAccuracy, dataTime, dataProg, dataMot, dataTotal };
  }

  function renderCharts(rows){
    const wrap = qs('#chartsWrap');
    if (!wrap) return;
    if (!rows || !rows.length){
      wrap.classList.add('d-none');
      destroyCharts();
      return;
    }
    wrap.classList.remove('d-none');

    const { studentLabels, dataAccuracy, dataTime, dataProg, dataMot, dataTotal } = buildChartDatasets(rows);

    // Colors for up to 8 students
    const palette = ['#28a745','#17a2b8','#ffc107','#dc3545','#6610f2','#20c997','#fd7e14','#0dcaf0'];
    function color(i){ return palette[i % palette.length]; }

    // Grouped Bar: Accuracy, Speed, Progress, Motivation, Total per student
    const gEl = qs('#chartGrouped');
    if (gEl){
      const ctxG = gEl.getContext('2d');
      chartGrouped && chartGrouped.destroy();
      chartGrouped = new Chart(ctxG, {
        type: 'bar',
        data: {
          labels: ['Точность','Скорость','Прогресс','Мотивация','Итог'],
          datasets: studentLabels.map((name, i) => ({
            label: name,
            data: [dataAccuracy[i], dataTime[i], dataProg[i], dataMot[i], dataTotal[i]],
            backgroundColor: color(i),
            borderColor: color(i),
            borderWidth: 1
          }))
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, max: 100, title: { display: true, text: '%'} }
          },
          plugins: { legend: { position: 'top' } }
        }
      });
    }

    // Radar: profile per student (same 5 metrics)
    const rEl = qs('#chartRadar');
    if (rEl){
      const ctxR = rEl.getContext('2d');
      chartRadar && chartRadar.destroy();
      chartRadar = new Chart(ctxR, {
        type: 'radar',
        data: {
          labels: ['Точность','Скорость','Прогресс','Мотивация','Итог'],
          datasets: studentLabels.map((name, i) => ({
            label: name,
            data: [dataAccuracy[i], dataTime[i], dataProg[i], dataMot[i], dataTotal[i]],
            borderColor: color(i),
            backgroundColor: color(i) + '33',
            borderWidth: 2,
            pointRadius: 3
          }))
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: { r: { min: 0, max: 100, ticks: { stepSize: 20 } } }
        }
      });
    }
  }

  // ------------------- Config UI -------------------
  const cfg = {
    alpha: 0.667,
    wAcc: 0.3,
    wTime: 0.2,
    wProg: 0.3,
    wMot: 0.2,
    lowMin: 0.3,
    lowMax: 0.7,
    medMin: 0.4,
    medMax: 0.8,
  };

  function clamp01(x){ return Math.min(1, Math.max(0, x)); }
  function round2(x){ return Math.round(x * 100) / 100; }
  function fmt2(x){ return (Math.round(x*100)/100).toFixed(2); }

  function cfgEls(){
    return {
      alpha: qs('#cfg_alpha'), alphaVal: qs('#cfg_alpha_val'),
      wAcc: qs('#cfg_w_acc'), wAccVal: qs('#cfg_w_acc_val'),
      wTime: qs('#cfg_w_time'), wTimeVal: qs('#cfg_w_time_val'),
      wProg: qs('#cfg_w_prog'), wProgVal: qs('#cfg_w_prog_val'),
      wMot: qs('#cfg_w_mot'), wMotVal: qs('#cfg_w_mot_val'),
      sum: qs('#cfg_weights_sum'),
      lowMin: qs('#cfg_low_min'), lowMax: qs('#cfg_low_max'), lowVals: qs('#cfg_low_vals'),
      medMin: qs('#cfg_med_min'), medMax: qs('#cfg_med_max'), medVals: qs('#cfg_med_vals'),
      save: qs('#cfg_save'), reload: qs('#cfg_reload'),
    };
  }

  function renderCfg(){
    const el = cfgEls();
    if (!el.alpha) return; // block not present
    el.alpha.value = String(cfg.alpha);
    el.alphaVal.textContent = fmt2(cfg.alpha);
    el.wAcc.value = String(cfg.wAcc); el.wAccVal.textContent = fmt2(cfg.wAcc);
    el.wTime.value = String(cfg.wTime); el.wTimeVal.textContent = fmt2(cfg.wTime);
    el.wProg.value = String(cfg.wProg); el.wProgVal.textContent = fmt2(cfg.wProg);
    el.wMot.value = String(cfg.wMot); el.wMotVal.textContent = fmt2(cfg.wMot);
    const sum = cfg.wAcc + cfg.wTime + cfg.wProg + cfg.wMot;
    el.sum.textContent = fmt2(sum);
    el.lowMin.value = String(cfg.lowMin); el.lowMax.value = String(cfg.lowMax);
    el.lowVals.textContent = `${fmt2(cfg.lowMin)}–${fmt2(cfg.lowMax)}`;
    el.medMin.value = String(cfg.medMin); el.medMax.value = String(cfg.medMax);
    el.medVals.textContent = `${fmt2(cfg.medMin)}–${fmt2(cfg.medMax)}`;
  }

  function redistributeWeights(changedKey){
    // Keep sum = 1 by scaling others proportionally
    const keys = ['wAcc','wTime','wProg','wMot'];
    const others = keys.filter(k => k !== changedKey);
    const target = clamp01(cfg[changedKey]);
    cfg[changedKey] = target;
    const rest = 1 - target;
    const currentSumOthers = others.map(k => cfg[k]).reduce((a,b)=>a+b,0);
    if (currentSumOthers <= 0){
      const share = rest / others.length;
      others.forEach(k => cfg[k] = share);
    } else {
      others.forEach(k => cfg[k] = (cfg[k] / currentSumOthers) * rest);
    }
    // minor rounding to two decimals and fix drift
    let sum = keys.map(k => cfg[k]).reduce((a,b)=>a+b,0);
    if (Math.abs(sum - 1) > 1e-6){
      const diff = 1 - sum;
      // add diff to the largest other to keep exact 1
      let best = others[0];
      others.forEach(k => { if (cfg[k] > cfg[best]) best = k; });
      cfg[best] = clamp01(cfg[best] + diff);
    }
  }

  async function loadCfg(){
    try{
      const resp = await fetch('/admin/api/evaluation_config', { credentials: 'same-origin' });
      const data = await resp.json();
      if (data && data.ok && data.data){
        const d = data.data;
        cfg.alpha = Number(d.engagement_weight_alpha ?? cfg.alpha);
        cfg.wAcc = Number(d.weight_accuracy ?? cfg.wAcc);
        cfg.wTime = Number(d.weight_time ?? cfg.wTime);
        cfg.wProg = Number(d.weight_progress ?? cfg.wProg);
        cfg.wMot = Number(d.weight_motivation ?? cfg.wMot);
        cfg.lowMin = Number(d.min_threshold_low ?? cfg.lowMin);
        cfg.lowMax = Number(d.max_threshold_low ?? cfg.lowMax);
        cfg.medMin = Number(d.min_threshold_medium ?? cfg.medMin);
        cfg.medMax = Number(d.max_threshold_medium ?? cfg.medMax);
        renderCfg();
      }
    } catch(e){ console.warn('Failed to load evaluation config', e); }
  }

  async function saveCfg(){
    try{
      const csrfEl = qs('input[name="csrf_token"]');
      const csrf = csrfEl && csrfEl.value ? csrfEl.value : null;
      const payload = {
        engagement_weight_alpha: round2(cfg.alpha),
        weight_accuracy: round2(cfg.wAcc),
        weight_time: round2(cfg.wTime),
        weight_progress: round2(cfg.wProg),
        weight_motivation: round2(cfg.wMot),
        min_threshold_low: round2(cfg.lowMin),
        max_threshold_low: round2(cfg.lowMax),
        min_threshold_medium: round2(cfg.medMin),
        max_threshold_medium: round2(cfg.medMax),
      };
      const resp = await fetch('/admin/api/evaluation_config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRFToken': csrf } : {}) },
        credentials: 'same-origin',
        body: JSON.stringify(payload)
      });
      const data = await resp.json().catch(()=>({}));
      const alerts = qs('#evalAlerts');
      if (!resp.ok || !data.ok){
        showFlashMessage('error', 'Не удалось сохранить конфигурацию');
      } else {
        showFlashMessage('success', 'Конфигурация сохранена');
      }
    } catch(e){
      const alerts = qs('#evalAlerts');
      showFlashMessage('error', 'Ошибка сохранения конфигурации');
    }
  }

  function wireCfg(){
    const el = cfgEls();
    if (!el.alpha) return;
    // alpha
    el.alpha.addEventListener('input', () => { cfg.alpha = clamp01(parseFloat(el.alpha.value)||0); el.alphaVal.textContent = fmt2(cfg.alpha); });
    // weights
    function hook(id, key){
      const inp = el[id];
      if (!inp) return;
      inp.addEventListener('input', () => {
        cfg[key] = clamp01(parseFloat(inp.value)||0);
        redistributeWeights(key);
        renderCfg();
      });
    }
    hook('wAcc','wAcc');
    hook('wTime','wTime');
    hook('wProg','wProg');
    hook('wMot','wMot');
    // thresholds: ensure min<=max per band
    function clampBand(minKey, maxKey, minEl, maxEl, labelEl){
      const vmin = clamp01(parseFloat(minEl.value)||0);
      const vmax = clamp01(parseFloat(maxEl.value)||0);
      if (vmin <= vmax){ cfg[minKey]=vmin; cfg[maxKey]=vmax; }
      else { cfg[minKey]=vmax; cfg[maxKey]=vmin; }
      labelEl.textContent = `${fmt2(cfg[minKey])}–${fmt2(cfg[maxKey])}`;
      minEl.value = String(cfg[minKey]);
      maxEl.value = String(cfg[maxKey]);
    }
    el.lowMin.addEventListener('input', ()=> clampBand('lowMin','lowMax', el.lowMin, el.lowMax, el.lowVals));
    el.lowMax.addEventListener('input', ()=> clampBand('lowMin','lowMax', el.lowMin, el.lowMax, el.lowVals));
    el.medMin.addEventListener('input', ()=> clampBand('medMin','medMax', el.medMin, el.medMax, el.medVals));
    el.medMax.addEventListener('input', ()=> clampBand('medMin','medMax', el.medMin, el.medMax, el.medVals));

    // actions
    el.save && el.save.addEventListener('click', saveCfg);
    el.reload && el.reload.addEventListener('click', () => { loadCfg(); });
  }

  function renderRows(tbody, rows){
    clear(tbody);
    let meta = null;
    try {
      const metaEl = qs('#eval-meta');
      if (metaEl && metaEl.textContent) meta = JSON.parse(metaEl.textContent);
    } catch(e){ meta = null; }
    const usersMap = (meta && meta.users) || {};
    const topicsMap = (meta && meta.topics) || {};
    rows.forEach(r => {
      const tr = document.createElement('tr');
      const cells = [];
      // Map we have: accuracy, time_score, progress_score, motivation_score, total_score, a1,a2,a3, attempts_total, tasks_solved, tasks_total, avg_time, level_before, level_after
      const fmtPct = v => (v == null ? '—' : (Math.round(v*1000)/10 + '%'));
      const fmtNum = v => (v == null ? '—' : String(v));

      cells.push(`<td>${usersMap[r.user_id] || r.user_id}</td>`);
      cells.push(`<td><span class="badge bg-secondary">${r.level_before || '—'}</span></td>`);
      const change = (r.level_change || 'stay');
      const nextCls = change === 'up' ? 'bg-success' : (change === 'down' ? 'bg-danger' : (change === 'mastered' ? 'bg-primary' : 'bg-info'));
      cells.push(`<td><span class="badge ${nextCls}">${r.level_after || '—'}</span></td>`);
      cells.push(`<td>${fmtPct(r.accuracy)}</td>`);
      cells.push(`<td>${fmtPct(r.time_score)}</td>`);
      cells.push(`<td>${fmtPct(r.progress_score)}</td>`);
      cells.push(`<td>${fmtPct(r.motivation_score)}</td>`);
      cells.push(`<td><strong>${fmtPct(r.total_score)}</strong></td>`);
      cells.push(`<td>${fmtNum(r.a1)}</td>`);
      cells.push(`<td>${fmtNum(r.a2)}</td>`);
      cells.push(`<td>${fmtNum(r.a3)}</td>`);
      cells.push(`<td>${fmtNum(r.tasks_solved)}</td>`);
      cells.push(`<td>${r.avg_time != null ? Math.round(r.avg_time) : '—'}</td>`);

      tr.innerHTML = cells.join('');
      tbody.appendChild(tr);
    });
  }

  function renderSelectedStudentTags(){
    const container = qs('#selectedStudents');
    const hiddenSel = qs('#evalFilters select[name="user_ids"]');
    if (!container || !hiddenSel) return;
    clear(container);
    const selected = Array.from(hiddenSel.options).filter(o => o.selected);
    selected.forEach(o => {
      const wrap = document.createElement('div');
      wrap.className = 'badge bg-light text-dark border d-inline-flex align-items-center px-2 py-1';
      wrap.dataset.userId = String(o.value);
      const nameSpan = document.createElement('span');
      nameSpan.textContent = o.textContent || o.value;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-sm btn-link text-danger p-0 ms-2';
      btn.setAttribute('aria-label', 'Удалить');
      btn.dataset.removeUser = String(o.value);
      btn.textContent = '✕';
      wrap.appendChild(nameSpan);
      wrap.appendChild(btn);
      container.appendChild(wrap);
    });
  }

  function wireStudentPicker(){
    const picker = qs('#studentPicker');
    const hiddenSel = qs('#evalFilters select[name="user_ids"]');
    const tags = qs('#selectedStudents');
    if (!picker || !hiddenSel || !tags) return;

    // Remove already selected users from picker on init
    const selectedIds = new Set(Array.from(hiddenSel.options).filter(o => o.selected).map(o => o.value));
    Array.from(picker.options).forEach(opt => {
      if (opt.value && selectedIds.has(opt.value)) {
        opt.remove();
      }
    });
    // Render tags initially
    renderSelectedStudentTags();

    // When user picks from dropdown
    picker.addEventListener('change', function(){
      const val = picker.value;
      if (!val) return;
      setInvalid(picker, false);
      // Mark in hidden select as selected
      const hiddenOpt = Array.from(hiddenSel.options).find(o => o.value === val);
      if (hiddenOpt) hiddenOpt.selected = true;
      // Remove from picker to avoid duplicates and reset value
      const pickOpt = Array.from(picker.options).find(o => o.value === val);
      if (pickOpt) pickOpt.remove();
      picker.value = '';
      // Re-render tags
      renderSelectedStudentTags();
    });

    // Remove tag -> unselect hidden and add back to picker
    tags.addEventListener('click', function(e){
      const btn = e.target.closest('[data-remove-user]');
      if (!btn) return;
      e.preventDefault();
      const id = String(btn.dataset.removeUser);
      // Unselect in hidden
      const hiddenOpt = Array.from(hiddenSel.options).find(o => o.value === id);
      if (hiddenOpt) hiddenOpt.selected = false;
      // Add back to picker (preserve label)
      if (!Array.from(picker.options).some(o => o.value === id)){
        const label = hiddenOpt ? (hiddenOpt.textContent || id) : id;
        const opt = document.createElement('option');
        opt.value = id;
        opt.textContent = label;
        picker.appendChild(opt);
      }
      // Re-render tags
      renderSelectedStudentTags();
    });
    // Clear invalid on topic/week changes
    const topicSel = qs('#evalFilters select[name="topic_id"]');
    if (topicSel){ topicSel.addEventListener('change', () => setInvalid(topicSel, false)); }
    const weekEl = qs('#period_week');
    if (weekEl){ weekEl.addEventListener('change', () => setInvalid(weekEl, false)); }
  }

  async function doPreview(){
    const alerts = qs('#evalAlerts');
    const tableWrap = qs('#resultsWrap');
    const tbody = qs('#resultsTable tbody');
    clear(alerts);

    // Client-side validation
    if (!validateFilters()){
      showFlashMessage('warning', 'Заполните обязательные фильтры.');
      return;
    }

    const usersSel = qs('#evalFilters select[name="user_ids"]');
    const topicSel = qs('#evalFilters select[name="topic_id"]');
    const weekEl = qs('#period_week');

    // Compute period from ISO week input (YYYY-Www) if provided
    let period_start = null, period_end = null;
    if (weekEl && weekEl.value) {
      const m = weekEl.value.match(/^(\d{4})-W(\d{2})$/);
      if (m){
        const year = parseInt(m[1], 10);
        const week = parseInt(m[2], 10);
        const range = isoWeekToRange(year, week);
        period_start = fmtDate(range.start);
        period_end = fmtDate(range.end);
      }
    }
    const topic_id = topicSel && topicSel.value ? parseInt(topicSel.value, 10) : null;
    const payload = {
      user_ids: toIntArray(usersSel),
      topic_id: topic_id,
      topic_ids: topic_id != null ? [topic_id] : [], // backward compatibility
      period_start: period_start,
      period_end: period_end,
    };

    if (!payload.user_ids.length){
      showFlashMessage('warning', 'Выберите хотя бы одного студента.');
      return;
    }
    if (payload.topic_id == null){
      showFlashMessage('warning', 'Выберите тему.');
      return;
    }

    try {
      const csrfEl = qs('input[name="csrf_token"]');
      const csrf = csrfEl && csrfEl.value ? csrfEl.value : null;
      const resp = await fetch('/admin/evaluation/preview', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrf ? { 'X-CSRFToken': csrf } : {}),
          'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin',
        body: JSON.stringify(payload)
      });
      const ct = resp.headers.get('Content-Type') || '';
      let data = {};
      let rawText = '';
      if (ct.includes('application/json')) {
        data = await resp.json().catch(() => ({}));
      } else {
        rawText = await resp.text().catch(() => '');
      }
      if (!resp.ok || data.ok === false){
        const msg = buildErrorMessage(resp.status, data, rawText);
        showFlashMessage('error', msg);
        // If backend reported validation errors, try to map to fields
        if (data && Array.isArray(data.errors)){
          const txt = data.errors.join(' ').toLowerCase();
          if (txt.includes('студент')){ const picker = qs('#studentPicker'); setInvalid(picker, true); ensureFeedback(picker, 'Нужно выбрать хотя бы одного студента'); }
          if (txt.includes('тема')){ const topicSel = qs('#evalFilters select[name="topic_id"]'); setInvalid(topicSel, true); ensureFeedback(topicSel, 'Нужно выбрать тему'); }
          if (txt.includes('конец периода')){ const weekEl = qs('#period_week'); setInvalid(weekEl, true); ensureFeedback(weekEl, 'Некорректный диапазон недели'); }
        }
        return;
      }

      const rows = Array.isArray(data.results) ? data.results : [];
      if (!rows.length){
        showFlashMessage('info', 'Нет данных за выбранный период.');
      }
      renderRows(tbody, rows);
      tableWrap.classList.toggle('d-none', rows.length === 0);
      // Ensure Chart.js is available, then render charts
      try{
        await ensureChartJsLoaded();
        renderCharts(rows);
      } catch (e) {
        console.warn('Charts disabled:', e);
        const chartsWrap = qs('#chartsWrap');
        chartsWrap && chartsWrap.classList.add('d-none');
        const alerts = qs('#evalAlerts');
        showFlashMessage('warning', 'Визуализация недоступна: не удалось загрузить Chart.js');
      }
      // Heatmaps (do not depend on Chart.js)
      renderHeatmaps(rows);
    } catch (e){
      console.error(e);
      const msg = (e && e.message) ? `Не удалось выполнить запрос: ${e.message}` : 'Не удалось выполнить запрос. Проверьте соединение.';
      showFlashMessage('error', msg);
    }
  }

  function isoWeekToRange(isoYear, isoWeek){
    // ISO week: Thursday of week 1 is Jan 4th logic
    const simple = new Date(Date.UTC(isoYear, 0, 4));
    const dayOfWeek = simple.getUTCDay() || 7; // 1..7
    const thursday = new Date(simple);
    thursday.setUTCDate(simple.getUTCDate() + (4 - dayOfWeek));
    const weekStart = new Date(thursday);
    weekStart.setUTCDate(thursday.getUTCDate() - 3 + (isoWeek - 1) * 7); // Monday
    const start = new Date(weekStart.getUTCFullYear(), weekStart.getUTCMonth(), weekStart.getUTCDate());
    const end = new Date(start); end.setDate(start.getDate()+6);
    return { start, end };
  }

  function wireWeekPresets(){
    const weekEl = qs('#period_week');
    qsa('[\n      data-week-preset\n    ]').forEach(btn => {
      btn.addEventListener('click', function(){
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        let from = startOfWeek(today);
        if (btn.getAttribute('data-week-preset') === 'prev'){
          from = new Date(from); from.setDate(from.getDate()-7);
        }
        const y = from.getFullYear();
        // Compute ISO week number for display in input type=week
        function isoWeek(date){
          const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
          const dayNum = d.getUTCDay() || 7;
          d.setUTCDate(d.getUTCDate() + 4 - dayNum);
          const yearStart = new Date(Date.UTC(d.getUTCFullYear(),0,1));
          const weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
          return { year: d.getUTCFullYear(), week: weekNo };
        }
        const iw = isoWeek(from);
        weekEl.value = `${iw.year}-W${String(iw.week).padStart(2,'0')}`;
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function(){
    const btn = qs('#previewRunBtn');
    if (btn) btn.addEventListener('click', doPreview);
    wireWeekPresets();
    wireStudentPicker();
    wireCfg();
    loadCfg();
  });
})();
