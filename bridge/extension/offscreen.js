(function () {
  var TAG = '[WebBridge:Offscreen]';
  var WS_URL = 'ws://127.0.0.1:10087';
  var ws = null;
  var reconnectTimer = null;
  var reconnectDelay = 1000;
  var maxReconnectDelay = 30000;
  var pingInterval = null;

  function log(msg) { console.log(TAG, msg); }
  function err(msg) { console.error(TAG, msg); }

  function connect() {
    if (ws) try { ws.close(); } catch (e) {}
    log('Connecting to ' + WS_URL);
    ws = new WebSocket(WS_URL);

    ws.onopen = function () {
      log('Connected');
      reconnectDelay = 1000;
      broadcast({ type: 'bridge_status', status: 'connected' });
      startPing();
    };

    ws.onmessage = function (event) {
      try {
        var msg = JSON.parse(event.data);
        if (msg.type === 'pong') return;
        if (!msg.action) return;

        if (msg.action === 'reload_extension') {
          ws.send(JSON.stringify({ id: msg.id, success: true, reloading: true }));
          setTimeout(function () { chrome.runtime.reload(); }, 100);
          return;
        }

        chrome.runtime.sendMessage({ type: 'bridge_command', msg: msg }, function (response) {
          if (chrome.runtime.lastError) {
            err('Runtime error: ' + chrome.runtime.lastError.message);
            ws.send(JSON.stringify({ id: msg.id, error: chrome.runtime.lastError.message }));
            return;
          }
          ws.send(JSON.stringify({ id: msg.id, ...response }));
        });
      } catch (e) {
        err('Parse error: ' + e.message);
      }
    };

    ws.onclose = function () {
      log('Disconnected');
      stopPing();
      broadcast({ type: 'bridge_status', status: 'disconnected' });
      scheduleReconnect();
    };

    ws.onerror = function (ev) {
      err('WebSocket error');
    };
  }

  function startPing() {
    stopPing();
    pingInterval = setInterval(function () {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 15000);
  }

  function stopPing() {
    if (pingInterval) { clearInterval(pingInterval); pingInterval = null; }
  }

  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    log('Reconnecting in ' + reconnectDelay + 'ms');
    reconnectTimer = setTimeout(function () {
      connect();
      reconnectDelay = Math.min(reconnectDelay * 2, maxReconnectDelay);
    }, reconnectDelay);
  }

  function broadcast(msg) {
    try { chrome.runtime.sendMessage(msg); } catch (e) {}
  }

  connect();
})();
