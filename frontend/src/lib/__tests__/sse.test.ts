import { describe, expect, it } from "vitest";

import { readSSE, type SSEEvent } from "@/lib/sse";

function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream);
}

describe("readSSE", () => {
  it("parses data events, including ones split across chunk boundaries", async () => {
    const response = streamResponse([
      'data: {"type":"citations","citations":[]}\n\n',
      'data: {"type":"to',
      'ken","text":"Hi"}\n\ndata: {"type":"done"}\n\n',
    ]);

    const events: SSEEvent[] = [];
    await readSSE(response, (e) => events.push(e));

    expect(events.map((e) => e.type)).toEqual(["citations", "token", "done"]);
    expect(events[1]).toMatchObject({ type: "token", text: "Hi" });
  });
});
