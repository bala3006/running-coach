const conversation = document.querySelector('#conversation');
const welcome = document.querySelector('#welcome-block');
const form = document.querySelector('#chat-form');
const input = document.querySelector('#message-input');
const sendButton = document.querySelector('#send-button');
const languageSelect = document.querySelector('#language-select');
const tamilVoice = document.querySelector('#tamil-voice');
const settingsDialog = document.querySelector('#settings-dialog');
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
document.querySelector('#strava-connect').addEventListener('click', () => toggleIntegration('strava', 'strava-status'));
document.querySelector('#sheets-connect').addEventListener('click', () => toggleIntegration('google', 'sheets-status'));

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
