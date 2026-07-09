import { executeCookieTool, isStorageAction, executeStorageTool } from './cookieTools.js';

let isConnected = false;
let lastNavigatedTabId = null;

const netCapture = { active: false, requests: [], max: 500, onBefore: null, onCompleted: null };

function updateBadge(text, color) {
  try { chrome.action.setBadgeText({ text }); } catch {}
  try { chrome.action.setBadgeBackgroundColor({ color }); } catch {}
}

async function ensureOffscreenDoc() {
  try {
    const existing = await chrome.offscreen.hasDocument();
    if (existing) return;
  } catch {}
  try {
    await chrome.offscreen.createDocument({
      url: chrome.runtime.getURL('offscreen.html'),
      reasons: ['BLOBS'],
      justification: 'Maintain WebSocket connection to the opencode AI agent',
    });
  } catch (e) {
    if (!e.message.includes('already exists')) {
      console.error('[WebBridge] Failed to create offscreen doc:', e);
      setTimeout(ensureOffscreenDoc, 5000);
    }
  }
}

chrome.runtime.onInstalled?.addListener(() => ensureOffscreenDoc());
chrome.runtime.onStartup?.addListener(() => ensureOffscreenDoc());

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'bridge_status') {
    isConnected = msg.status === 'connected';
    updateBadge(isConnected ? 'ON' : 'OFF', isConnected ? '#22c55e' : '#ef4444');
    chrome.runtime.sendMessage({ type: 'connection', status: msg.status }).catch(() => {});
  } else if (msg.type === 'bridge_command') {
    executeCommand(msg.msg.action, msg.msg.args || {})
      .then(result => sendResponse(result))
      .catch(err => sendResponse({ error: err.message }));
    return true;
  } else if (msg.type === 'status') {
    sendResponse({ connected: isConnected });
  } else if (msg.type === 'command') {
    executeCommand(msg.action, msg.args || {})
      .then(result => sendResponse(result))
      .catch(err => sendResponse({ error: err.message }));
    return true;
  }
});

function getActiveTab() {
  return new Promise(resolve => {
    chrome.tabs.query({ active: true, windowType: 'normal' }, tabs => {
      if (tabs && tabs.length > 0) {
        chrome.windows.getLastFocused({}, win => {
          if (!chrome.runtime.lastError && win && win.type === 'normal') {
            const found = tabs.find(t => t.windowId === win.id);
            if (found) { resolve(found); return; }
          }
          resolve(tabs[0]);
        });
      } else {
        chrome.tabs.query({ active: true }, all => resolve(all[0] || null));
      }
    });
  });
}

async function getTargetTab() {
  if (lastNavigatedTabId) {
    try {
      const tab = await chrome.tabs.get(lastNavigatedTabId);
      if (tab) return tab;
    } catch {
      lastNavigatedTabId = null;
    }
  }
  return await getActiveTab();
}

function sendToContent(tabId, type, payload) {
  return new Promise(resolve => {
    chrome.tabs.sendMessage(tabId, { type, ...payload }, res => {
      if (chrome.runtime.lastError) {
        resolve({ error: chrome.runtime.lastError.message });
      } else {
        resolve(res || { success: true });
      }
    });
  });
}

function waitForPage(tabId) {
  return new Promise(resolve => {
    const done = () => chrome.tabs.onUpdated.removeListener(listener);
    const listener = (id, info) => {
      if (id === tabId && info.status === 'complete') { done(); setTimeout(resolve, 500); }
    };
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(() => { done(); resolve(); }, 10000);
  });
}

async function executeCommand(action, args) {
  try {
    switch (action) {

      case 'navigate': {
        const url = args.url;
        const newTab = args.newTab !== false;
        let tab;
        if (newTab) {
          tab = await chrome.tabs.create({ url, active: true });
        } else {
          tab = await getTargetTab();
          if (tab) {
            tab = await chrome.tabs.update(tab.id, { url });
          } else {
            tab = await chrome.tabs.create({ url, active: true });
          }
        }
        lastNavigatedTabId = tab.id;
        await waitForPage(tab.id);
        return { success: true, url: tab.url, tabId: tab.id };
      }

      case 'snapshot': {
        const tab = await getTargetTab();
        if (!tab) return { error: 'No active tab' };
        const result = await sendToContent(tab.id, 'dom_command', { action: 'snapshot' });
        return { ...result, url: tab.url, title: tab.title };
      }

      case 'click':
      case 'fill':
      case 'find':
      case 'text':
      case 'html':
      case 'attr':
      case 'scroll':
      case 'auto_scroll':
      case 'scroll_stop':
      case 'upload':
      case 'evaluate':
      case 'pressKey':
      case 'wa_sendText':
      case 'wa_startChat':
      case 'wa_clickResult': {
        const tab = await getTargetTab();
        if (!tab) return { error: 'No active tab' };
        return await sendToContent(tab.id, 'dom_command', { action, args });
      }

      case 'screenshot': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        const fmt = args.format === 'jpeg' ? 'jpeg' : 'png';
        const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: fmt, quality: args.quality || 80 });
        return { success: true, data: dataUrl.split(',')[1], format: fmt };
      }

      case 'url': {
        const tab = await getActiveTab();
        return { success: true, url: tab?.url || '' };
      }

      case 'title': {
        const tab = await getActiveTab();
        return { success: true, title: tab?.title || '' };
      }

      case 'find_tab': {
        const match = args.url ? String(args.url).toLowerCase() : '';
        const tabId = args.tabId ? parseInt(args.tabId) : null;
        const tabs = await chrome.tabs.query({});
        let found = null;
        if (tabId) {
          found = tabs.find(t => t.id === tabId);
        } else if (match) {
          const realTabs = tabs.filter(t => t.url && !t.url.startsWith('chrome-extension://') && !t.url.startsWith('chrome://') && !t.url.startsWith('about:'));
          found = realTabs.find(t => t.url.toLowerCase() === match);
          if (!found && match.startsWith('http')) {
            let domain;
            try { domain = new URL(match).hostname; } catch { domain = match; }
            found = realTabs.find(t => t.url.toLowerCase().includes(domain));
          }
        }
        if (found) {
          await chrome.tabs.update(found.id, { active: true });
          await chrome.windows.update(found.windowId, { focused: true });
          lastNavigatedTabId = found.id;
          return { success: true, found: true, tabId: found.id, url: found.url, title: found.title };
        }
        if (match && !tabId) {
          const tab = await chrome.tabs.create({ url: match, active: true });
          lastNavigatedTabId = tab.id;
          await waitForPage(tab.id);
          return { success: true, found: false, tabId: tab.id, url: tab.url };
        }
        return { success: false, error: 'Tab not found' };
      }

      case 'list_tabs': {
        const tabs = await chrome.tabs.query({});
        return {
          success: true,
          tabs: tabs.map(t => ({ id: t.id, index: t.index, windowId: t.windowId, active: t.active, title: t.title, url: t.url, pinned: t.pinned })),
          count: tabs.length,
        };
      }

      case 'close_tab': {
        let tabId = args.tabId;
        if (!tabId) {
          const tab = await getActiveTab();
          if (!tab) return { error: 'No tab to close' };
          tabId = tab.id;
        }
        await chrome.tabs.remove(tabId);
        return { success: true, tabId };
      }

      case 'close_session': {
        const tabs = await chrome.tabs.query({});
        const ids = tabs.map(t => t.id);
        if (ids.length > 0) await chrome.tabs.remove(ids);
        return { success: true, closed: ids.length };
      }

      case 'network_start': {
        if (netCapture.active) return { success: true, alreadyActive: true };
        netCapture.requests = [];
        netCapture.active = true;

        netCapture.onBefore = details => {
          if (netCapture.requests.length >= netCapture.max) netCapture.requests.shift();
          netCapture.requests.push({
            id: details.requestId, url: details.url, method: details.method, type: details.type,
            timestamp: details.timeStamp, initiator: details.initiator || '',
            requestHeaders: details.requestHeaders, statusCode: 0, statusLine: '',
            responseHeaders: null, time: 0,
          });
        };

        netCapture.onCompleted = details => {
          const entry = netCapture.requests.find(r => r.id === details.requestId);
          if (entry) {
            entry.statusCode = details.statusCode; entry.statusLine = details.statusLine;
            entry.responseHeaders = details.responseHeaders; entry.time = details.timeStamp - entry.timestamp;
            entry.fromCache = details.fromCache;
          }
        };

        try {
          chrome.webRequest.onBeforeRequest.addListener(netCapture.onBefore, { urls: ['<all_urls>'] });
          chrome.webRequest.onCompleted.addListener(netCapture.onCompleted, { urls: ['<all_urls>'] });
        } catch (e) {
          return { error: 'Failed to start network capture: ' + e.message };
        }
        return { success: true, active: true };
      }

      case 'network_stop': {
        if (!netCapture.active) return { success: true, wasActive: false };
        if (netCapture.onBefore) chrome.webRequest.onBeforeRequest.removeListener(netCapture.onBefore);
        if (netCapture.onCompleted) chrome.webRequest.onCompleted.removeListener(netCapture.onCompleted);
        netCapture.active = false;
        return { success: true, captured: netCapture.requests.length };
      }

      case 'network_list': {
        return {
          success: true,
          requests: netCapture.requests.map(r => ({ id: r.id, url: r.url, method: r.method, type: r.type, statusCode: r.statusCode, time: Math.round(r.time), fromCache: r.fromCache })),
          count: netCapture.requests.length, active: netCapture.active,
        };
      }

      case 'network_detail': {
        const reqId = args.requestId || args.id;
        if (!reqId) return { error: 'requestId required' };
        const entry = netCapture.requests.find(r => r.id === reqId);
        if (!entry) return { error: 'Request not found' };
        return { success: true, request: entry };
      }

      case 'highlight':
      case 'clear_highlight': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        return await sendToContent(tab.id, 'dom_command', { action, args });
      }

      case 'reload_extension':
        chrome.runtime.reload();
        return { success: true };

      case 'cookies_getAll':
      case 'cookies_get':
      case 'cookies_set':
      case 'cookies_delete':
      case 'cookies_clear': {
        const result = await executeCookieTool(action, args, getActiveTab);
        if (result !== null) return result;
        return { error: 'Cookie tool failed' };
      }

      default:
        if (isStorageAction(action)) {
          const tab = await getActiveTab();
          if (!tab) return { error: 'No active tab for storage access' };
          return await executeStorageTool(action, args, tab.id);
        }
        return { error: 'Unknown action: ' + action };
    }
  } catch (e) {
    return { error: e.message };
  }
}
