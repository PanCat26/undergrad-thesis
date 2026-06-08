import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SourceViewer } from "@/components/workspace/source-viewer";
import type { Source } from "@/lib/types";

const { request, requestRaw } = vi.hoisted(() => ({ request: vi.fn(), requestRaw: vi.fn() }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ request, requestRaw }) }));

const baseSource: Source = {
  id: "1",
  filename: "a.tex",
  kind: "paper",
  ext: ".tex",
  size_bytes: 1,
  status: "ready",
  error: null,
  chunk_count: 1,
  created_at: "",
  updated_at: "",
};

describe("SourceViewer", () => {
  beforeEach(() => {
    request.mockReset();
    requestRaw.mockReset();
  });

  it("renders a text preview", async () => {
    request.mockResolvedValue({ view: "text", text: "hello body" });
    render(<SourceViewer projectId="p1" source={baseSource} onClose={vi.fn()} />);
    expect(await screen.findByText("hello body")).toBeInTheDocument();
  });

  it("renders a table preview", async () => {
    request.mockResolvedValue({ view: "table", columns: ["alpha", "beta"], rows: [["1", "2"]] });
    render(
      <SourceViewer
        projectId="p1"
        source={{ ...baseSource, ext: ".csv", kind: "dataset", filename: "d.csv" }}
        onClose={vi.fn()}
      />
    );
    expect(await screen.findByText("alpha")).toBeInTheDocument();
    expect(await screen.findByText("1")).toBeInTheDocument();
  });
});
