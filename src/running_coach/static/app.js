const conversation = document.querySelector('#conversation');
const welcome = document.querySelector('#welcome-block');
const form = document.querySelector('#chat-form');
const input = document.querySelector('#message-input');
const sendButton = document.querySelector('#send-button');
const languageSelect = document.querySelector('#language-select');
const tamilVoice = document.querySelector('#tamil-voice');
const settingsDialog = document.querySelector('#settings-dialog');
const trainingDialog = document.querySelector('#training-dialog');
const syncRunsButton = document.querySelector('#sync-runs-button');
const reindexMemoryButton = document.querySelector('#reindex-memory-button');
const runSelect = document.querySelector('#run-select');
let trainingRuns = [];
languageSelect.value = localStorage.getItem('coach-language') || 'en-ta';
tamilVoice.checked = localStorage.getItem('tamil-voice') !== 'false';
const sessionId = localStorage.getItem('coach-session-id') || crypto.randomUUID();
localStorage.setItem('coach-session-id', sessionId);
languageSelect.addEventListener('change', () => localStorage.setItem('coach-language', languageSelect.value));
tamilVoice.addEventListener('change', () => localStorage.setItem('tamil-voice', tamilVoice.checked));

function appendMessage(kind, content) {
  const article = document.createElement('article');
  article.className = `chat-message ${kind}`;
  if (kind === 'assistant') {
    const avatar = document.createElement('span');
    avatar.className = 'message-avatar';
    avatar.textContent = 'CE';
    article.append(avatar);
  }
  const body = document.createElement('div');
  body.className = 'message-body';
  if (kind === 'assistant') {
    const label = document.createElement('div');
    label.className = 'message-label';
    label.textContent = 'COACH EKLAVYA';
    body.append(label);
  }
  const text = document.createElement('div');
  text.textContent = content;
  body.append(text);
  article.append(body);
  conversation.append(article);
  conversation.scrollTop = conversation.scrollHeight;
  return article;
}

async function sendMessage(message) {
  if (!message.trim()) return;
  welcome?.remove();
  appendMessage('user', message.trim());
  const pending = appendMessage('assistant', 'Thinking...');
  pending.querySelector('.message-body > div:last-child').className = 'loading-dots';
  sendButton.disabled = true;
  input.disabled = true;
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: message.trim(),
        language: languageSelect.value,
        tamil_voice: tamilVoice.checked,
        session_id: sessionId,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'The coach could not respond.');
    pending.querySelector('.message-body > div:last-child').textContent = payload.response;
  } catch (error) {
    pending.querySelector('.message-body > div:last-child').textContent = error.message;
  } finally {
    sendButton.disabled = false;
    input.disabled = false;
    input.focus();
    conversation.scrollTop = conversation.scrollHeight;
  }
}

async function restoreHistory() {
  try {
    const response = await fetch(`/api/chat/${sessionId}/history`);
    const payload = await response.json();
    if (!payload.messages?.length) return;
    welcome?.remove();
    payload.messages.forEach((message) => appendMessage(message.role, message.content));
  } catch {
    // A fresh conversation remains usable if local history is unavailable.
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const message = input.value;
  input.value = '';
  input.style.height = 'auto';
  sendMessage(message);
});

input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
});

input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll('[data-prompt]').forEach((button) => {
  button.addEventListener('click', () => {
    input.value = button.dataset.prompt;
    form.requestSubmit();
  });
});

document.querySelector('#settings-button').addEventListener('click', () => settingsDialog.showModal());
document.querySelector('#manage-connections').addEventListener('click', () => settingsDialog.showModal());
document.querySelector('#training-log-button').addEventListener('click', () => {
  trainingDialog.showModal();
  loadTrainingLog();
});
document.querySelector('#strava-connect').addEventListener('click', () => toggleIntegration('strava', 'strava-status'));
document.querySelector('#sheets-connect').addEventListener('click', () => toggleIntegration('google', 'sheets-status'));

document.querySelector('#sync-runs-button').addEventListener('click', async () => {
  const status = document.querySelector('#training-sync-status');
  syncRunsButton.disabled = true;
  status.textContent = 'Syncing recent activities…';
  try {
    const response = await fetch('/api/training/sync', { method: 'POST' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Could not sync Strava runs.');
    await loadTrainingLog();
    status.textContent = payload.available
      ? `Synced ${payload.synced} activities and indexed ${payload.indexed} memories.`
      : `Synced ${payload.synced} activities. Keyword search remains available; install ${payload.model} for semantic search.`;
  } catch (error) {
    status.textContent = error.message;
  } finally {
    syncRunsButton.disabled = false;
  }
});

reindexMemoryButton.addEventListener('click', async () => {
  const status = document.querySelector('#memory-index-status');
  reindexMemoryButton.disabled = true;
  status.textContent = 'Indexing saved training memories…';
  try {
    const response = await fetch('/api/training/reindex', { method: 'POST' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Could not index local memories.');
    await loadTrainingLog();
    status.textContent = payload.available
      ? `Indexed ${payload.indexed} memories. Semantic search is ready.`
      : `Could not reach ${payload.model}. Keyword search remains available.`;
  } catch (error) {
    status.textContent = error.message;
    reindexMemoryButton.disabled = false;
  }
});

runSelect.addEventListener('change', populateReflection);

document.querySelector('#reflection-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const status = document.querySelector('#reflection-status');
  const activityId = runSelect.value;
  if (!activityId) return;
  const optionalNumber = (selector) => {
    const value = document.querySelector(selector).value;
    return value === '' ? null : Number(value);
  };
  try {
    const response = await fetch(`/api/training/runs/${encodeURIComponent(activityId)}/reflection`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        feeling: document.querySelector('#run-feeling').value,
        notes: document.querySelector('#run-notes').value,
        perceived_effort: optionalNumber('#run-effort'),
        temperature_c: optionalNumber('#run-temperature'),
        humidity_pct: optionalNumber('#run-humidity'),
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Could not save reflection.');
    status.textContent = payload.available
      ? 'Reflection saved and indexed in local training memory.'
      : 'Reflection saved locally; keyword search is available until embeddings are ready.';
    await loadTrainingLog();
  } catch (error) {
    status.textContent = error.message;
  }
});

document.querySelector('#race-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const status = document.querySelector('#race-status');
  const [hours, minutes, seconds = 0] = document.querySelector('#race-time').value.split(':').map(Number);
  try {
    const response = await fetch('/api/training/races', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: document.querySelector('#race-name').value.trim(),
        event_date: document.querySelector('#race-date').value,
        distance_km: Number(document.querySelector('#race-distance').value),
        target_time_seconds: hours * 3600 + minutes * 60 + seconds,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Could not save race target.');
    status.textContent = payload.embedding_index?.available
      ? 'Race target saved and indexed.'
      : 'Race target saved locally; keyword search is available until embeddings are ready.';
    event.currentTarget.reset();
    await loadTrainingLog();
  } catch (error) {
    status.textContent = error.message;
  }
});

function formatDuration(totalSeconds) {
  if (totalSeconds == null) return 'No estimate';
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}` : `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function populateReflection() {
  const run = trainingRuns.find((activity) => activity.id === runSelect.value);
  document.querySelector('#run-feeling').value = run?.feeling || '';
  document.querySelector('#run-effort').value = run?.perceived_effort ?? '';
  document.querySelector('#run-temperature').value = run?.temperature_c ?? '';
  document.querySelector('#run-humidity').value = run?.humidity_pct ?? '';
  document.querySelector('#run-notes').value = run?.notes || '';
}

function renderRuns() {
  const selectedId = runSelect.value;
  runSelect.replaceChildren(new Option(trainingRuns.length ? 'Choose a run' : 'Sync a run first', ''));
  const history = document.querySelector('#run-history');
  history.replaceChildren();
  trainingRuns.forEach((run) => {
    const label = `${run.start_date_local || 'Undated'} · ${run.name} · ${run.distance_km} km`;
    runSelect.add(new Option(label, run.id));
    const item = document.createElement('li');
    const title = document.createElement('strong');
    title.textContent = label;
    const details = [
      run.elevation_gain_m == null ? '' : `Ascent ${run.elevation_gain_m} m`,
      run.descent_m == null ? '' : `descent ${run.descent_m} m`,
      run.temperature_c == null ? '' : `${run.temperature_c} °C`,
      run.humidity_pct == null ? '' : `${run.humidity_pct}% RH`,
      run.feeling || '',
    ].filter(Boolean).join(' · ');
    item.append(title);
    if (details) {
      const description = document.createElement('p');
      description.textContent = details;
      item.append(description);
    }
    history.append(item);
  });
  runSelect.value = trainingRuns.some((run) => run.id === selectedId) ? selectedId : '';
  populateReflection();
    document.querySelector('#save-reflection-button').disabled = trainingRuns.length === 0;
}

function renderRaceGoals(goals) {
  const list = document.querySelector('#race-goals-list');
  list.replaceChildren();
  goals.forEach((goal) => {
    const item = document.createElement('li');
    const title = document.createElement('strong');
    title.textContent = `${goal.name} · ${goal.distance_km} km · ${goal.event_date}`;
    const assessment = goal.assessment;
    const verdict = {
      within_projection: 'Within rough projection',
      stretch_target: 'Faster than current projection',
      insufficient_data: 'Not enough recent comparable data',
      event_passed: 'Event date has passed',
    }[assessment.verdict] || assessment.verdict;
    const description = document.createElement('p');
    description.textContent = `${verdict} · target ${formatDuration(goal.target_time_seconds)} · estimate ${formatDuration(assessment.estimated_time_seconds)}${assessment.confidence ? ` · ${assessment.confidence} confidence` : ''}`;
    item.append(title, description);
    list.append(item);
  });
}

async function loadTrainingLog() {
  try {
    const [runsResponse, racesResponse, healthResponse] = await Promise.all([
      fetch('/api/training/runs'),
      fetch('/api/training/races'),
      fetch('/api/health'),
    ]);
    if (!runsResponse.ok || !racesResponse.ok || !healthResponse.ok) throw new Error('Could not load local training data.');
    const [runs, races, health] = await Promise.all([
      runsResponse.json(),
      racesResponse.json(),
      healthResponse.json(),
    ]);
    trainingRuns = runs.runs;
    renderRuns();
    renderRaceGoals(races.races);
    const status = document.querySelector('#memory-index-status');
    reindexMemoryButton.disabled = !health.embedding_model_available
      || health.memory_total === health.memory_embedded;
    if (!health.ollama) {
      status.textContent = 'Ollama is offline; local keyword search remains available.';
    } else if (!health.embedding_model_available) {
      status.textContent = `Keyword retrieval active. Run ollama pull ${health.embedding_model} to enable semantic search.`;
    } else if (health.memory_total > health.memory_embedded) {
      status.textContent = `${health.memory_embedded} of ${health.memory_total} memories indexed. Index pending records.`;
    } else {
      status.textContent = `Semantic retrieval ready · ${health.memory_embedded} local memories indexed.`;
    }
  } catch (error) {
    document.querySelector('#training-sync-status').textContent = error.message;
  }
}

async function toggleIntegration(provider, statusId) {
  const connected = document.querySelector(`#${statusId}`).dataset.connected === 'true';
  if (connected) {
    if (!window.confirm(`Disconnect ${provider === 'google' ? 'Google Sheets' : 'Strava'}?`)) return;
    await fetch(`/api/integrations/${provider}`, { method: 'DELETE' });
    refreshStatus();
    return;
  }
  window.location.href = `/api/integrations/${provider}/connect`;
}

async function refreshStatus() {
  const modelStatus = document.querySelector('#model-status');
  try {
    const response = await fetch('/api/health');
    const status = await response.json();
    const label = !status.ollama ? 'OLLAMA OFFLINE' : status.model_available ? 'MODEL READY' : 'MODEL NOT PULLED';
    modelStatus.innerHTML = `<span class="status-dot ${status.model_available ? '' : 'status-muted'}"></span><span class="model-label">${label}</span><span class="model-name">· ${status.model}</span>`;
  } catch {
    modelStatus.innerHTML = '<span class="status-dot status-muted"></span>API UNAVAILABLE';
  }
  try {
    const response = await fetch('/api/integrations/status');
    const status = await response.json();
    setServiceStatus('strava-status', status.strava, status.strava_configured);
    setServiceStatus('sheets-status', status.google_sheets, status.google_configured);
    syncRunsButton.disabled = !status.strava;
    syncRunsButton.title = status.strava ? '' : 'Connect Strava before syncing runs';
  } catch {
    setServiceStatus('strava-status', false, false);
    setServiceStatus('sheets-status', false, false);
  }
}

function setServiceStatus(id, connected, configured) {
  const row = document.querySelector(`#${id}`);
  const state = row.querySelector('.service-state');
  state.textContent = connected ? 'Connected' : configured ? 'Ready to connect' : 'Set up OAuth';
  state.style.color = connected ? 'var(--green)' : '';
  row.dataset.connected = String(connected);
  const button = document.querySelector(`#${id === 'strava-status' ? 'strava-connect' : 'sheets-connect'}`);
  button.textContent = connected ? 'Disconnect' : id === 'strava-status' ? 'Connect Strava' : 'Connect Sheets';
  button.disabled = !connected && !configured;
  button.title = configured ? '' : 'Add provider OAuth settings to .env';
}

refreshStatus();
restoreHistory();
