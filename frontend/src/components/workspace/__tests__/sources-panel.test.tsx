import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SourcesPanel } from "@/components/workspace/sources-panel";
import type { Source } from "@/lib/types";

const { request, upload } = vi.hoisted(() => ({ request: vi.fn(), upload: vi.fn() }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ request, upload }) }));

const props = {
  projectId: "p1",
  viewingSourceId: null,
  onView: vi.fn(),
  onSourceDeleted: vi.fn(),
};

const source: Source = {
  id: "1",
  filename: "paper.pdf",
  kind: "paper",
  ext: ".pdf",
  size_bytes: 10,
  status: "ready",
  error: null,
  chunk_count: 3,
  created_at: "",
  updated_at: "",
};

describe("SourcesPanel", () => {
  beforeEach(() => {
    request.mockReset();
    upload.mockReset();
  });

  it("shows the empty state when there are no sources", async () => {
    request.mockResolvedValue([]);
    render(<SourcesPanel {...props} />);
    expect(await screen.findByText(/No sources/i)).toBeInTheDocument();
  });

  it("renders uploaded sources", async () => {
    request.mockResolvedValue([source]);
    render(<SourcesPanel {...props} />);
    expect(await screen.findByText("paper.pdf")).toBeInTheDocument();
  });
});
