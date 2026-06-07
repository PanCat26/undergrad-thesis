import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectsView } from "@/components/projects/projects-view";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ request }) }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

describe("ProjectsView", () => {
  beforeEach(() => {
    request.mockReset();
  });

  it("shows the empty state when there are no projects", async () => {
    request.mockResolvedValue([]);
    render(<ProjectsView />);
    expect(await screen.findByText(/No projects yet/i)).toBeInTheDocument();
  });

  it("renders the list of projects", async () => {
    request.mockResolvedValue([
      { id: "1", name: "Thesis", created_at: "2026-01-01", updated_at: "2026-01-02" },
    ]);
    render(<ProjectsView />);
    expect(await screen.findByText("Thesis")).toBeInTheDocument();
  });

  it("shows an error state when loading fails", async () => {
    request.mockRejectedValue(new Error("boom"));
    render(<ProjectsView />);
    expect(await screen.findByText(/Failed to load projects/i)).toBeInTheDocument();
  });
});
