const logEl = document.getElementById('log');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const urlBar = document.getElementById('urlBar');

const hasChrome = typeof chrome !== 'undefined' && chrome.runtime;

function log(msg, type = 'info') {
  const time = new Date().toLocaleTimeString();
  const line = document.createElement('div');
  line.innerHTML = `<span class="time">[${time}]</span> <span class="${type}">${msg}</span>`;
  logEl.appendChild(line);
  logEl.scrollTop = logEl.scrollHeight;
}

function sendCmd(action, args = {}) {
  if (!hasChrome) {
    log(`Cannot run ${action}: Extension API not available (not running as popup)`, 'err');
    return;
  }
  chrome.runtime.sendMessage({ type: 'command', action, args }, (res) => {
    if (chrome.runtime.lastError) {
      log(`Error: ${chrome.runtime.lastError.message}`, 'err');
      return;
    }
    if (res && res.success) {
      log(`${action} OK`, 'ok');
      if (action === 'snapshot') log(`Page: ${res.title || res.url || ''}`, 'info');
    } else {
      log(`${action} failed: ${res?.error || 'unknown'}`, 'err');
    }
  });
}

function clearLog() {
  logEl.innerHTML = '';
}

// Add event listeners for controls
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btnSnapshot').addEventListener('click', () => sendCmd('snapshot'));
  document.getElementById('btnSS').addEventListener('click', () => sendCmd('screenshot'));
  document.getElementById('btnURL').addEventListener('click', () => sendCmd('url'));
  document.getElementById('btnClear').addEventListener('click', clearLog);
});

if (hasChrome) {
  // Background status
  chrome.runtime.sendMessage({ type: 'status' }, (res) => {
    if (res?.connected) {
      statusDot.classList.add('connected');
      statusText.textContent = 'Connected';
    }
  });

  // Listen for background broadcasts
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === 'connection') {
      if (msg.status === 'connected') {
        statusDot.classList.add('connected');
        statusText.textContent = 'Connected';
        log('Bridge connected', 'ok');
      } else {
        statusDot.classList.remove('connected');
        statusText.textContent = 'Disconnected';
        log('Bridge disconnected', 'err');
      }
    }
  });

  // Get active tab URL
  if (chrome.tabs && chrome.tabs.query) {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.url) {
        const url = tabs[0].url;
        urlBar.textContent = url.length > 50 ? url.slice(0, 50) + '...' : url;
        urlBar.title = url;
      }
    });
  }
} else {
  log('Extension context not loaded (running as standalone webpage)', 'info');
}
