import api from "./api";

export const authService = {
  async login(credentials) {
    return (await api.post("/auth/login", credentials)).data;
  },
  async register(details) {
    return (await api.post("/auth/register", details)).data;
  },
  async me() {
    return (await api.get("/auth/me")).data;
  },
  async logout() {
    return api.post("/auth/logout");
  },
};
