import assert from "node:assert/strict";
import test from "node:test";

import { readSseStream } from "./sse.js";

function makeStream(chunks) {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(chunk);
      }
      controller.close();
    },
  });
}

function splitBytes(bytes, size) {
  const chunks = [];
  for (let offset = 0; offset < bytes.length; offset += size) {
    chunks.push(bytes.slice(offset, offset + size));
  }
  return chunks;
}

test("reads a fragmented Markdown table through the [DONE] marker", async () => {
  const content = [
    "## High-Level Design (HLD) vs. Low-Level Design (LLD)",
    "",
    "| Feature | High-Level Design (HLD) | Low-Level Design (LLD) |",
    "| --- | --- | --- |",
    "| Focus | Overall architecture | Implementation details |",
  ].join("\n");
  const encoder = new TextEncoder();
  const separatorStart = content.indexOf("| ---");
  const contentChunks = [
    content.slice(0, separatorStart),
    content.slice(separatorStart),
  ];
  const event = encoder.encode(
    contentChunks
      .map(
        (chunk) =>
          `data: ${JSON.stringify({
            choices: [{ delta: { content: chunk } }],
          })}\n\n`,
      )
      .join("") +
      `data: ${JSON.stringify({
        choices: [{ delta: {}, finish_reason: "stop" }],
      })}\n\ndata: [DONE]\n\n`,
  );
  const received = [];

  const stats = await readSseStream(
    makeStream(splitBytes(event, 7)),
    (text) => received.push(text),
  );

  assert.equal(received.join(""), content);
  assert.deepEqual(stats, {
    eventCount: 3,
    contentCharacters: content.length,
    finishReasons: ["stop"],
  });
});

test("does not read events after [DONE]", async () => {
  const encoder = new TextEncoder();
  const stream = makeStream([
    encoder.encode(
      'data: {"choices":[{"delta":{"content":"complete"},"finish_reason":"stop"}]}\n\n' +
        "data: [DONE]\n\n" +
        'data: {"choices":[{"delta":{"content":"ignored"}}]}\n\n',
    ),
  ]);
  const received = [];

  await readSseStream(stream, (text) => received.push(text));

  assert.deepEqual(received, ["complete"]);
});

test("rejects EOF before [DONE] instead of completing silently", async () => {
  const encoder = new TextEncoder();
  const received = [];
  const originalWarn = console.warn;
  console.warn = () => {};

  try {
    await assert.rejects(
      readSseStream(
        makeStream([
          encoder.encode(
            'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n',
          ),
        ]),
        (text) => received.push(text),
      ),
      { message: "The completion stream ended before [DONE]." },
    );
  } finally {
    console.warn = originalWarn;
  }

  assert.deepEqual(received, ["partial"]);
});
