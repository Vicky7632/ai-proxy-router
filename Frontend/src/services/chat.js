import api from "./api";

export const chatService = {
  async complete(proxyKey, request) {
    return (
      await api.post("/v1/chat/completions", request, {
        headers: { Authorization: `Bearer ${proxyKey}` },
      })
    ).data;
  },
};
