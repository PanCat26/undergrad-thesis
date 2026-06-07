import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FileTree } from "@/components/workspace/file-tree";
import type { ProjectFile } from "@/lib/types";

const files: ProjectFile[] = [
  { id: "1", path: "main.tex", updated_at: "2026-01-01" },
  { id: "2", path: "chapters/intro.tex", updated_at: "2026-01-01" },
];

const noop = () => Promise.resolve();

describe("FileTree", () => {
  it("renders a nested folder and selects a file by its name", () => {
    const onSelect = vi.fn();
    render(
      <FileTree
        files={files}
        selectedId="1"
        onSelect={onSelect}
        onCreate={noop}
        onRename={noop}
        onDelete={noop}
        onDeleteFolder={noop}
      />
    );
    expect(screen.getByText("main.tex")).toBeInTheDocument();
    expect(screen.getByText("chapters")).toBeInTheDocument();
    fireEvent.click(screen.getByText("intro.tex"));
    expect(onSelect).toHaveBeenCalledWith(files[1]);
  });

  it("collapses a folder when clicked", () => {
    render(
      <FileTree
        files={files}
        selectedId={null}
        onSelect={vi.fn()}
        onCreate={noop}
        onRename={noop}
        onDelete={noop}
        onDeleteFolder={noop}
      />
    );
    expect(screen.getByText("intro.tex")).toBeInTheDocument();
    fireEvent.click(screen.getByText("chapters"));
    expect(screen.queryByText("intro.tex")).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no files", () => {
    render(
      <FileTree
        files={[]}
        selectedId={null}
        onSelect={vi.fn()}
        onCreate={noop}
        onRename={noop}
        onDelete={noop}
        onDeleteFolder={noop}
      />
    );
    expect(screen.getByText("No files")).toBeInTheDocument();
  });
});
