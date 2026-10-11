import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { analyticsService } from "../services/analytics";
import {
  readProxyKeySession,
  validateProxyKeySession,
  writeProxyKeySession,
} from "../services/proxyKeySession";

const ProxyKeyContext = createContext(null);

function getSessionStorage() {
  try {
    return window.sessionStorage;
  } catch (error) {
    console.warn("Unable to access proxy-key session storage", {
      errorType: error?.name || "Error",
    });
    return null;
  }
}

export function ProxyKeyProvider({ children }) {
  const [storage] = useState(getSessionStorage);
  const [initialProxyKey] = useState(() => {
    try {
      return readProxyKeySession(storage);
    } catch (error) {
      console.warn("Unable to restore proxy-key session state", {
        errorType: error?.name || "Error",
      });
      return "";
    }
  });
  const [proxyKey, setProxyKeyState] = useState(initialProxyKey);

  const setProxyKey = useCallback(
    (nextProxyKey) => {
      setProxyKeyState(nextProxyKey);
      try {
        writeProxyKeySession(storage, nextProxyKey);
      } catch (error) {
        console.warn("Unable to persist proxy-key session state", {
          errorType: error?.name || "Error",
        });
      }
    },
    [storage],
  );

  useEffect(() => {
    if (!initialProxyKey || !storage) {
      return;
    }

    let active = true;
    validateProxyKeySession(storage, (storedKey) =>
      analyticsService.getCacheAnalytics(storedKey),
    )
      .then((isValid) => {
        const currentProxyKey = readProxyKeySession(storage);
        if (
          !active ||
          isValid ||
          (currentProxyKey && currentProxyKey !== initialProxyKey)
        ) {
          return;
        }
        setProxyKeyState("");
      })
      .catch((error) => {
        console.warn("Unable to validate restored proxy key", {
          errorType: error?.name || "Error",
          status: error?.response?.status || null,
        });
      });

    return () => {
      active = false;
    };
  }, [initialProxyKey, storage]);

  const value = useMemo(() => ({ proxyKey, setProxyKey }), [proxyKey, setProxyKey]);

  return (
    <ProxyKeyContext.Provider value={value}>
      {children}
    </ProxyKeyContext.Provider>
  );
}

export function useProxyKey() {
  const context = useContext(ProxyKeyContext);
  if (!context) {
    throw new Error("useProxyKey must be used within a ProxyKeyProvider");
  }
  return context;
}
