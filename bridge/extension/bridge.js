(function() {
  let ws = null;
  const WS_URL = 'ws://127.0.0.1:10087';
  let reconnectTimer = null;

  function connect() {
    if (ws) {
      try { ws.close(); } catch(e) {}
    }
    
    console.log('Connecting to WebBridge server at', WS_URL);
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log('WebSocket connected');
      chrome.runtime.sendMessage({ type: 'bridge_status', status: 'connected' });
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        console.log('Received command:', msg);

        // Drop server keep-alive / control messages that have no action to execute
        if (msg.type === 'pong' || !msg.action) {
          return;
        }

        chrome.runtime.sendMessage({ type: 'bridge_command', msg: msg }, (response) => {
          const err = chrome.runtime.lastError;
          if (err) {
            console.error('Runtime message error:', err);
            ws.send(JSON.stringify({ id: msg.id, error: err.message }));
            return;
          }
          console.log('Command response:', response);
          ws.send(JSON.stringify({ id: msg.id, ...response }));
        });
      } catch (e) {
        console.error('Failed to handle WebSocket message:', e);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      chrome.runtime.sendMessage({ type: 'bridge_status', status: 'disconnected' });
      scheduleReconnect();
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => {
      connect();
    }, 2000);
  }

  connect();
})();
