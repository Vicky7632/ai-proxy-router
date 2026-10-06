import api from "./api";

export const apiKeysService = {
  async list() {
    return (await api.get("/keys")).data;
  },
  async create(name) {
    return (await api.post("/keys", { name })).data;
  },
  async revoke(id) {
    return api.delete(`/keys/${id}`);
  },
};
