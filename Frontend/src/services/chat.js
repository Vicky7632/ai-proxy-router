import api, { getErrorMessage } from "./api";
import { readSseStream } from "./sse";

async function readErrorResponse(response) {
  try {
    const data = await response.json();
    return { response: { data } };
  } catch {
    return { response: { data: null } };
  }
}

export const chatService = {
  async complete(proxyKey, request) {
    return (
      await api.post("/v1/chat/completions", request, {
        headers: { Authorization: `Bearer ${proxyKey}` },
      })
    ).data;
  },

  async stream(proxyKey, request, onChunk, onDone = () => {}) {
    const response = await fetch(api.getUri({ url: "/v1/chat/completions" }), {
      method: "POST",
      credentials: "include",
      headers: {
        Authorization: `Bearer ${proxyKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await readErrorResponse(response);
      throw new Error(
        getErrorMessage(error, "The completion request failed."),
      );
    }

    if (!response.body) {
      throw new Error("The completion stream was unavailable.");
    }

    const streamStats = await readSseStream(response.body, async (text) => {
      onChunk(text);
      await new Promise((resolve) => requestAnimationFrame(resolve));
    });
    console.info("SSE stream completed", {
      receivedDone: true,
      cacheStatus: response.headers.get("X-Cache") || "UNKNOWN",
      ...streamStats,
    });
    onDone();
  },
};
