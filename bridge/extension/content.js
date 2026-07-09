(function () {
  'use strict';

  const TAG = '[WebBridge]';

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'dom_command') {
      executeDOMCommand(msg.action, msg.args)
        .then(result => sendResponse({ success: true, ...result }))
        .catch(err => sendResponse({ success: false, error: err.message }));
      return true;
    }
  });

  const domApi = {
    snapshot: () => getAccessibilitySnapshot(),
    find: findElements,
    click: clickElement,
    fill: fillElement,
    scrollTo: scrollToElement,
    getHtml: getHtml,
    extractText: extractText,
    extractAttr: extractAttribute,
  };
  window.__webBridge = domApi;

  async function executeDOMCommand(action, args) {
    switch (action) {
      case 'snapshot':
        return { tree: getAccessibilitySnapshot() };
      case 'find':
        return { elements: findElements(args.selector) };
      case 'click':
        return clickElement(args.selector);
      case 'fill':
        return fillElement(args.selector, args.value);
      case 'scroll':
        return scrollToElement(args.selector, args.x, args.y);
      case 'auto_scroll':
        return await autoScroll(args.duration || 5, args.step || 300, args.interval || 0.1);
      case 'html':
        return { html: getHtml(args.selector) };
      case 'text':
        return { texts: extractText(args.selector) };
      case 'attr':
        return { values: extractAttribute(args.selector, args.attr) };
      case 'scroll_stop':
        return stopScroll();
      case 'upload':
        return await uploadFile(args.selector, args.filePath, args.fileData, args.fileName);
      case 'evaluate':
        return { result: await evaluateInPage(args.code) };
      case 'pressKey':
        return pressKey(args.key);
      case 'highlight':
        return highlightElements(args);
      case 'clear_highlight':
        return { cleared: clearHighlights() };
      case 'wa_sendText':
        return await waSendText(args.text);
      case 'wa_startChat':
        return waStartChat(args.phone);
      case 'wa_clickResult':
        return waClickSearchResult();
      default:
        throw new Error('Unknown DOM action: ' + action);
    }
  }

  function isVisible(node) {
    if (!node || node.nodeType !== Node.ELEMENT_NODE) return false;
    const style = window.getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function isInteractive(node) {
    const tag = node.tagName.toLowerCase();
    const role = node.getAttribute('role') || '';
    return ['a', 'button', 'input', 'select', 'textarea', 'details', 'summary'].includes(tag) ||
      node.hasAttribute('onclick') ||
      /button|link|checkbox|radio|tab|menuitem|option|switch|searchbox|textbox/.test(role);
  }

  function getAccessibilitySnapshot(maxDepth = 12) {
    function buildTree(node, depth) {
      if (depth > maxDepth) return null;
      if (node.nodeType === Node.TEXT_NODE) {
        const text = node.textContent.trim();
        return text ? { type: 'text', text: text.slice(0, 200) } : null;
      }
      if (node.nodeType !== Node.ELEMENT_NODE) return null;

      const tag = node.tagName.toLowerCase();
      const visible = isVisible(node);
      const interactive = isInteractive(node);
      let ref;
      if (interactive) {
        ref = node.getAttribute('data-wb-ref');
        if (!ref) {
          ref = '@e_' + Math.random().toString(36).slice(2, 8);
          node.setAttribute('data-wb-ref', ref);
        }
      }

      const rect = node.getBoundingClientRect();
      const children = [];
      for (const child of node.childNodes) {
        const c = buildTree(child, depth + 1);
        if (c) children.push(c);
      }

      const entry = {
        tag,
        role: node.getAttribute('role') || undefined,
        name: node.getAttribute('aria-label') || node.title || undefined,
        text: node.innerText?.slice(0, 100) || undefined,
        visible,
        rect: visible ? { x: ~~rect.x, y: ~~rect.y, w: ~~rect.width, h: ~~rect.height } : undefined,
        interactive: interactive || undefined,
        ref,
      };
      if (children.length) entry.children = children;
      return entry;
    }
    return buildTree(document.body, 0) || { tag: 'body', children: [] };
  }

  function resolveElement(selector) {
    if (!selector) return null;
    if (selector.startsWith('@e_')) {
      return document.querySelector(`[data-wb-ref="${CSS.escape(selector)}"]`);
    }
    try {
      return document.querySelector(selector);
    } catch {
      return null;
    }
  }

  function resolveElements(selector) {
    try {
      return [...document.querySelectorAll(selector)];
    } catch {
      return [];
    }
  }

  function findElements(selector) {
    try {
      const nodes = document.querySelectorAll(selector);
      return Array.from(nodes).slice(0, 20).map(el => ({
        tag: el.tagName.toLowerCase(),
        id: el.id || undefined,
        classes: el.className?.slice(0, 100) || undefined,
        text: (el.innerText || '').slice(0, 200),
        visible: isVisible(el),
        rect: el.getBoundingClientRect(),
        attrs: collectAttrs(el),
      }));
    } catch {
      const nodes = [...document.querySelectorAll('*')].filter(el =>
        el.children.length === 0 && el.innerText?.includes(selector)
      );
      return nodes.slice(0, 10).map(el => ({
        tag: el.tagName.toLowerCase(),
        text: el.innerText?.slice(0, 200),
        visible: isVisible(el),
      }));
    }
  }

  function clickElement(selector) {
    const el = resolveElement(selector);
    if (!el) throw new Error('Element not found: ' + selector);
    const tag = el.tagName.toLowerCase();
    const text = (el.innerText || '').slice(0, 100);

    el.focus();
    el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, view: window }));
    el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
    el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, view: window }));
    el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
    try { el.click(); } catch { el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); }
    return { success: true, tag, text };
  }

  function fillElement(selector, value) {
    const el = resolveElement(selector);
    if (!el) throw new Error('Element not found: ' + selector);

    if (el.isContentEditable) {
      el.focus();
      el.innerHTML = '';
      document.execCommand('insertText', false, value);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return { success: true, mode: 'contenteditable' };
    }

    el.focus();
    el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
    return { success: true, mode: 'value' };
  }

  function getHtml(selector) {
    if (!selector) return document.documentElement.outerHTML;
    const el = resolveElement(selector);
    return el ? el.outerHTML : null;
  }

  function extractText(selector) {
    return resolveElements(selector).map(el => el.innerText.trim());
  }

  function extractAttribute(selector, attr) {
    return resolveElements(selector).map(el => el.getAttribute(attr));
  }

  function collectAttrs(el) {
    const m = {};
    for (const a of el.attributes) {
      if (a.name.startsWith('data-') || ['href', 'src', 'alt', 'title', 'placeholder', 'type', 'name', 'value', 'role', 'aria-label'].includes(a.name)) {
        m[a.name] = a.value;
      }
    }
    return m;
  }

  function getScrollableContainer() {
    const prioritySelectors = [
      '[role="main"]', 'main', '#react-root', '#root', '#app', '.app',
      '[role="tabpanel"]', '[data-pagelet="root"]',
    ];
    for (const sel of prioritySelectors) {
      const el = document.querySelector(sel);
      if (el) {
        const style = window.getComputedStyle(el);
        if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
          if (el.scrollHeight - el.clientHeight > 100) return el;
        }
        for (const child of el.querySelectorAll('*')) {
          const cs = window.getComputedStyle(child);
          if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && child.scrollHeight - child.clientHeight > 100) return child;
        }
      }
    }

    const docEl = document.documentElement;
    const body = document.body;
    let best = window;
    let maxRange = 0;

    if (window.getComputedStyle(docEl).overflowY !== 'hidden' && body ? window.getComputedStyle(body).overflowY !== 'hidden' : true) {
      const docHeight = Math.max(docEl.scrollHeight, body ? body.scrollHeight : 0);
      maxRange = Math.max(0, docHeight - window.innerHeight);
    }

    for (const el of document.querySelectorAll('*')) {
      if (el === docEl || el === body) continue;
      const style = window.getComputedStyle(el);
      if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
        const range = el.scrollHeight - el.clientHeight;
        if (range > 10 && range > maxRange) {
          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) { maxRange = range; best = el; }
        }
      }
    }
    return best;
  }

  async function scrollToElement(selector, x, y) {
    const container = getScrollableContainer();
    const isWin = container === window;

    if (x != null || y != null) {
      const dx = x || 0;
      const dy = y || 0;
      if (selector) {
        const el = resolveElement(selector);
        if (el) {
          const before = el.scrollTop;
          el.scrollBy({ top: dy, left: dx, behavior: 'auto' });
          return { success: true, mode: 'element-offset', tag: el.tagName.toLowerCase(), top: el.scrollTop, left: el.scrollLeft, moved: el.scrollTop - before };
        }
      }
      const before = getScrollY(container, isWin);
      container.scrollBy({ top: dy, left: dx, behavior: 'auto' });
      return { success: true, mode: 'offset', top: getScrollY(container, isWin), moved: getScrollY(container, isWin) - before };
    }

    if (!selector) {
      const before = getScrollY(container, isWin);
      container.scrollBy({ top: 500, left: 0, behavior: 'auto' });
      return { success: true, mode: 'page', top: getScrollY(container, isWin), moved: getScrollY(container, isWin) - before };
    }

    const el = resolveElement(selector);
    if (!el) {
      const before = getScrollY(container, isWin);
      container.scrollBy({ top: 500, left: 0, behavior: 'auto' });
      return { success: true, mode: 'page-fallback', top: getScrollY(container, isWin), moved: getScrollY(container, isWin) - before };
    }

    el.scrollIntoView({ behavior: 'auto', block: 'center' });
    return { success: true, mode: 'element', tag: el.tagName.toLowerCase() };
  }

  function getScrollY(container, isWin) {
    return isWin ? window.scrollY : container.scrollTop;
  }

  async function uploadFile(selector, filePath, fileData, fileName) {
    const el = resolveElement(selector);
    if (!el) throw new Error('Element not found: ' + selector);
    if (el.tagName !== 'INPUT' || el.type !== 'file') throw new Error('Element is not a file input');

    if (fileData) {
      const byteStr = atob(fileData);
      const ab = new ArrayBuffer(byteStr.length);
      const ia = new Uint8Array(ab);
      for (let i = 0; i < byteStr.length; i++) ia[i] = byteStr.charCodeAt(i);
      const blob = new Blob([ab]);
      const file = new File([blob], fileName || 'upload.bin');
      const dt = new DataTransfer();
      dt.items.add(file);
      Object.defineProperty(el, 'files', { value: dt.files, writable: false });
    } else {
      throw new Error('filePath not supported; use fileData (base64) instead');
    }

    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return { success: true, fileName: fileName || 'upload.bin' };
  }

  let scrollIntervalId = null;

  async function autoScroll(durationSec, stepPx, intervalSec) {
    const container = getScrollableContainer();
    const isWin = container === window;
    const steps = Math.floor(durationSec / intervalSec);
    const ms = intervalSec * 1000;

    return new Promise(resolve => {
      let total = 0;
      let i = 0;
      let zeroCount = 0;
      scrollIntervalId = setInterval(() => {
        const cy = isWin ? window.scrollY : container.scrollTop;
        const th = isWin ? Math.max(document.documentElement.scrollHeight, document.body.scrollHeight) : container.scrollHeight;
        const vh = isWin ? window.innerHeight : container.clientHeight;

        if (i >= steps) {
          clearInterval(scrollIntervalId); scrollIntervalId = null;
          resolve({ scrolled: total, reachedEnd: vh + cy >= th - 10 });
          return;
        }

        const before = cy;
        container.scrollBy({ top: stepPx, left: 0, behavior: 'auto' });
        const after = isWin ? window.scrollY : container.scrollTop;
        const actual = after - before;
        total += actual;
        i++;

        if (actual === 0) {
          zeroCount++;
          if (zeroCount >= 5) {
            clearInterval(scrollIntervalId); scrollIntervalId = null;
            resolve({ scrolled: total, reachedEnd: (stepPx > 0 && vh + cy >= th - 10) || th <= vh });
            return;
          }
        } else {
          zeroCount = 0;
        }
      }, ms);
    });
  }

  function pressKey(key) {
    const el = getWaChatInput() || getWaSearchBar();
    if (!el) return { success: false, error: "No WhatsApp input found" };
    el.focus();
    const ev = new KeyboardEvent('keydown', { key, code: key === 'Enter' ? 'Enter' : key, bubbles: true, cancelable: true });
    el.dispatchEvent(ev);
    return { success: true, key };
  }

  function stopScroll() {
    if (scrollIntervalId) { clearInterval(scrollIntervalId); scrollIntervalId = null; }
    return { success: true, stopped: true };
  }

  function getWaChatInput() {
    let inputs = document.querySelectorAll('div[contenteditable="true"]');
    for (const el of inputs) {
      const rect = el.getBoundingClientRect();
      if (rect.width > 400 && rect.height > 0) return el;
    }
    if (inputs.length > 0) return inputs[0];

    inputs = document.querySelectorAll('input[type="text"][role="textbox"]');
    const searchBar = document.querySelector('input[aria-label*="search" i]');
    for (const el of inputs) {
      if (el === searchBar) continue;
      const rect = el.getBoundingClientRect();
      if (rect.width > 400 && rect.height > 0) return el;
    }
    return null;
  }

  function getWaSearchBar() {
    let inputs = document.querySelectorAll('div[contenteditable="true"]');
    for (const el of inputs) {
      const rect = el.getBoundingClientRect();
      if (rect.width > 50 && rect.width < 400 && rect.height > 0) return el;
    }
    const el = document.querySelector('input[aria-label*="Search" i], input[role="textbox"][placeholder*="search" i]');
    if (el) return el;
    return null;
  }

  async function waSendText(text) {
    const el = getWaChatInput();
    if (!el) return { success: false, error: 'No WhatsApp chat input found' };
    el.focus();
    if (el.isContentEditable) {
      const p = el.querySelector('p') || el;
      const sel = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(p);
      range.collapse(false);
      sel.removeAllRanges();
      sel.addRange(range);
      document.execCommand('insertText', false, text);
    } else {
      el.value = text;
      el.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
    await new Promise(r => setTimeout(r, 500));
    const btn = document.querySelector('button[aria-label="Send"]') || document.querySelector('span[data-icon="send"]')?.closest('button');
    if (btn && !btn.disabled) {
      btn.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, view: window }));
      btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
      btn.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, view: window }));
      btn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
      try { btn.click(); } catch { btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); }
      return { success: true, mode: 'click' };
    }
    el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true, cancelable: true }));
    return { success: true, mode: 'enter' };
  }

  function waStartChat(phone) {
    const searchBar = getWaSearchBar();
    if (!searchBar) return { success: false, error: 'No search bar found' };
    searchBar.focus();
    if (searchBar.isContentEditable) {
      searchBar.innerHTML = '';
      document.execCommand('insertText', false, phone);
      searchBar.dispatchEvent(new Event('input', { bubbles: true }));
    } else {
      searchBar.value = phone;
      searchBar.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
      searchBar.dispatchEvent(new Event('change', { bubbles: true }));
    }
    return { success: true };
  }

  function waClickSearchResult() {
    let target = document.querySelector('div[aria-selected] div[role="gridcell"]');
    if (target) {
      target.focus();
      target.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, view: window }));
      target.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
      target.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, view: window }));
      target.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
      try { target.click(); } catch { target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); }
      return { success: true };
    }
    const items = document.querySelectorAll('[data-testid*="chat-list-item"], [data-testid*="contact"], div[role="gridcell"]');
    for (const el of items) {
      if (isVisible(el)) {
        el.focus();
        el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, view: window }));
        el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
        el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, view: window }));
        el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
        try { el.click(); } catch { el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); }
        return { success: true };
      }
    }
    return { success: false, error: 'No search result found' };
  }

  const HIGHLIGHT_CONTAINER_ID = '__wb_highlight_layer';
  const HIGHLIGHT_STYLE_ID = '__wb_highlight_styles';

  function injectHighlightStyles() {
    if (document.getElementById(HIGHLIGHT_STYLE_ID)) return;
    const s = document.createElement('style');
    s.id = HIGHLIGHT_STYLE_ID;
    s.textContent = `
      .wb-hl-overlay{position:fixed;pointer-events:none;z-index:2147483647;border:3px solid var(--hl-c);background:color-mix(in srgb,var(--hl-c) 15%,transparent);border-radius:4px;transition:opacity .3s;box-shadow:0 0 12px color-mix(in srgb,var(--hl-c) 40%,transparent)}
      .wb-hl-overlay.fade-out{opacity:0}
      .wb-hl-label{position:fixed;pointer-events:none;z-index:2147483647;background:var(--hl-c);color:#000;font:10px/1.2 monospace;padding:1px 5px;border-radius:3px;white-space:nowrap}
    `;
    document.head.appendChild(s);
  }

  function highlightElements(args) {
    const selector = args.selector;
    const color = args.color || '#22c55e';
    const duration = args.duration || 0;
    const scrollIntoView = args.scrollIntoView || false;
    const maxElements = args.maxElements || 20;
    if (!selector) throw new Error('selector required');

    clearHighlights();
    const els = [...document.querySelectorAll(selector)].slice(0, maxElements);
    if (els.length === 0) return { elements: [], count: 0 };

    injectHighlightStyles();
    const container = document.createElement('div');
    container.id = HIGHLIGHT_CONTAINER_ID;
    document.body.appendChild(container);

    const results = [];
    els.forEach((el, i) => {
      if (!(el instanceof HTMLElement)) return;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      const overlay = document.createElement('div');
      overlay.className = 'wb-hl-overlay';
      overlay.style.setProperty('--hl-c', color);
      overlay.style.left = (rect.left + window.scrollX) + 'px';
      overlay.style.top = (rect.top + window.scrollY) + 'px';
      overlay.style.width = rect.width + 'px';
      overlay.style.height = rect.height + 'px';
      const label = document.createElement('div');
      label.className = 'wb-hl-label';
      label.style.setProperty('--hl-c', color);
      label.textContent = '#' + (i + 1);
      overlay.appendChild(label);
      container.appendChild(overlay);
      results.push({
        tag: el.tagName.toLowerCase(), text: (el.innerText || '').slice(0, 200),
        rect: { x: ~~rect.x, y: ~~rect.y, width: ~~rect.width, height: ~~rect.height },
        index: i, visible: true, selector,
      });
    });

    if (scrollIntoView && els[0] instanceof HTMLElement) els[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (duration > 0) setTimeout(() => { container.querySelectorAll('.wb-hl-overlay').forEach(o => o.classList.add('fade-out')); setTimeout(clearHighlights, 300); }, duration);
    return { elements: results, count: results.length };
  }

  function clearHighlights() {
    const c = document.getElementById(HIGHLIGHT_CONTAINER_ID);
    const n = c ? c.childElementCount : 0;
    if (c) c.remove();
    return n;
  }

  async function evaluateInPage(code) {
    try {
      return await eval(code);
    } catch (e) {
      return { error: e.message };
    }
  }
})();
