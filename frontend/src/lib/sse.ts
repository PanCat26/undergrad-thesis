export type SSEEvent =
  | { type: "token"; text: string }
  | { type: "tool_call"; summary: string }
  | { type: "proposed_edit"; path: string; diff: string; content: string }
  | { type: "final"; content: string; citations: unknown[] }
  | { type: "done" }
  | { type: "error"; message: string };

/**
 * Read a Server-Sent-Events stream from a fetch Response, invoking `onEvent`
 * for each parsed `data:` payload.
 */
export async function readSSE(
  response: Response,
  onEvent: (event: SSEEvent) => void
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      for (const line of block.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            onEvent(JSON.parse(line.slice(6)) as SSEEvent);
          } catch {
            // ignore malformed frames
          }
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}
