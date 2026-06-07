import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PdfPreview } from "@/components/workspace/pdf-preview";

describe("PdfPreview", () => {
  it("shows the compile log when compilation fails", () => {
    render(
      <PdfPreview
        pdfUrl={null}
        compileLog="! Undefined control sequence."
        compiling={false}
        onCompile={vi.fn()}
      />
    );
    expect(screen.getByText(/Undefined control sequence/)).toBeInTheDocument();
  });

  it("triggers compilation when the button is clicked", () => {
    const onCompile = vi.fn();
    render(
      <PdfPreview pdfUrl={null} compileLog={null} compiling={false} onCompile={onCompile} />
    );
    fireEvent.click(screen.getByRole("button", { name: /Compile/i }));
    expect(onCompile).toHaveBeenCalled();
  });
});
