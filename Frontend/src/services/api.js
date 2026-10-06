import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

let refreshRequest;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const request = error.config;
    const requestUrl = request?.url || "";
    const canRefresh =
      error.response?.status === 401 &&
      request &&
      !request._retry &&
      (requestUrl === "/auth/me" || !requestUrl.startsWith("/auth/"));

    if (!canRefresh) {
      return Promise.reject(error);
    }

    request._retry = true;
    try {
      refreshRequest ||= api.post("/auth/refresh");
      await refreshRequest;
      return api(request);
    } catch (refreshError) {
      return Promise.reject(refreshError);
    } finally {
      refreshRequest = undefined;
    }
  },
);

export function getErrorMessage(error, fallback = "Something went wrong.") {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).filter(Boolean).join(" ");
  }
  if (error?.message === "Network Error") {
    return "Unable to reach the API. Check that the backend is running and VITE_API_BASE_URL is correct.";
  }
  return error?.message || fallback;
}

export default api;
