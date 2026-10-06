import api from "./api";

export const providersService = {
  async getHealth(proxyKey) {
    return (
      await api.get("/v1/providers/health", {
        headers: { Authorization: `Bearer ${proxyKey}` },
      })
    ).data;
  },
};
