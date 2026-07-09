(() => {
  const tag = document.currentScript?.getAttribute('data-tag') || 'wb';
  window[tag] = window.__webBridge || null;
})();
