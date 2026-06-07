"use client";

import * as React from "react";
import { toast } from "sonner";
import { ChevronDown, ChevronRight, FileText, Folder, MoreVertical, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ProjectFile } from "@/lib/types";

interface FileTreeProps {
  files: ProjectFile[];
  selectedId: string | null;
  onSelect: (file: ProjectFile) => void;
  onCreate: (path: string) => Promise<void>;
  onRename: (file: ProjectFile, path: string) => Promise<void>;
  onDelete: (file: ProjectFile) => Promise<void>;
  onDeleteFolder: (prefix: string) => Promise<void>;
}

type TreeNode =
  | { type: "file"; file: ProjectFile }
  | { type: "folder"; name: string; path: string; children: TreeNode[] };

function buildTree(files: ProjectFile[]): TreeNode[] {
  const root: TreeNode[] = [];
  for (const file of files) {
    const parts = file.path.split("/");
    let level = root;
    for (let i = 0; i < parts.length - 1; i++) {
      const path = parts.slice(0, i + 1).join("/");
      let folder = level.find(
        (n): n is Extract<TreeNode, { type: "folder" }> =>
          n.type === "folder" && n.name === parts[i]
      );
      if (!folder) {
        folder = { type: "folder", name: parts[i], path, children: [] };
        level.push(folder);
      }
      level = folder.children;
    }
    level.push({ type: "file", file });
  }

  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
      const an = a.type === "folder" ? a.name : a.file.path;
      const bn = b.type === "folder" ? b.name : b.file.path;
      return an.localeCompare(bn);
    });
    for (const node of nodes) if (node.type === "folder") sortNodes(node.children);
  };
  sortNodes(root);
  return root;
}

function basename(path: string): string {
  return path.split("/").pop() ?? path;
}

export function FileTree({
  files,
  selectedId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  onDeleteFolder,
}: FileTreeProps) {
  const [createPrefix, setCreatePrefix] = React.useState<string | null>(null);
  const [renaming, setRenaming] = React.useState<ProjectFile | null>(null);
  const [deletingFile, setDeletingFile] = React.useState<ProjectFile | null>(null);
  const [deletingFolder, setDeletingFolder] = React.useState<string | null>(null);
  const [collapsed, setCollapsed] = React.useState<Set<string>>(new Set());

  const tree = React.useMemo(() => buildTree(files), [files]);

  const toggle = (path: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });

  const renderNodes = (nodes: TreeNode[], depth: number): React.ReactNode =>
    nodes.map((node) => {
      const indent = { paddingLeft: depth * 12 + 8 };
      if (node.type === "folder") {
        const isCollapsed = collapsed.has(node.path);
        return (
          <li key={`d:${node.path}`}>
            <div className="group flex items-center gap-1 py-1 pr-2 text-sm hover:bg-accent" style={indent}>
              <button
                className="flex min-w-0 flex-1 items-center gap-1 text-left"
                onClick={() => toggle(node.path)}
              >
                {isCollapsed ? (
                  <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                )}
                <Folder className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="truncate">{node.name}</span>
              </button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-5 w-5 opacity-0 group-hover:opacity-100"
                    aria-label="Folder actions"
                  >
                    <MoreVertical className="h-3.5 w-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onSelect={() => setCreatePrefix(`${node.path}/`)}>
                    New file
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onSelect={() => setDeletingFolder(node.path)}
                  >
                    Delete folder
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
            {!isCollapsed && <ul>{renderNodes(node.children, depth + 1)}</ul>}
          </li>
        );
      }
      return (
        <li key={`f:${node.file.id}`}>
          <div
            className={cn(
              "group flex items-center gap-1 py-1 pr-2 text-sm hover:bg-accent",
              selectedId === node.file.id && "bg-accent"
            )}
            style={indent}
          >
            <button
              className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
              onClick={() => onSelect(node.file)}
            >
              <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate">{basename(node.file.path)}</span>
            </button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5 opacity-0 group-hover:opacity-100"
                  aria-label="File actions"
                >
                  <MoreVertical className="h-3.5 w-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => setRenaming(node.file)}>Rename</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onSelect={() => setDeletingFile(node.file)}
                >
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </li>
      );
    });

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between border-b px-3 py-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Files
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          aria-label="New file"
          onClick={() => setCreatePrefix("")}
        >
          <Plus />
        </Button>
      </div>

      <ul className="flex-1 overflow-auto py-1">
        {renderNodes(tree, 0)}
        {files.length === 0 && <li className="px-3 py-2 text-xs text-muted-foreground">No files</li>}
      </ul>

      <PathDialog
        open={createPrefix !== null}
        title="New file"
        description="Enter a path, e.g. chapters/intro.tex"
        confirmLabel="Create"
        initial={createPrefix ?? ""}
        onOpenChange={(open) => !open && setCreatePrefix(null)}
        onSubmit={onCreate}
      />
      <PathDialog
        open={renaming !== null}
        title="Rename file"
        confirmLabel="Save"
        initial={renaming?.path ?? ""}
        onOpenChange={(open) => !open && setRenaming(null)}
        onSubmit={async (path) => {
          if (renaming) await onRename(renaming, path);
        }}
      />
      <ConfirmDeleteDialog
        open={deletingFile !== null}
        title="Delete file"
        body={
          <>
            Permanently delete{" "}
            <span className="font-medium text-foreground">{deletingFile?.path}</span>? This cannot be
            undone.
          </>
        }
        onOpenChange={(open) => !open && setDeletingFile(null)}
        onConfirm={async () => {
          if (deletingFile) await onDelete(deletingFile);
        }}
      />
      <ConfirmDeleteDialog
        open={deletingFolder !== null}
        title="Delete folder"
        body={
          <>
            Permanently delete the folder{" "}
            <span className="font-medium text-foreground">{deletingFolder}</span> and all files
            inside it? This cannot be undone.
          </>
        }
        onOpenChange={(open) => !open && setDeletingFolder(null)}
        onConfirm={async () => {
          if (deletingFolder) await onDeleteFolder(deletingFolder);
        }}
      />
    </div>
  );
}

function PathDialog({
  open,
  title,
  description,
  confirmLabel,
  initial = "",
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel: string;
  initial?: string;
  onOpenChange: (open: boolean) => void;
  onSubmit: (path: string) => Promise<void>;
}) {
  const [path, setPath] = React.useState(initial);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (open) setPath(initial);
  }, [open, initial]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!path.trim()) return;
    setLoading(true);
    try {
      await onSubmit(path.trim());
      onOpenChange(false);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            {description && <DialogDescription>{description}</DialogDescription>}
          </DialogHeader>
          <div className="space-y-1.5 py-4">
            <Label htmlFor="file-path">Path</Label>
            <Input
              id="file-path"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="main.tex"
              autoFocus
              required
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={loading}>
              {confirmLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ConfirmDeleteDialog({
  open,
  title,
  body,
  onOpenChange,
  onConfirm,
}: {
  open: boolean;
  title: string;
  body: React.ReactNode;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => Promise<void>;
}) {
  const [loading, setLoading] = React.useState(false);

  const confirm = async () => {
    setLoading(true);
    try {
      await onConfirm();
      onOpenChange(false);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{body}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={confirm} disabled={loading}>
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
