/* FitPulse — main application JavaScript */

// ── Theme Toggle ─────────────────────────────────────────────
(function initTheme() {
  const saved = localStorage.getItem('fp-theme') || 'light';
  document.documentElement.setAttribute('data-bs-theme', saved);
  updateThemeIcon(saved);
})();

function updateThemeIcon(theme) {
  const icon = document.getElementById('themeIcon');
  if (!icon) return;
  icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
}

document.addEventListener('DOMContentLoaded', function () {
  const btn = document.getElementById('themeToggle');
  if (btn) {
    btn.addEventListener('click', function () {
      const current = document.documentElement.getAttribute('data-bs-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-bs-theme', next);
      localStorage.setItem('fp-theme', next);
      updateThemeIcon(next);
    });
  }

  // Auto-dismiss flash alerts after 4 seconds
  document.querySelectorAll('.flash-alert').forEach(function (el) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      if (bsAlert) bsAlert.close();
    }, 4000);
  });

  // Render existing chat bubbles as markdown
  document.querySelectorAll('.chat-bubble[data-md]').forEach(renderBubble);
});

// ── Utility: password toggle ─────────────────────────────────
function togglePass(inputId, iconId) {
  const inp = document.getElementById(inputId);
  const ico = document.getElementById(iconId);
  if (inp.type === 'password') {
    inp.type = 'text';
    ico.className = 'fas fa-eye';
  } else {
    inp.type = 'password';
    ico.className = 'fas fa-eye-slash';
  }
}

// ── Utility: show toast ──────────────────────────────────────
function showToast(msg, type) {
  type = type || 'success';
  const wrap = document.createElement('div');
  wrap.style.cssText = 'position:fixed;top:70px;right:1rem;z-index:9999;';
  wrap.innerHTML = `
    <div class="alert alert-${type} alert-dismissible fade show shadow" role="alert" style="min-width:280px;border-radius:10px;">
      ${msg}
      <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    </div>`;
  document.body.appendChild(wrap);
  setTimeout(function () { wrap.remove(); }, 4000);
}

// ── Utility: render markdown bubble ─────────────────────────
function renderBubble(bubble) {
  const raw = bubble.getAttribute('data-md') || '';
  const content = bubble.querySelector('.bubble-content');
  if (content) {
    try { content.innerHTML = marked.parse(raw); }
    catch (e) { content.textContent = raw; }
  }
}

// ── Dashboard Charts ─────────────────────────────────────────
let progressChart = null;
let currentChartType = 'weight';
let chartDataGlobal = null;

function initDashboard(chartData) {
  chartDataGlobal = chartData;
  renderProgressChart('weight');
  renderMacroChart();
  initBMIRing();
}

function initBMIRing() {
  const ring = document.querySelector('.bmi-ring');
  if (!ring) return;
  const bmi = parseFloat(ring.dataset.bmi || 0);
  const circle = document.getElementById('bmiRing');
  if (!circle) return;
  const circumference = 2 * Math.PI * 40; // r=40
  // Map BMI 10–40 to ring offset
  const pct = Math.min(Math.max((bmi - 10) / 30, 0), 1);
  circle.style.strokeDasharray = circumference;
  circle.style.strokeDashoffset = circumference * (1 - pct);
  if (bmi < 18.5)      circle.style.stroke = '#3b82f6';
  else if (bmi < 25)   circle.style.stroke = '#10b981';
  else if (bmi < 30)   circle.style.stroke = '#f59e0b';
  else                 circle.style.stroke = '#ef4444';
}

function switchChart(type) {
  currentChartType = type;
  document.querySelectorAll('[onclick^="switchChart"]').forEach(function (b) {
    b.classList.toggle('active', b.getAttribute('onclick').includes(type));
  });
  renderProgressChart(type);
}

function renderProgressChart(type) {
  const ctx = document.getElementById('progressChart');
  if (!ctx || !chartDataGlobal) return;
  const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
  const gridColor = isDark ? 'rgba(255,255,255,.08)' : 'rgba(0,0,0,.06)';
  const textColor = isDark ? '#94a3b8' : '#6b7280';

  const d = chartDataGlobal[type];
  let label, color, data;
  if (type === 'weight') {
    label = 'Weight (kg)'; color = '#4f46e5'; data = d.data;
  } else if (type === 'workouts') {
    label = 'Duration (min)'; color = '#f59e0b'; data = d.data;
  } else {
    label = 'Calories (kcal)'; color = '#10b981'; data = d.data;
  }

  if (progressChart) progressChart.destroy();
  progressChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: d.labels,
      datasets: [{
        label: label,
        data: data,
        borderColor: color,
        backgroundColor: color + '1a',
        fill: true,
        tension: .4,
        pointRadius: 4,
        pointBackgroundColor: color,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: gridColor }, ticks: { color: textColor, maxTicksLimit: 8 } },
        y: { grid: { color: gridColor }, ticks: { color: textColor } },
      },
    },
  });
}

function renderMacroChart() {
  const ctx = document.getElementById('macroChart');
  if (!ctx) return;
  // We'd get macros from today's nutrition; use placeholder if no data
  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Protein', 'Carbs', 'Fat'],
      datasets: [{
        data: [30, 45, 25],
        backgroundColor: ['#4f46e5', '#10b981', '#f59e0b'],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12, padding: 12 } },
      },
      cutout: '65%',
    },
  });
}

// ── Chat ─────────────────────────────────────────────────────
let sessionId = 'default';

function initChat(sid) {
  sessionId = sid;
  const input = document.getElementById('chatInput');
  if (input) {
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    input.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 150) + 'px';
    });
  }
  scrollToBottom();
}

function scrollToBottom() {
  const msgs = document.getElementById('chatMessages');
  if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function sendMessage() {
  const input = document.getElementById('chatInput');
  const msg = (input.value || '').trim();
  if (!msg) return;
  input.value = '';
  input.style.height = 'auto';
  appendBubble('user', msg, new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }));
  showTyping(true);
  document.getElementById('sendBtn').disabled = true;

  fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: msg, session_id: sessionId }),
  })
  .then(function (r) { return r.json(); })
  .then(function (data) {
    showTyping(false);
    document.getElementById('sendBtn').disabled = false;
    const text = data.response || data.error || 'Sorry, something went wrong.';
    appendBubble('assistant', text, new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }));
    const welcome = document.querySelector('.chat-welcome');
    if (welcome) welcome.remove();
  })
  .catch(function (err) {
    showTyping(false);
    document.getElementById('sendBtn').disabled = false;
    appendBubble('assistant', '⚠️ Connection error. Please try again.', '--:--');
  });
}

function sendQuick(prompt) {
  const input = document.getElementById('chatInput');
  if (input) input.value = prompt;
  sendMessage();
  // close offcanvas if open
  const oc = document.getElementById('quickOffcanvas');
  if (oc) {
    const bsOc = bootstrap.Offcanvas.getInstance(oc);
    if (bsOc) bsOc.hide();
  }
}

function appendBubble(role, text, time) {
  const msgs = document.getElementById('chatMessages');
  if (!msgs) return;
  const isUser = role === 'user';
  const wrap = document.createElement('div');
  wrap.className = 'chat-bubble-wrap' + (isUser ? ' justify-content-end' : '');

  let content = '';
  if (!isUser) {
    content += '<div class="bot-avatar-sm"><i class="fas fa-robot"></i></div>';
  }

  const bubbleClass = 'chat-bubble chat-bubble-' + role;
  const innerContent = isUser ? escapeHtml(text) : '';
  content += `<div class="${bubbleClass}" data-md="${escapeAttr(text)}">
    <div class="bubble-content">${innerContent}</div>
    <div class="bubble-time">${time}</div>
  </div>`;

  if (isUser) {
    const initial = document.querySelector('.user-avatar-sm') ? document.querySelector('.user-avatar-sm').textContent : 'U';
    content += `<div class="user-avatar-sm">${initial}</div>`;
  }

  wrap.innerHTML = content;
  msgs.appendChild(wrap);

  if (!isUser) {
    const bubble = wrap.querySelector('.chat-bubble');
    if (bubble) renderBubble(bubble);
  }
  scrollToBottom();
}

function showTyping(visible) {
  const ind = document.getElementById('typingIndicator');
  if (ind) ind.classList.toggle('d-none', !visible);
  scrollToBottom();
}

function clearChat() {
  if (!confirm('Clear all chat history?')) return;
  fetch('/api/chat/clear', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  .then(function () { location.reload(); })
  .catch(function () { showToast('Failed to clear chat', 'danger'); });
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function escapeAttr(s) {
  return s.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ── Workout ───────────────────────────────────────────────────
function logWorkout() {
  const payload = {
    date:         document.getElementById('wDate').value,
    workout_type: document.getElementById('wType').value,
    duration:     document.getElementById('wDuration').value,
    calories:     document.getElementById('wCalories').value,
    notes:        document.getElementById('wNotes').value,
    completed:    document.getElementById('wCompleted').checked,
  };
  fetch('/api/workout/log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  .then(function (r) { return r.json(); })
  .then(function () {
    bootstrap.Modal.getInstance(document.getElementById('logWorkoutModal')).hide();
    showToast('<i class="fas fa-check-circle me-2"></i>Workout logged! 💪', 'success');
    setTimeout(function () { location.reload(); }, 1200);
  })
  .catch(function () { showToast('Failed to log workout', 'danger'); });
}

function generatePlan() {
  const card    = document.getElementById('aiPlanCard');
  const content = document.getElementById('aiPlanContent');
  card.classList.remove('d-none');
  content.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary"></div><p class="mt-2 text-muted">Generating your personalized plan...</p></div>';
  fetch('/api/workout/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
  .then(function (r) { return r.json(); })
  .then(function (d) {
    try { content.innerHTML = marked.parse(d.plan || 'No plan generated.'); }
    catch(e) { content.textContent = d.plan || ''; }
    card.scrollIntoView({ behavior: 'smooth' });
  })
  .catch(function () { content.textContent = 'Error generating plan. Check your API key.'; });
}

function deleteWorkout(id, btn) {
  if (!confirm('Delete this workout log?')) return;
  fetch('/api/workout/delete/' + id, { method: 'DELETE' })
  .then(function () {
    btn.closest('tr').remove();
    showToast('Workout deleted', 'info');
  });
}

// ── Nutrition ──────────────────────────────────────────────── 
function logMeal() {
  const payload = {
    meal_type: document.getElementById('mealType').value,
    food_item: document.getElementById('foodItem').value,
    calories:  document.getElementById('mCal').value,
    protein:   document.getElementById('mProt').value,
    carbs:     document.getElementById('mCarbs').value,
    fat:       document.getElementById('mFat').value,
    water_ml:  document.getElementById('mWater').value,
  };
  if (!payload.food_item) { showToast('Enter a food item', 'warning'); return; }
  fetch('/api/nutrition/log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  .then(function (r) { return r.json(); })
  .then(function () {
    bootstrap.Modal.getInstance(document.getElementById('logMealModal')).hide();
    showToast('<i class="fas fa-check-circle me-2"></i>Meal logged! 🥗', 'success');
    setTimeout(function () { location.reload(); }, 1200);
  });
}

function deleteNutrition(id, btn) {
  if (!confirm('Delete this meal entry?')) return;
  fetch('/api/nutrition/delete/' + id, { method: 'DELETE' })
  .then(function () {
    btn.closest('tr').remove();
    showToast('Meal deleted', 'info');
  });
}

function generateMealPlan() {
  const card    = document.getElementById('aiMealCard');
  const content = document.getElementById('aiMealContent');
  card.classList.remove('d-none');
  content.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-success"></div><p class="mt-2 text-muted">Generating your meal plan...</p></div>';
  fetch('/api/nutrition/meal-plan', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
  .then(function (r) { return r.json(); })
  .then(function (d) {
    try { content.innerHTML = marked.parse(d.plan || 'No plan generated.'); }
    catch(e) { content.textContent = d.plan || ''; }
    card.scrollIntoView({ behavior: 'smooth' });
  })
  .catch(function () { content.textContent = 'Error generating meal plan. Check your API key.'; });
}

function logWater(ml) {
  const payload = { meal_type: 'Water', food_item: 'Water', calories: 0, water_ml: ml };
  fetch('/api/nutrition/log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  .then(function () {
    showToast('<i class="fas fa-tint me-2"></i>+' + ml + 'ml water logged! 💧', 'info');
    setTimeout(function () { location.reload(); }, 1000);
  });
}

// ── Calculator ─────────────────────────────────────────────── 
function calcBMI() {
  const h = parseFloat(document.getElementById('bmiHeight').value);
  const w = parseFloat(document.getElementById('bmiWeight').value);
  if (!h || !w) { showToast('Enter valid height and weight', 'warning'); return; }

  fetch('/api/calculator/bmi', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ height: h, weight: w }),
  })
  .then(function (r) { return r.json(); })
  .then(function (d) {
    document.getElementById('bmiResult').classList.remove('d-none');
    document.getElementById('bmiNumber').textContent = d.bmi;

    const catEl = document.getElementById('bmiCat');
    catEl.textContent = d.category;
    const catMap = {
      'Underweight': 'bg-info text-white',
      'Normal weight': 'bg-success text-white',
      'Overweight': 'bg-warning text-dark',
      'Obese': 'bg-danger text-white',
    };
    catEl.className = 'badge fs-6 mb-3 ' + (catMap[d.category] || 'bg-secondary text-white');

    // Position marker on scale (BMI 10–40)
    const pct = Math.min(Math.max(((d.bmi - 10) / 30) * 100, 0), 100);
    document.getElementById('bmiMarker').style.left = pct + '%';

    const insights = {
      'Underweight': '⚠️ Your BMI is below the healthy range. Consider eating more nutrient-rich foods and consulting a nutritionist.',
      'Normal weight': '✅ Great! Your BMI is in the healthy range. Keep maintaining your current lifestyle.',
      'Overweight': '🎯 Your BMI is slightly above healthy. Regular exercise and a balanced diet can help bring it to normal range.',
      'Obese': '⚠️ Your BMI indicates obesity. Consult a healthcare professional for a personalized weight management plan.',
    };
    document.getElementById('bmiInsight').textContent = insights[d.category] || '';
  });
}

function calcBMR() {
  const payload = {
    weight:   document.getElementById('bmrWeight').value,
    height:   document.getElementById('bmrHeight').value,
    age:      document.getElementById('bmrAge').value,
    gender:   document.getElementById('bmrGender').value,
    activity: document.getElementById('bmrActivity').value,
  };
  fetch('/api/calculator/bmr', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  .then(function (r) { return r.json(); })
  .then(function (d) {
    document.getElementById('bmrResult').classList.remove('d-none');
    document.getElementById('bmrVal').textContent      = d.bmr.toLocaleString();
    document.getElementById('tdeeVal').textContent     = d.tdee.toLocaleString();
    document.getElementById('gainVal').textContent     = d.weight_gain.toLocaleString();
    document.getElementById('maintainVal').textContent = d.maintenance.toLocaleString();
    document.getElementById('lossVal').textContent     = d.weight_loss.toLocaleString();
  });
}

// ── Habits ─────────────────────────────────────────────────── 
function logHabit() {
  const payload = {
    habit_name: document.getElementById('habitName').value,
    value:      document.getElementById('habitValue').value,
    unit:       document.getElementById('habitUnit').value,
    completed:  document.getElementById('habitCompleted').checked,
  };
  if (!payload.habit_name) { showToast('Enter a habit name', 'warning'); return; }
  fetch('/api/habits/log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  .then(function () {
    bootstrap.Modal.getInstance(document.getElementById('addHabitModal')).hide();
    showToast('<i class="fas fa-check-circle me-2"></i>Habit logged! ✅', 'success');
    setTimeout(function () { location.reload(); }, 1200);
  });
}

function quickHabit(name, unit, target, color) {
  document.getElementById('qHabitName').value    = name;
  document.getElementById('qHabitUnit').value    = unit;
  document.getElementById('qHabitTitle').textContent = 'Log ' + name;
  document.getElementById('qHabitLabel').textContent = 'Value (' + unit + ')';
  document.getElementById('qHabitValue').value   = target;
  new bootstrap.Modal(document.getElementById('quickHabitModal')).show();
}

function saveQuickHabit() {
  const payload = {
    habit_name: document.getElementById('qHabitName').value,
    value:      document.getElementById('qHabitValue').value,
    unit:       document.getElementById('qHabitUnit').value,
    completed:  true,
  };
  fetch('/api/habits/log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  .then(function () {
    bootstrap.Modal.getInstance(document.getElementById('quickHabitModal')).hide();
    showToast('<i class="fas fa-check-circle me-2"></i>' + payload.habit_name + ' logged! ✅', 'success');
    setTimeout(function () { location.reload(); }, 1200);
  });
}

// ── Profile: weight logger ────────────────────────────────── 
function logWeight() {
  const w = parseFloat(document.getElementById('newWeight').value);
  if (!w) { showToast('Enter a valid weight', 'warning'); return; }
  fetch('/api/weight/log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ weight: w, date: new Date().toISOString().split('T')[0] }),
  })
  .then(function (r) { return r.json(); })
  .then(function (d) {
    showToast('<i class="fas fa-weight me-2"></i>Weight updated! BMI: ' + d.bmi, 'success');
    setTimeout(function () { location.reload(); }, 1200);
  });
}
