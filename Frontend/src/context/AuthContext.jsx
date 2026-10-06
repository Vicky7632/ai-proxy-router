import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useLocation } from "react-router-dom";
import { authService } from "../services/auth";
import { getErrorMessage } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const location = useLocation();
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading");
  const [authError, setAuthError] = useState("");
  const userRef = useRef(null);
  const sessionRequest = useRef(null);

  const loadUser = useCallback(async () => {
    if (userRef.current) {
      return userRef.current;
    }
    if (sessionRequest.current) {
      return sessionRequest.current;
    }

    setStatus("loading");
    setAuthError("");
    const request = authService
      .me()
      .then((authenticatedUser) => {
        userRef.current = authenticatedUser;
        setUser(authenticatedUser);
        setStatus("authenticated");
        return authenticatedUser;
      })
      .catch((error) => {
        userRef.current = null;
        setUser(null);
        if (error.response?.status === 401) {
          setStatus("unauthenticated");
        } else {
          setAuthError(getErrorMessage(error, "Unable to connect to the API."));
          setStatus("error");
        }
        return null;
      })
      .finally(() => {
        sessionRequest.current = null;
      });
    sessionRequest.current = request;
    return request;
  }, []);

  useEffect(() => {
    if (location.pathname === "/dashboard" || location.pathname.startsWith("/dashboard/")) {
      loadUser();
    } else {
      setStatus((current) => (current === "loading" ? "unauthenticated" : current));
    }
  }, [loadUser, location.pathname]);

  const value = useMemo(
    () => ({
      user,
      status,
      authError,
      retryAuth: loadUser,
      async login(credentials) {
        await authService.login(credentials);
        const currentUser = await authService.me();
        userRef.current = currentUser;
        setUser(currentUser);
        setAuthError("");
        setStatus("authenticated");
        return currentUser;
      },
      setAuthenticatedUser(currentUser) {
        userRef.current = currentUser;
        setUser(currentUser);
        setAuthError("");
        setStatus("authenticated");
      },
      async logout() {
        await authService.logout();
        userRef.current = null;
        setUser(null);
        setAuthError("");
        setStatus("unauthenticated");
      },
    }),
    [authError, loadUser, status, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
