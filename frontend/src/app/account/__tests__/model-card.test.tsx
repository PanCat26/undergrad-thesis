import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ModelCard } from "@/components/account/model-card";

const { request, updateLlm, testLlm } = vi.hoisted(() => ({
  request: vi.fn(),
  updateLlm: vi.fn(),
  testLlm: vi.fn(),
}));

let user: { id: string; email: string | null; is_guest: boolean };
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user, request, updateLlm, testLlm }) }));

describe("ModelCard", () => {
  beforeEach(() => {
    request.mockReset();
    updateLlm.mockReset();
    testLlm.mockReset();
    user = { id: "u1", email: "a@b.com", is_guest: false };
    request.mockResolvedValue([{ id: "gpt-4.1-mini", label: "gpt-4.1-mini (default)" }]);
  });

  it("shows the create-account state for guests", async () => {
    user = { id: "g", email: null, is_guest: true };
    render(<ModelCard />);
    expect(await screen.findByText(/Create an account to choose/i)).toBeInTheDocument();
  });

  it("lets a registered user enter a custom endpoint and save it", async () => {
    render(<ModelCard />);
    await screen.findByText(/gpt-4\.1-mini/i);

    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "__custom__" } });
    fireEvent.change(await screen.findByLabelText("Endpoint URL"), {
      target: { value: "http://host.docker.internal:11434/v1" },
    });
    fireEvent.change(screen.getByLabelText("Model name"), { target: { value: "llama3.1" } });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() =>
      expect(updateLlm).toHaveBeenCalledWith({
        model: "llama3.1",
        base_url: "http://host.docker.internal:11434/v1",
        api_key: null,
      })
    );
  });

  it("does not save a custom model with empty fields", async () => {
    render(<ModelCard />);
    await screen.findByText(/gpt-4\.1-mini/i);
    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "__custom__" } });
    await screen.findByLabelText("Endpoint URL");
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(testLlm).not.toHaveBeenCalled());
    expect(updateLlm).not.toHaveBeenCalled();
    // The custom menu stays open (selection isn't reset).
    expect(screen.getByLabelText("Endpoint URL")).toBeInTheDocument();
  });

  it("runs a connection test and shows the result", async () => {
    testLlm.mockResolvedValue({ ok: true });
    render(<ModelCard />);
    await screen.findByText(/gpt-4\.1-mini/i);

    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "__custom__" } });
    fireEvent.change(await screen.findByLabelText("Endpoint URL"), {
      target: { value: "http://x/v1" },
    });
    fireEvent.change(screen.getByLabelText("Model name"), { target: { value: "m" } });
    fireEvent.click(screen.getByRole("button", { name: /test connection/i }));

    await waitFor(() => expect(testLlm).toHaveBeenCalled());
    expect(await screen.findByText(/Connection succeeded/i)).toBeInTheDocument();
  });
});
