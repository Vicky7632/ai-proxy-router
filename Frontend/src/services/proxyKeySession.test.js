import assert from "node:assert/strict";
import test from "node:test";

import api from "./api.js";
import { apiKeysService } from "./apiKeys.js";
import {
  PROXY_KEY_SESSION_STORAGE_KEY,
  readProxyKeySession,
  validateProxyKeySession,
  writeProxyKeySession,
} from "./proxyKeySession.js";

function makeStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) {
      return values.get(key) ?? null;
    },
    setItem(key, value) {
      values.set(key, String(value));
    },
    removeItem(key) {
      values.delete(key);
    },
  };
}

test("restores a connected key from tab storage after page initialization", () => {
  const storage = makeStorage({
    [PROXY_KEY_SESSION_STORAGE_KEY]: "existing-proxy-key",
  });

  assert.equal(readProxyKeySession(storage), "existing-proxy-key");
});

test("persists and clears the connected key in tab storage", () => {
  const storage = makeStorage();

  writeProxyKeySession(storage, "existing-proxy-key");
  assert.equal(readProxyKeySession(storage), "existing-proxy-key");

  writeProxyKeySession(storage, "");
  assert.equal(readProxyKeySession(storage), "");
});

test("clears a stored key rejected by the backend", async () => {
  const storage = makeStorage({
    [PROXY_KEY_SESSION_STORAGE_KEY]: "revoked-proxy-key",
  });
  let validatedKey;

  const isValid = await validateProxyKeySession(storage, async (key) => {
    validatedKey = key;
    throw { response: { status: 401 } };
  });

  assert.equal(validatedKey, "revoked-proxy-key");
  assert.equal(isValid, false);
  assert.equal(readProxyKeySession(storage), "");
});

test("does not clear a newly connected key when an older validation fails", async () => {
  const storage = makeStorage({
    [PROXY_KEY_SESSION_STORAGE_KEY]: "old-proxy-key",
  });

  const isValid = await validateProxyKeySession(storage, async () => {
    writeProxyKeySession(storage, "new-proxy-key");
    throw { response: { status: 401 } };
  });

  assert.equal(isValid, false);
  assert.equal(readProxyKeySession(storage), "new-proxy-key");
});

test("preserves the stored key and surfaces transient validation failures", async () => {
  const storage = makeStorage({
    [PROXY_KEY_SESSION_STORAGE_KEY]: "existing-proxy-key",
  });
  const networkError = new Error("API unavailable");

  await assert.rejects(
    validateProxyKeySession(storage, async () => {
      throw networkError;
    }),
    networkError,
  );
  assert.equal(readProxyKeySession(storage), "existing-proxy-key");
});

test("API-key list failures remain visible to the page caller", async () => {
  const originalGet = api.get;
  const unauthorized = { response: { status: 401 } };
  api.get = async () => {
    throw unauthorized;
  };

  try {
    await assert.rejects(apiKeysService.list(), (error) => error === unauthorized);
  } finally {
    api.get = originalGet;
  }
});
