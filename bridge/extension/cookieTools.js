export async function executeCookieTool(action, args, getActiveTab) {
  switch (action) {

    case 'cookies_getAll': {
      const opts = {};
      if (args.domain) opts.domain = args.domain;
      if (args.url) opts.url = args.url;
      if (args.name) opts.name = args.name;
      const cookies = await chrome.cookies.getAll(opts);
      return {
        success: true,
        cookies: cookies.map(c => ({
          name: c.name, value: c.value, domain: c.domain,
          path: c.path, secure: c.secure, httpOnly: c.httpOnly,
          sameSite: c.sameSite, session: c.session,
          expirationDate: c.expirationDate,
        })),
        count: cookies.length,
      };
    }

    case 'cookies_get': {
      if (!args.url && !args.domain) return { error: 'url or domain required' };
      if (!args.name) return { error: 'name required' };
      const url = args.url || `https://${args.domain.replace(/^\./, '')}/`;
      const cookie = await chrome.cookies.get({ url, name: args.name });
      if (!cookie) return { success: true, cookie: null, found: false };
      return { success: true, cookie: { name: cookie.name, value: cookie.value, domain: cookie.domain, path: cookie.path, secure: cookie.secure, httpOnly: cookie.httpOnly }, found: true };
    }

    case 'cookies_set': {
      if (!args.url) return { error: 'url required' };
      if (!args.name) return { error: 'name required' };
      if (args.value === undefined) return { error: 'value required' };
      const details = { url: args.url, name: args.name, value: args.value };
      if (args.domain) details.domain = args.domain;
      if (args.path) details.path = args.path;
      if (args.secure !== undefined) details.secure = args.secure;
      if (args.httpOnly !== undefined) details.httpOnly = args.httpOnly;
      if (args.sameSite) details.sameSite = args.sameSite;
      if (args.expirationDate) details.expirationDate = args.expirationDate;
      const cookie = await chrome.cookies.set(details);
      return { success: true, cookie: cookie ? { name: cookie.name, domain: cookie.domain, path: cookie.path } : null };
    }

    case 'cookies_delete': {
      if (!args.url) return { error: 'url required' };
      if (!args.name) return { error: 'name required' };
      await chrome.cookies.remove({ url: args.url, name: args.name });
      return { success: true, deleted: args.name };
    }

    case 'cookies_clear': {
      if (!args.domain) return { error: 'domain required' };
      const domain = args.domain.replace(/^\./, '');
      const all = await chrome.cookies.getAll({ domain });
      let deleted = 0;
      for (const c of all) {
        const url = (c.secure ? 'https' : 'http') + '://' + domain + c.path;
        try { await chrome.cookies.remove({ url, name: c.name }); deleted++; } catch {}
      }
      return { success: true, deleted, count: all.length };
    }

    default:
      return null;
  }
}

export function isStorageAction(action) {
  return action.startsWith('storage_');
}

export async function executeStorageTool(action, args, tabId) {
  const storageMap = {
    storage_getLocal: 'local',
    storage_setLocal: 'local',
    storage_removeLocal: 'local',
    storage_clearLocal: 'local',
    storage_getSession: 'session',
    storage_setSession: 'session',
    storage_removeSession: 'session',
    storage_clearSession: 'session',
  };
  const area = storageMap[action];
  if (!area) return null;

  const key = args.key;
  const value = args.value;

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    world: 'MAIN',
    func: evalInWorld,
    args: [{ action, key: key ?? null, value: value ?? null }],
  });

  if (!results || !results[0]) return { error: 'No result from page' };
  return results[0].result;
}

function evalInWorld(params) {
  const storage = params.action.includes('Session') ? sessionStorage : localStorage;
  const k = params.key;
  const v = params.value;

  switch (params.action) {
    case 'storage_getLocal':
    case 'storage_getSession':
      if (k != null) return { success: true, key: k, value: storage.getItem(k) };
      const all = {};
      for (let i = 0; i < storage.length; i++) {
        const name = storage.key(i);
        all[name] = storage.getItem(name);
      }
      return { success: true, entries: all, count: storage.length };

    case 'storage_setLocal':
    case 'storage_setSession':
      storage.setItem(k, v);
      return { success: true, key: k, set: true };

    case 'storage_removeLocal':
    case 'storage_removeSession':
      storage.removeItem(k);
      return { success: true, key: k, removed: true };

    case 'storage_clearLocal':
    case 'storage_clearSession':
      const before = storage.length;
      storage.clear();
      return { success: true, cleared: before };
  }
}
