(function(){
  let loaded = false;        // data fetched
  let charts = {};           // chart instances and cache

  function $(id){ return document.getElementById(id); }

  function fmtPct(x){
    return (Math.round((x || 0) * 1000) / 10) + '%';
  }

  function buildHeatmapConfig(canvasId, topics, values, title){
    // values: array of {topic_name, prev, curr}; x = ['prev','curr']
    const yLabels = topics;
    const xLabels = ['prev', 'curr'];
    const data = [];
    for (let i = 0; i < yLabels.length; i++){
      const t = yLabels[i];
      const row = values.find(v => v.topic_name === t) || {prev: 0, curr: 0};
      data.push({x: 'prev', y: t, v: row.prev || 0});
      data.push({x: 'curr', y: t, v: row.curr || 0});
    }
    const vmax = Math.max(1, ...data.map(d => d.v || 0));
    const color = (v) => {
      // blue scale
      const ratio = v / vmax;
      const r = Math.round(30 + 100 * ratio);
      const g = Math.round(144 + 50 * ratio);
      const b = Math.round(255 * ratio);
      return `rgba(${r}, ${g}, ${b}, ${Math.max(0.15, 0.15 + 0.75*ratio)})`;
    };

    return {
      type: 'matrix',
      data: {
        datasets: [{
          label: title,
          data: data,
          backgroundColor: ctx => color(ctx.raw.v || 0),
          // chart.chartArea может быть не вычислен на первом проходе — подстрахуемся
          width: ({chart}) => {
            const ca = chart.chartArea || { width: Math.max(120, chart.width || 240) };
            return Math.max(20, (ca.width / xLabels.length) - 8);
          },
          height: ({chart}) => {
            const ca = chart.chartArea || { height: Math.max(100, chart.height || 200) };
            return Math.max(18, (ca.height / yLabels.length) - 6);
          },
          borderWidth: 1,
          borderColor: 'rgba(0,0,0,0.05)'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { type: 'category', labels: xLabels, grid: { display: false }, title: { display: true, text: 'Неделя' } },
          y: { type: 'category', labels: yLabels, grid: { display: false }, title: { display: true, text: 'Тема' } }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title(items){ return items[0].raw.y + ' — ' + items[0].raw.x; },
              label(ctx){ return `Значение: ${ctx.raw.v}`; }
            }
          }
        }
      }
    };
  }

  function buildBarConfig(canvasId, labels, values, title){
    return {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: title,
          data: values,
          backgroundColor: 'rgba(54, 162, 235, 0.6)'
        }]
      },
      options: {
        animation: { duration: 0 },
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0 }},
          y: { }
        }
      }
    };
  }

  function buildLineConfig(prevRate, currRate){
    return {
      type: 'line',
      data: {
        labels: ['Прошлая', 'Текущая'],
        datasets: [{
          label: 'Success rate',
          data: [prevRate * 100, currRate * 100],
          borderColor: 'rgba(75, 192, 192, 1)',
          backgroundColor: 'rgba(75, 192, 192, 0.2)',
          fill: false,
          tension: 0,
          pointRadius: 4
        }]
      },
      options: {
        animation: { duration: 0 },
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (ctx) => `${ctx.parsed.y.toFixed(1)}%` } }
        },
        scales: {
          y: { beginAtZero: true, suggestedMax: 100, ticks: { callback: (v) => v + '%' } }
        }
      }
    };
  }

  function aggregateTopics(by_topic_prev, by_topic_curr){
    const names = new Set();
    (by_topic_prev || []).forEach(r => names.add(r.topic_name));
    (by_topic_curr || []).forEach(r => names.add(r.topic_name));
    const topics = Array.from(names).sort((a,b)=>a.localeCompare(b));

    const attemptsMap = topics.map(name => ({ topic_name: name,
      prev: (by_topic_prev.find(r=>r.topic_name===name)||{}).attempts || 0,
      curr: (by_topic_curr.find(r=>r.topic_name===name)||{}).attempts || 0,
    }));
    const solvedMap = topics.map(name => ({ topic_name: name,
      prev: (by_topic_prev.find(r=>r.topic_name===name)||{}).solved || 0,
      curr: (by_topic_curr.find(r=>r.topic_name===name)||{}).solved || 0,
    }));
    return { topics, attemptsMap, solvedMap };
  }

  async function loadStats(){
    const resp = await fetch('/student/profile/stats.json');
    if (!resp.ok){ throw new Error('Failed to fetch stats'); }
    return resp.json();
  }

  function renderAll(payload){
    // Week labels
    const prevLabel = `${payload.weeks.prev.start} — ${payload.weeks.prev.end}`;
    const currLabel = `${payload.weeks.curr.start} — ${payload.weeks.curr.end}`;
    const prevBadge = $('week-prev-label'); if (prevBadge) prevBadge.innerText = `Прошлая неделя: ${prevLabel}`;
    const currBadge = $('week-curr-label'); if (currBadge) currBadge.innerText = `Текущая неделя: ${currLabel}`;

    const {topics, attemptsMap, solvedMap} = aggregateTopics(payload.by_topic.prev, payload.by_topic.curr);

    // Heatmaps
    if ($('heatAttempts')){
      charts.heatAttempts?.destroy?.();
      charts.heatAttempts = new Chart($('heatAttempts').getContext('2d'),
        buildHeatmapConfig('heatAttempts', topics, attemptsMap, 'Попытки'));
    }
    if ($('heatSolved')){
      charts.heatSolved?.destroy?.();
      charts.heatSolved = new Chart($('heatSolved').getContext('2d'),
        buildHeatmapConfig('heatSolved', topics, solvedMap, 'Решено'));
    }

    // Top-5 bars
    const prevTop = (payload.top5_by_solved_tasks.prev || []).map(r => ({name: r.topic_name, val: r.solved_tasks_count}));
    const currTop = (payload.top5_by_solved_tasks.curr || []).map(r => ({name: r.topic_name, val: r.solved_tasks_count}));
    if ($('barTopPrev')){
      charts.barTopPrev?.destroy?.();
      charts.barTopPrev = new Chart($('barTopPrev').getContext('2d'),
        buildBarConfig('barTopPrev', prevTop.map(x=>x.name), prevTop.map(x=>x.val), 'Решённые задачи'));
    }
    if ($('barTopCurr')){
      charts.barTopCurr?.destroy?.();
      charts.barTopCurr = new Chart($('barTopCurr').getContext('2d'),
        buildBarConfig('barTopCurr', currTop.map(x=>x.name), currTop.map(x=>x.val), 'Решённые задачи'));
    }

    // Success rate line (totals)
    const prevSR = (payload.totals.prev && payload.totals.prev.success_rate) || 0;
    const currSR = (payload.totals.curr && payload.totals.curr.success_rate) || 0;
    if ($('lineSuccessRate')){
      charts.lineSuccessRate?.destroy?.();
      charts.lineSuccessRate = new Chart($('lineSuccessRate').getContext('2d'),
        buildLineConfig(prevSR, currSR));
    }
  }

  async function ensureDataAndRender(){
    try {
      if (!charts._dataLoaded){
        const payload = await loadStats();
        charts._dataLoaded = true;
        charts._payload = payload;
        renderAll(payload);
      } else if (charts._payload) {
        renderAll(charts._payload);
      }
    } catch(e){ console.error(e); }
  }

  function destroyCharts(){
    Object.keys(charts).forEach(k => {
      if (charts[k] && typeof charts[k].destroy === 'function'){
        try { charts[k].destroy(); } catch(_){}
      }
    });
    charts = { _dataLoaded: charts._dataLoaded, _payload: charts._payload };
  }

  function initInlineToggle(){
    const section = document.getElementById('weeklyStatsSection');
    const toggleBtn = document.getElementById('statsToggleBtn');
    const refreshBtn = document.getElementById('statsRefreshBtn');
    if (!section || !toggleBtn) return;

    toggleBtn.addEventListener('click', async () => {
      const isHidden = section.style.display === 'none';
      section.style.display = isHidden ? 'block' : 'none';
      toggleBtn.innerHTML = isHidden
        ? '<i class="fas fa-chart-line"></i> Скрыть статистику'
        : '<i class="fas fa-chart-line"></i> Показать статистику';
      refreshBtn.style.display = isHidden ? 'inline-block' : 'none';
      if (isHidden) {
        await ensureDataAndRender();
      } else {
        // освобождаем ресурсы графиков
        destroyCharts();
      }
    });

    if (refreshBtn){
      refreshBtn.addEventListener('click', async () => {
        charts._dataLoaded = false;
        charts._payload = null;
        destroyCharts();
        await ensureDataAndRender();
      });
    }
  }

  function initOnce(){
    if (loaded) return; loaded = true;
    initInlineToggle();
  }

  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', initOnce);
  } else {
    initOnce();
  }
})();
