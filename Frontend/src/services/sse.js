export async function readSseStream(body, onChunk) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let receivedDone = false;
  let eventCount = 0;
  let contentCharacters = 0;
  const finishReasons = new Set();

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
      receivedDone = true;
      return;
    }

    let event;
    try {
      event = JSON.parse(payload);
    } catch {
      return;
    }

    eventCount += 1;
    const choices = event?.choices;
    if (Array.isArray(choices)) {
      for (const choice of choices) {
        if (typeof choice?.finish_reason === "string") {
          finishReasons.add(choice.finish_reason);
        }
      }
    }
    const text = event?.choices?.[0]?.delta?.content;
    if (typeof text === "string" && text.length > 0) {
      contentCharacters += text.length;
      await onChunk(text);
    }
  }

  try {
    while (!receivedDone) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        await processLine(line);
        if (receivedDone) {
          break;
        }
      }
    }

    if (!receivedDone) {
      buffer += decoder.decode();
      const remainingLines = buffer.split("\n");
      buffer = remainingLines.pop() || "";
      for (const line of remainingLines) {
        await processLine(line);
        if (receivedDone) {
          break;
        }
      }
      if (!receivedDone && buffer) {
        await processLine(buffer);
      }
    }

    if (!receivedDone) {
      console.warn("SSE stream ended before [DONE]");
      throw new Error("The completion stream ended before [DONE].");
    }

    return { eventCount, contentCharacters, finishReasons: [...finishReasons] };
  } finally {
    reader.releaseLock();
  }
}
