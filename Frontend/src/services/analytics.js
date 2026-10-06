import api from "./api";

export const analyticsService = {
  async getCacheAnalytics(proxyKey) {
    return (
      await api.get("/v1/analytics/cache", {
        headers: { Authorization: `Bearer ${proxyKey}` },
      })
    ).data;
  },
};
