import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AssistantPanel } from "@/components/workspace/assistant-panel";

const { request, requestRaw } = vi.hoisted(() => ({ request: vi.fn(), requestRaw: vi.fn() }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ request, requestRaw }) }));

const props = {
  projectId: "p1",
  onViewSource: vi.fn(),
  onOpenFile: vi.fn(),
  onEditApplied: vi.fn(),
};

describe("AssistantPanel", () => {
  beforeEach(() => {
    request.mockReset();
    requestRaw.mockReset();
  });

  it("ensures a session exists and shows the empty state", async () => {
    request.mockImplementation((path: string, options?: { method?: string }) => {
      if (path.endsWith("/sessions") && options?.method === "POST") {
        return Promise.resolve({ id: "s1", title: "Chat 1", mode: "qa", created_at: "", updated_at: "" });
      }
      if (path.endsWith("/sessions")) return Promise.resolve([]);
      return Promise.resolve([]);
    });
    render(<AssistantPanel {...props} />);
    expect(await screen.findByText(/Ask a question about your sources/i)).toBeInTheDocument();
    expect(await screen.findByText("Chat 1")).toBeInTheDocument();
  });

  it("loads and renders an existing session's messages as markdown", async () => {
    request.mockImplementation((path: string) => {
      if (path.endsWith("/sessions")) {
        return Promise.resolve([
          { id: "s1", title: "Chat 1", mode: "qa", created_at: "", updated_at: "" },
        ]);
      }
      if (path.includes("/messages")) {
        return Promise.resolve([
          { id: "m1", role: "assistant", content: "**Hello** there", citations: null, created_at: "" },
        ]);
      }
      return Promise.resolve([]);
    });
    render(<AssistantPanel {...props} />);
    expect(await screen.findByText("Hello")).toBeInTheDocument();
  });

  it("switches mode via PATCH when the Agent toggle is clicked", async () => {
    request.mockImplementation((path: string, options?: { method?: string }) => {
      if (path.endsWith("/sessions") && !options?.method) {
        return Promise.resolve([
          { id: "s1", title: "Chat 1", mode: "qa", created_at: "", updated_at: "" },
        ]);
      }
      return Promise.resolve([]);
    });
    render(<AssistantPanel {...props} />);
    fireEvent.click(await screen.findByText("Agent"));
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith(
        "/api/projects/p1/chat/sessions/s1",
        expect.objectContaining({ method: "PATCH", body: { mode: "agentic" } })
      )
    );
  });
});
