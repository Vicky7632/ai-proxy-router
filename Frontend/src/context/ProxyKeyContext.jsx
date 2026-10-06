import { createContext, useContext, useMemo, useState } from "react";

const ProxyKeyContext = createContext(null);

export function ProxyKeyProvider({ children }) {
  const [proxyKey, setProxyKey] = useState("");
  const value = useMemo(() => ({ proxyKey, setProxyKey }), [proxyKey]);

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
