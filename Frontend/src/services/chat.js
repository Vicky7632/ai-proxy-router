import api, { getErrorMessage } from "./api";

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

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finished = false;

    async function processLine(line) {
      const trimmedLine = line.endsWith("\r") ? line.slice(0, -1) : line;
      if (!trimmedLine.startsWith("data:")) {
        return;
      }

      const payload = trimmedLine.slice(5).trim();
      if (!payload) {
        return;
      }
      if (payload === "[DONE]") {
        finished = true;
        return;
      }

      let event;
      try {
        event = JSON.parse(payload);
      } catch {
        // Ignore malformed or non-JSON SSE data and continue reading.
        return;
      }
      const text = event?.choices?.[0]?.delta?.content;
      if (typeof text === "string" && text.length > 0) {
        onChunk(text);
        await new Promise((resolve) => requestAnimationFrame(resolve));
      }
    }

    try {
      while (!finished) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          await processLine(line);
          if (finished) {
            break;
          }
        }
      }

      if (!finished) {
        buffer += decoder.decode();
        const remainingLines = buffer.split("\n");
        buffer = remainingLines.pop() || "";
        for (const line of remainingLines) {
          await processLine(line);
          if (finished) {
            break;
          }
        }
        if (!finished && buffer) {
          await processLine(buffer);
        }
      }
      onDone();
    } finally {
      reader.releaseLock();
    }
  },
};
