let isConnected = false;
let netCapture = { active: false, requests: [], max: 500, onBefore: null, onCompleted: null };

function updateBadge(text, color) {
  try { chrome.action.setBadgeText({ text }); } catch (e) { console.debug('Badge text error:', e); }
  try { chrome.action.setBadgeBackgroundColor({ color }); } catch (e) { console.debug('Badge color error:', e); }
}

// Open bridge page as a small popup to maintain persistent WebSocket
let bridgeWindowId = null;
function openBridge() {
  if (bridgeWindowId) {
    chrome.windows.get(bridgeWindowId, (win) => {
      if (chrome.runtime.lastError) bridgeWindowId = null;
    });
  }
  chrome.windows.create({
    url: chrome.runtime.getURL('bridge.html'),
    type: 'popup',
    width: 1, height: 1, left: -1000, top: -1000,
    focused: false,
  }, (win) => {
    if (win && !chrome.runtime.lastError) {
      bridgeWindowId = win.id;
    } else {
      console.debug('Failed to create bridge window:', chrome.runtime.lastError?.message);
      // Retry once after a delay
      setTimeout(() => {
        chrome.windows.create({
          url: chrome.runtime.getURL('bridge.html'),
          type: 'popup',
          width: 1, height: 1, left: -1000, top: -1000,
          focused: false,
        }, (retryWin) => {
          if (retryWin) bridgeWindowId = retryWin.id;
        });
      }, 5000);
    }
  });
}

// Listen for messages from bridge page and popup
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'bridge_status') {
    isConnected = msg.status === 'connected';
    updateBadge(isConnected ? 'ON' : 'OFF', isConnected ? '#22c55e' : '#ef4444');
    
    // Broadcast status change to popup if open
    chrome.runtime.sendMessage({ type: 'connection', status: msg.status }).catch(() => {});
  }
  if (msg.type === 'bridge_command') {
    executeCommand(msg.msg.action, msg.msg.args || {})
      .then((result) => sendResponse(result))
      .catch((e) => sendResponse({ error: e.message }));
    return true; // keep channel open for async response
  }
  if (msg.type === 'status') {
    sendResponse({ connected: isConnected });
  }
  if (msg.type === 'command') {
    executeCommand(msg.action, msg.args || {})
      .then((result) => sendResponse(result))
      .catch((e) => sendResponse({ error: e.message }));
    return true; // keep channel open for async response
  }
});

// Open bridge on install and startup
chrome.runtime.onInstalled?.addListener(() => { openBridge(); });
chrome.runtime.onStartup?.addListener(() => { openBridge(); });

// Keep alive: open bridge if not open (checked via alarms)
chrome.alarms.create('bridge_keepalive', { periodInMinutes: 0.25 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'bridge_keepalive') {
    if (!bridgeWindowId) openBridge();
  }
});

function getActiveTab() {
  return new Promise((resolve) => {
    // Query for the active tab in a normal window
    chrome.tabs.query({ active: true, windowType: 'normal' }, (tabs) => {
      if (tabs && tabs.length > 0) {
        // If there are multiple normal windows, prioritize the one in the last focused window
        chrome.windows.getLastFocused({}, (win) => {
          if (!chrome.runtime.lastError && win && win.type === 'normal') {
            const activeInFocused = tabs.find(t => t.windowId === win.id);
            if (activeInFocused) {
              resolve(activeInFocused);
              return;
            }
          }
          resolve(tabs[0]);
        });
      } else {
        // Fallback to any active tab if no normal window is found
        chrome.tabs.query({ active: true }, (allTabs) => {
          resolve(allTabs[0] || null);
        });
      }
    });
  });
}

async function executeCommand(action, args) {
  try {
    switch (action) {
      // --- Existing ---
      case 'navigate': {
        const url = args.url;
        const newTab = args.newTab !== false;
        let tab;
        if (newTab) {
          tab = await chrome.tabs.create({ url, active: true });
        } else {
          tab = (await getActiveTab()) || await chrome.tabs.create({ url });
          await chrome.tabs.update(tab.id, { url });
        }
        await waitForPage(tab.id);
        return { success: true, url: tab.url, tabId: tab.id };
      }

      case 'snapshot': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        const result = await sendToContent(tab.id, 'dom_command', { action: 'snapshot' });
        return { ...result, url: tab.url, title: tab.title };
      }

      case 'click': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        return await sendToContent(tab.id, 'dom_command', { action: 'click', args });
      }

      case 'fill': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        return await sendToContent(tab.id, 'dom_command', { action: 'fill', args });
      }

      case 'find': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        return await sendToContent(tab.id, 'dom_command', { action: 'find', args });
      }

      case 'text': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        return await sendToContent(tab.id, 'dom_command', { action: 'text', args });
      }

      case 'html': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        return await sendToContent(tab.id, 'dom_command', { action: 'html', args });
      }

      case 'attr': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        return await sendToContent(tab.id, 'dom_command', { action: 'attr', args });
      }

      case 'auto_scroll': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        return await sendToContent(tab.id, 'dom_command', { action: 'auto_scroll', args });
      }

      case 'scroll': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        return await sendToContent(tab.id, 'dom_command', { action: 'scroll', args });
      }

      case 'evaluate': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        return await sendToContent(tab.id, 'dom_command', { action: 'evaluate', args });
      }

      case 'screenshot': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        const fmt = args.format === 'jpeg' ? 'jpeg' : 'png';
        const quality = args.quality || 80;
        const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: fmt, quality });
        const base64 = dataUrl.split(',')[1];
        return { success: true, data: base64, format: fmt };
      }

      case 'url': {
        const tab = await getActiveTab();
        return { success: true, url: tab?.url || '' };
      }

      case 'title': {
        const tab = await getActiveTab();
        return { success: true, title: tab?.title || '' };
      }

      // --- New: find_tab ---
      case 'find_tab': {
        const match = (args.url || '').toLowerCase();
        const tabs = await chrome.tabs.query({});
        // Try exact URL match first
        let found = tabs.find(t => t.url && t.url.toLowerCase() === match);
        if (!found && match) {
          // Try domain match
          let domain;
          try { domain = new URL(match).hostname; } catch { domain = match; }
          found = tabs.find(t => t.url && t.url.toLowerCase().includes(domain));
        }
        if (found) {
          await chrome.tabs.update(found.id, { active: true });
          await chrome.windows.update(found.windowId, { focused: true });
          return { success: true, found: true, tabId: found.id, url: found.url, title: found.title };
        }
        // Not found — navigate in new tab
        if (match) {
          const tab = await chrome.tabs.create({ url: match, active: true });
          await waitForPage(tab.id);
          return { success: true, found: false, tabId: tab.id, url: tab.url };
        }
        return { success: true, found: false };
      }

      // --- New: list_tabs ---
      case 'list_tabs': {
        const tabs = await chrome.tabs.query({});
        const list = tabs.map(t => ({
          id: t.id,
          index: t.index,
          windowId: t.windowId,
          active: t.active,
          title: t.title,
          url: t.url,
          pinned: t.pinned,
        }));
        return { success: true, tabs: list, count: list.length };
      }

      // --- New: close_tab ---
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

      // --- New: close_session ---
      case 'close_session': {
        const tabs = await chrome.tabs.query({});
        const ids = tabs.map(t => t.id);
        if (ids.length > 0) {
          await chrome.tabs.remove(ids);
        }
        return { success: true, closed: ids.length };
      }

      // --- New: network_start ---
      case 'network_start': {
        if (netCapture.active) return { success: true, alreadyActive: true };
        netCapture.requests = [];
        netCapture.active = true;

        netCapture.onBefore = (details) => {
          if (netCapture.requests.length >= netCapture.max) {
            netCapture.requests.shift();
          }
          netCapture.requests.push({
            id: details.requestId,
            url: details.url,
            method: details.method,
            type: details.type,
            timestamp: details.timeStamp,
            initiator: details.initiator || '',
            requestHeaders: details.requestHeaders,
            statusCode: 0,
            statusLine: '',
            responseHeaders: null,
            time: 0,
          });
        };

        netCapture.onCompleted = (details) => {
          const entry = netCapture.requests.find(r => r.id === details.requestId);
          if (entry) {
            entry.statusCode = details.statusCode;
            entry.statusLine = details.statusLine;
            entry.responseHeaders = details.responseHeaders;
            entry.time = details.timeStamp - entry.timestamp;
            entry.fromCache = details.fromCache;
          }
        };

        try {
          chrome.webRequest.onBeforeRequest.addListener(
            netCapture.onBefore,
            { urls: ['<all_urls>'] },
          );
          chrome.webRequest.onCompleted.addListener(
            netCapture.onCompleted,
            { urls: ['<all_urls>'] },
          );
        } catch (e) {
          return { error: `Failed to start network capture: ${e.message}` };
        }

        return { success: true, active: true };
      }

      // --- New: network_stop ---
      case 'network_stop': {
        if (!netCapture.active) return { success: true, wasActive: false };
        if (netCapture.onBefore) {
          chrome.webRequest.onBeforeRequest.removeListener(netCapture.onBefore);
        }
        if (netCapture.onCompleted) {
          chrome.webRequest.onCompleted.removeListener(netCapture.onCompleted);
        }
        netCapture.active = false;
        return { success: true, captured: netCapture.requests.length };
      }

      // --- New: network_list ---
      case 'network_list': {
        const list = netCapture.requests.map(r => ({
          id: r.id,
          url: r.url,
          method: r.method,
          type: r.type,
          statusCode: r.statusCode,
          time: Math.round(r.time),
          fromCache: r.fromCache,
        }));
        return { success: true, requests: list, count: list.length, active: netCapture.active };
      }

      // --- New: network_detail ---
      case 'network_detail': {
        const reqId = args.requestId || args.id;
        if (!reqId) return { error: 'requestId required' };
        const entry = netCapture.requests.find(r => r.id === reqId);
        if (!entry) return { error: 'Request not found' };
        return { success: true, request: entry };
      }

      // --- scroll_stop ---
      case 'scroll_stop': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        return await sendToContent(tab.id, 'dom_command', { action: 'scroll_stop', args: {} });
      }

      // --- New: upload ---
      case 'upload': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        return await sendToContent(tab.id, 'dom_command', { action: 'upload', args });
      }

      // --- New: save_as_pdf ---
      case 'save_as_pdf': {
        const tab = await getActiveTab();
        if (!tab) return { error: 'No active tab' };
        const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: 'png' });
        const base64 = dataUrl.split(',')[1];
        return { success: true, data: base64, format: 'png', note: 'Screenshot-based PDF (full PDF API not available in MV3)' };
      }

      default:
        return { error: `Unknown action: ${action}` };
    }
  } catch (e) {
    return { error: e.message };
  }
}

function sendToContent(tabId, type, payload) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, { type, ...payload }, (res) => {
      if (chrome.runtime.lastError) {
        resolve({ error: chrome.runtime.lastError.message });
      } else {
        resolve(res || { success: true });
      }
    });
  });
}

function waitForPage(tabId) {
  return new Promise((resolve) => {
    function listener(id, info) {
      if (id === tabId && info.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        setTimeout(resolve, 500);
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(resolve, 10000);
  });
}
