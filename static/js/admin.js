(() => {
  const sidebar = document.getElementById('sidebar');
  document.getElementById('sidebar-toggle')?.addEventListener('click', () => sidebar?.classList.toggle('open'));

  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', event => {
      if (form.hasAttribute('data-bulk-form') && ![...form.elements].some(item => item.name === 'ids' && item.checked)) {
        event.preventDefault();
        window.alert('Selecciona por lo menos un elemento.');
        return;
      }
      if (!window.confirm(form.dataset.confirm || '¿Confirmas esta acción?')) event.preventDefault();
    });
  });

  document.querySelectorAll('[data-select-all]').forEach(master => {
    const scope = master.dataset.selectAll;
    const items = [...document.querySelectorAll(`[data-select-item="${scope}"]`)];
    const counter = document.querySelector(`[data-selected-count="${scope}"]`);
    const update = () => {
      const checked = items.filter(item => item.checked).length;
      if (counter) counter.textContent = `${checked} seleccionado${checked === 1 ? '' : 's'}`;
      master.checked = items.length > 0 && checked === items.length;
      master.indeterminate = checked > 0 && checked < items.length;
    };
    master.addEventListener('change', () => { items.forEach(item => { item.checked = master.checked; }); update(); });
    items.forEach(item => item.addEventListener('change', update));
    update();
  });

  const chartNode = document.getElementById('chart-data');
  if (chartNode && window.Chart) {
    const data = JSON.parse(chartNode.textContent);
    Chart.defaults.font.family = "Inter, Segoe UI, sans-serif";
    Chart.defaults.color = '#6b7d76';
    const grid = { color: 'rgba(28, 68, 58, .08)' };
    const common = { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { usePointStyle: true, boxWidth: 8 } } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { precision: 0 }, grid } } };
    const movementChart = new Chart(document.getElementById('daily-chart'), { type: 'line', data: { labels: data.labels, datasets: [
      { label: 'Entradas', data: data.entries, borderColor: '#1d6b59', backgroundColor: 'rgba(29,107,89,.12)', fill: true, tension: .35 },
      { label: 'Salidas', data: data.exits, borderColor: '#c79b3b', backgroundColor: 'rgba(199,155,59,.08)', fill: true, tension: .35 }
    ] }, options: common });
    new Chart(document.getElementById('hourly-chart'), { type: 'bar', data: { labels: data.hours, datasets: [{ label: 'Entradas', data: data.entries_by_hour, backgroundColor: '#1d6b59', borderRadius: 5 }] }, options: { ...common, plugins: { legend: { display: false } } } });
    const careerChart = new Chart(document.getElementById('career-chart'), { type: 'doughnut', data: { labels: data.careers.length ? data.careers : ['Sin actividad'], datasets: [{ data: data.career_values.length ? data.career_values : [1], backgroundColor: ['#1d6b59','#c79b3b','#357a8a','#735d99','#b45c55','#7c8f62','#57946f','#c27245','#496aa3','#957458','#7391a1','#ad6c86'], borderWidth: 0 }] }, options: { responsive: true, maintainAspectRatio: false, cutout: '64%', plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8 } } } } });

    const periodName = value => ({ day: 'Día', week: 'Semana', month: 'Mes', year: 'Año' }[value] || 'Semana');
    async function fetchChart(period, career) {
      const params = new URLSearchParams({ period });
      if (career) params.set('career', career);
      const response = await fetch(`/admin/charts/data?${params}`);
      if (!response.ok) throw new Error('No fue posible actualizar la gráfica');
      return response.json();
    }
    async function updateMovementChart() {
      const period = document.getElementById('movement-period').value;
      const career = document.getElementById('movement-career').value;
      const next = await fetchChart(period, career);
      movementChart.data.labels = next.labels;
      movementChart.data.datasets[0].data = next.entries;
      movementChart.data.datasets[1].data = next.exits;
      movementChart.update();
      document.getElementById('movement-chart-caption').textContent = `${periodName(period)} · ${career || 'todas las carreras'} · ${next.start} a ${next.end}`;
    }
    async function updateCareerChart() {
      const period = document.getElementById('career-period').value;
      const career = document.getElementById('career-select').value;
      const next = await fetchChart(period, career);
      careerChart.data.labels = next.careers.length ? next.careers : ['Sin actividad'];
      careerChart.data.datasets[0].data = next.career_values.length ? next.career_values : [1];
      careerChart.update();
      document.getElementById('career-chart-caption').textContent = `Entradas · ${periodName(period).toLowerCase()} · ${career || 'todas las carreras'}`;
    }
    ['movement-period','movement-career'].forEach(id => document.getElementById(id)?.addEventListener('change', () => updateMovementChart().catch(() => {})));
    ['career-period','career-select'].forEach(id => document.getElementById(id)?.addEventListener('change', () => updateCareerChart().catch(() => {})));
  }

  if (document.getElementById('inside-groups')) {
    setInterval(async () => {
      try {
        const response = await fetch('/api/inside/grouped');
        if (!response.ok) return;
        const data = await response.json();
        document.getElementById('inside-count').textContent = data.all.length;
        document.getElementById('inside-student-count').textContent = data.student_count;
        document.getElementById('inside-personnel-count').textContent = data.personnel_count;
        const card = row => `<article class="inside-card"><img src="${escapeHtml(row.student.photo)}" alt=""><div><h3>${escapeHtml(row.student.name)}</h3><span class="mono">${escapeHtml(row.student.matricula)}</span><p>${escapeHtml(row.student.career)} · ${escapeHtml(row.student.campus)}</p><div class="inside-meta"><span><i class="fa-solid fa-right-to-bracket"></i> ${row.entered_at}</span><span><i class="fa-regular fa-clock"></i> ${row.duration_minutes} min</span></div></div></article>`;
        const section = (title, icon, groups, empty) => `<section><div class="inside-section-heading"><h2><i class="fa-solid ${icon}"></i> ${title}</h2></div>${Object.entries(groups).map(([name, rows]) => `<article class="inside-group"><header><h3>${escapeHtml(name)}</h3><span>${rows.length}</span></header><div class="people-grid">${rows.map(card).join('')}</div></article>`).join('') || `<div class="empty-state compact-empty">${empty}</div>`}</section>`;
        document.getElementById('inside-groups').innerHTML = section('Alumnos por carrera o grupo', 'fa-user-graduate', data.students, 'No hay alumnos dentro.') + section('Docentes y personal autorizado', 'fa-chalkboard-user', data.personnel, 'No hay personal dentro.');
      } catch (_) { /* Mantiene el último estado visible. */ }
    }, 15000);
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  }
})();
