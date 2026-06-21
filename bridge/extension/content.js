// WebBridge content script - provides DOM access to the background script
(function() {
  'use strict';

  // Listen for commands from background
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'dom_command') {
      executeDOMCommand(msg.action, msg.args)
        .then(result => sendResponse({ success: true, ...result }))
        .catch(err => sendResponse({ success: false, error: err.message }));
      return true;
    }
  });

  // Expose a global for evaluate() access
  window.__webBridge = {
    snapshot: getAccessibilitySnapshot,
    find: findElements,
    click: clickElement,
    fill: fillElement,
    scrollTo: scrollToElement,
    getHtml: getHtml,
    extractText: extractText,
    extractAttr: extractAttribute,
  };

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
      case 'evaluate':
        return { result: await evaluateCode(args.code) };
      case 'scroll_stop':
        return stopScroll();
      case 'upload':
        return await uploadFile(args.selector, args.filePath, args.fileData, args.fileName);
      default:
        throw new Error(`Unknown DOM action: ${action}`);
    }
  }

  function getAccessibilitySnapshot() {
    function buildTree(node, depth = 0) {
      if (depth > 6) return null;
      if (node.nodeType === Node.TEXT_NODE) {
        const text = node.textContent.trim();
        if (!text) return null;
        return { type: 'text', text: text.slice(0, 200) };
      }
      if (node.nodeType !== Node.ELEMENT_NODE) return null;

      const tag = node.tagName.toLowerCase();
      const role = node.getAttribute('role') || '';
      const name = node.getAttribute('aria-label') || node.title || '';
      const visible = node.offsetParent !== null;
      const rect = node.getBoundingClientRect();
      const isInteractive = ['a','button','input','select','textarea','details','summary'].includes(tag)
        || node.hasAttribute('onclick')
        || node.getAttribute('role')?.match(/button|link|checkbox|radio|tab|menuitem|option/);

      let children = [];
      for (const child of node.childNodes) {
        const c = buildTree(child, depth + 1);
        if (c) children.push(c);
      }

      // Generate a stable ref and STAMP it onto the DOM node so resolveElement() can find it later
      let ref = undefined;
      if (isInteractive) {
        ref = node.getAttribute('data-wb-ref');
        if (!ref) {
          ref = `@e_${Math.random().toString(36).slice(2, 8)}`;
          node.setAttribute('data-wb-ref', ref);
        }
      }

      const entry = {
        tag,
        role: role || undefined,
        name: name || undefined,
        text: node.innerText?.slice(0, 100) || undefined,
        visible,
        rect: visible ? { x: ~~rect.x, y: ~~rect.y, w: ~~rect.width, h: ~~rect.height } : undefined,
        interactive: isInteractive || undefined,
        ref,
      };
      if (children.length) entry.children = children;
      return entry;
    }

    return buildTree(document.body) || { tag: 'body', children: [] };
  }

  function findElements(selector) {
    if (selector.startsWith('@e_')) {
      // Find by ref in snapshot — walk DOM
      return [];
    }
    try {
      const nodes = document.querySelectorAll(selector);
      return Array.from(nodes).slice(0, 20).map(el => ({
        tag: el.tagName.toLowerCase(),
        id: el.id || undefined,
        classes: el.className?.slice(0, 100) || undefined,
        text: (el.innerText || '').slice(0, 200),
        visible: el.offsetParent !== null,
        rect: el.getBoundingClientRect(),
        attrs: getAttrs(el),
      }));
    } catch {
      // Try text match
      const nodes = [...document.querySelectorAll('*')].filter(el =>
        el.children.length === 0 && el.innerText?.includes(selector)
      );
      return nodes.slice(0, 10).map(el => ({
        tag: el.tagName.toLowerCase(),
        text: el.innerText?.slice(0, 200),
        visible: el.offsetParent !== null,
      }));
    }
  }

  function clickElement(selector) {
    const el = resolveElement(selector);
    if (!el) throw new Error('Element not found');

    // Try native click first, fallback to MouseEvent
    try {
      el.click();
    } catch {
      el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    }
    return { success: true, tag: el.tagName.toLowerCase(), text: (el.innerText || '').slice(0, 100) };
  }

  function fillElement(selector, value) {
    const el = resolveElement(selector);
    if (!el) throw new Error('Element not found');

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

  function getScrollableContainer() {
    // Priority selectors for common SPA platforms
    const prioritySelectors = [
      '[role="main"]',
      'main',
      '[data-pagelet="root"]',
      '#facebook [role="feed"]',
      '[data-pagelet="Feed"]',
      '[aria-label="Home"]',
      '[role="tabpanel"]',
      '#react-root',
      '#root',
      '#app',
      '.app',
    ];
    for (const sel of prioritySelectors) {
      const el = document.querySelector(sel);
      if (el) {
        const style = window.getComputedStyle(el);
        if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
          const range = el.scrollHeight - el.clientHeight;
          if (range > 100) return el;
        }
        // Also check first scrollable child of the priority element
        const children = el.querySelectorAll('*');
        for (const child of children) {
          const cs = window.getComputedStyle(child);
          if (cs.overflowY === 'auto' || cs.overflowY === 'scroll') {
            const cr = child.scrollHeight - child.clientHeight;
            if (cr > 100) return child;
          }
        }
      }
    }

    // Fallback: window scroll range
    const docEl = document.documentElement;
    const body = document.body;
    const docElOverflow = window.getComputedStyle(docEl).overflowY;
    const bodyOverflow = body ? window.getComputedStyle(body).overflowY : '';
    let best = window;
    let maxRange = 0;

    if (docElOverflow !== 'hidden' && bodyOverflow !== 'hidden') {
      const docHeight = Math.max(docEl.scrollHeight, body ? body.scrollHeight : 0);
      maxRange = Math.max(0, docHeight - window.innerHeight);
    }

    // Find the nested scrollable element with the largest scroll range
    const all = document.querySelectorAll('*');
    for (const el of all) {
      if (el === document.documentElement || el === document.body) continue;
      const style = window.getComputedStyle(el);
      if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
        const range = el.scrollHeight - el.clientHeight;
        if (range > 10 && range > maxRange) {
          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            maxRange = range;
            best = el;
          }
        }
      }
    }
    return best;
  }

  async function scrollToElement(selector, x, y) {
    const container = getScrollableContainer();
    const isWin = container === window;
    const getScrollY = () => isWin ? window.scrollY : container.scrollTop;
    const getScrollX = () => isWin ? window.scrollX : container.scrollLeft;

    const scrollBy = (dx, dy) => {
      container.scrollBy({ top: dy, left: dx, behavior: 'auto' });
    };

    // If offsets (x or y) are provided, scroll the container or specified target element by the offsets
    if ((x !== undefined && x !== null) || (y !== undefined && y !== null)) {
      const scrollX = (x !== undefined && x !== null) ? x : 0;
      const scrollY = (y !== undefined && y !== null) ? y : 0;
      
      if (selector) {
        const el = resolveElement(selector);
        if (el) {
          const before = el.scrollTop;
          el.scrollBy({ top: scrollY, left: scrollX, behavior: 'auto' });
          return { success: true, mode: 'element-offset', tag: el.tagName.toLowerCase(), top: el.scrollTop, left: el.scrollLeft, moved: el.scrollTop - before };
        }
      }
      const before = getScrollY();
      scrollBy(scrollX, scrollY);
      return { success: true, mode: 'offset', top: getScrollY(), left: getScrollX(), moved: getScrollY() - before };
    }

    if (!selector) {
      // Page scroll: default down 500px
      const before = getScrollY();
      scrollBy(0, 500);
      return { success: true, mode: 'page', top: getScrollY(), moved: getScrollY() - before };
    }
    const el = resolveElement(selector);
    if (!el) {
      // Element not found — fallback to page scroll
      const before = getScrollY();
      scrollBy(0, 500);
      return { success: true, mode: 'page-fallback', top: getScrollY(), moved: getScrollY() - before };
    }
    el.scrollIntoView({ behavior: 'auto', block: 'center' });
    return { success: true, mode: 'element', tag: el.tagName.toLowerCase() };
  }

  function getHtml(selector) {
    if (!selector) return document.documentElement.outerHTML;
    const el = resolveElement(selector);
    if (!el) return null;
    return el.outerHTML;
  }

  function extractText(selector) {
    const els = resolveElements(selector);
    return els.map(el => el.innerText.trim());
  }

  function extractAttribute(selector, attr) {
    const els = resolveElements(selector);
    return els.map(el => el.getAttribute(attr));
  }

  async function evaluateCode(code) {
    const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
    // Auto-wrap: if it looks like an expression (not a block statement), add return
    const trimmed = code.trim();
    const needsReturn = !trimmed.startsWith('{') && !trimmed.startsWith('return') && !trimmed.startsWith('if') && !trimmed.startsWith('for') && !trimmed.startsWith('while') && !trimmed.startsWith('switch') && !trimmed.startsWith('try') && !trimmed.startsWith('let ') && !trimmed.startsWith('const ') && !trimmed.startsWith('var ') && !trimmed.startsWith('function') && !trimmed.startsWith('class') && !trimmed.includes(';');
    const wrappedCode = needsReturn ? `return ${code}` : code;
    const fn = new AsyncFunction('window', 'document', wrappedCode);
    return await fn(window, document);
  }

  function resolveElement(selector) {
    if (selector.startsWith('@e_')) {
      // Resolve from snapshot tree (linear scan)
      const all = document.querySelectorAll('[data-wb-ref]');
      for (const el of all) {
        if (el.getAttribute('data-wb-ref') === selector) return el;
      }
      return null;
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

  function getAttrs(el) {
    const m = {};
    for (const a of el.attributes) {
      if (a.name.startsWith('data-') || ['href', 'src', 'alt', 'title', 'placeholder', 'type', 'name', 'value'].includes(a.name)) {
        m[a.name] = a.value;
      }
    }
    return m;
  }

  async function uploadFile(selector, filePath, fileData, fileName) {
    const el = resolveElement(selector);
    if (!el) throw new Error('Element not found');
    if (el.tagName !== 'INPUT' || el.type !== 'file') throw new Error('Element is not a file input');

    if (fileData) {
      // fileData is base64 content
      const byteStr = atob(fileData);
      const ab = new ArrayBuffer(byteStr.length);
      const ia = new Uint8Array(ab);
      for (let i = 0; i < byteStr.length; i++) ia[i] = byteStr.charCodeAt(i);
      const blob = new Blob([ab]);
      const file = new File([blob], fileName || 'upload.bin');
      const dt = new DataTransfer();
      dt.items.add(file);
      el.files = dt.files;
    } else if (filePath) {
      // Use a file input change event with the path
      // Note: browser security restricts actual file path access;
      // use fileData approach for reliable uploads
      throw new Error('filePath not supported directly; use fileData (base64) instead');
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
    return new Promise((resolve) => {
      let total = 0;
      let i = 0;
      let zeroScrollCount = 0;
      scrollIntervalId = setInterval(() => {
        const currentScrollY = isWin ? window.scrollY : container.scrollTop;
        const totalHeight = isWin ? Math.max(document.documentElement.scrollHeight, document.body.scrollHeight) : container.scrollHeight;
        const viewportHeight = isWin ? window.innerHeight : container.clientHeight;

        if (i >= steps) {
          clearInterval(scrollIntervalId);
          scrollIntervalId = null;
          resolve({ scrolled: total, reachedEnd: viewportHeight + currentScrollY >= totalHeight - 10 });
          return;
        }
        const before = currentScrollY;
        container.scrollBy({ top: stepPx, left: 0, behavior: 'auto' });
        const after = isWin ? window.scrollY : container.scrollTop;
        const actual = after - before;
        total += actual;
        i++;
        
        if (actual === 0) {
          zeroScrollCount++;
          if (zeroScrollCount >= 5) {
            clearInterval(scrollIntervalId);
            scrollIntervalId = null;
            const reachedBottom = stepPx > 0 && (viewportHeight + currentScrollY >= totalHeight - 10);
            resolve({ scrolled: total, reachedEnd: reachedBottom || totalHeight <= viewportHeight });
            return;
          }
        } else {
          zeroScrollCount = 0;
        }
      }, ms);
    });
  }

  function stopScroll() {
    if (scrollIntervalId) {
      clearInterval(scrollIntervalId);
      scrollIntervalId = null;
    }
    return { success: true, stopped: true };
  }
})();
