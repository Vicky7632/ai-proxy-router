export const PROXY_KEY_SESSION_STORAGE_KEY = "ai-proxy-router.proxy-key";

export function readProxyKeySession(storage) {
  return storage?.getItem(PROXY_KEY_SESSION_STORAGE_KEY) || "";
}

export function writeProxyKeySession(storage, proxyKey) {
  if (!storage) {
    throw new Error("Session storage is unavailable.");
  }
  if (proxyKey) {
    storage.setItem(PROXY_KEY_SESSION_STORAGE_KEY, proxyKey);
  } else {
    storage.removeItem(PROXY_KEY_SESSION_STORAGE_KEY);
  }
}

export async function validateProxyKeySession(storage, validate) {
  const proxyKey = readProxyKeySession(storage);
  if (!proxyKey) {
    return false;
  }

  try {
    await validate(proxyKey);
    return true;
  } catch (error) {
    const status = error?.response?.status;
    if (status === 401 || status === 403) {
      if (readProxyKeySession(storage) === proxyKey) {
        writeProxyKeySession(storage, "");
      }
      return false;
    }
    throw error;
  }
}
