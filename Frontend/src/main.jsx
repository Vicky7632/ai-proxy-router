import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { ProxyKeyProvider } from "./context/ProxyKeyContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ProxyKeyProvider>
          <App />
        </ProxyKeyProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
