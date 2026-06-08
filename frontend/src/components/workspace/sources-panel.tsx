"use client";

import * as React from "react";
import { toast } from "sonner";
import {
  AlertCircle,
  FileText,
  Loader2,
  MoreVertical,
  Table2,
  Upload,
} from "lucide-react";

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
import { getErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import type { Source } from "@/lib/types";

const ACCEPT = ".pdf,.docx,.tex,.csv,.json";

interface SourcesPanelProps {
  projectId: string;
  viewingSourceId: string | null;
  onView: (source: Source) => void;
  onSourceDeleted: (id: string) => void;
}

export function SourcesPanel({
  projectId,
  viewingSourceId,
  onView,
  onSourceDeleted,
}: SourcesPanelProps) {
  const { request, upload } = useAuth();
  const base = `/api/projects/${projectId}/sources`;

  const [sources, setSources] = React.useState<Source[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [uploading, setUploading] = React.useState(false);
  const [deleting, setDeleting] = React.useState<Source | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const load = React.useCallback(async () => {
    try {
      setSources(await request<Source[]>(base));
    } catch {
      // keep the previous list on transient errors
    } finally {
      setLoading(false);
    }
  }, [base, request]);

  React.useEffect(() => {
    void load();
  }, [load]);

  // Poll while any source is still being ingested.
  React.useEffect(() => {
    if (!sources.some((s) => s.status === "processing")) return;
    const timer = setInterval(load, 2500);
    return () => clearInterval(timer);
  }, [sources, load]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const created = await upload<Source>(base, form);
      setSources((prev) => [created, ...prev]);
      toast.success("Upload started");
    } catch (err) {
      toast.error(getErrorMessage(err, "Upload failed"));
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async () => {
    if (!deleting) return;
    await request(`${base}/${deleting.id}`, { method: "DELETE" });
    setSources((prev) => prev.filter((s) => s.id !== deleting.id));
    onSourceDeleted(deleting.id);
    toast.success("Source deleted");
    setDeleting(null);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between border-b px-3 py-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Sources
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          aria-label="Upload source"
          disabled={uploading}
          onClick={() => fileInputRef.current?.click()}
        >
          {uploading ? <Loader2 className="animate-spin" /> : <Upload />}
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleUpload(file);
            e.target.value = "";
          }}
        />
      </div>

      <ul className="flex-1 overflow-auto py-1">
        {loading ? (
          <li className="flex justify-center py-6">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          </li>
        ) : sources.length === 0 ? (
          <li className="px-3 py-2 text-xs text-muted-foreground">
            No sources. Upload a paper or dataset.
          </li>
        ) : (
          sources.map((source) => (
            <li key={source.id}>
              <div
                className={cn(
                  "group flex items-center gap-1.5 px-2 py-1 text-sm hover:bg-accent",
                  viewingSourceId === source.id && "bg-accent"
                )}
              >
                <button
                  className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                  onClick={() => onView(source)}
                  disabled={source.status !== "ready" && source.status !== "failed"}
                >
                  {source.kind === "dataset" ? (
                    <Table2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  ) : (
                    <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  )}
                  <span className="truncate">{source.filename}</span>
                </button>
                <StatusBadge source={source} />
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5 opacity-0 group-hover:opacity-100"
                      aria-label="Source actions"
                    >
                      <MoreVertical className="h-3.5 w-3.5" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      disabled={source.status === "processing"}
                      onSelect={() => onView(source)}
                    >
                      View
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onSelect={() => setDeleting(source)}
                    >
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </li>
          ))
        )}
      </ul>

      <DeleteSourceDialog
        source={deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        onConfirm={handleDelete}
      />
    </div>
  );
}

function StatusBadge({ source }: { source: Source }) {
  if (source.status === "processing") {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
      </span>
    );
  }
  if (source.status === "failed") {
    return (
      <span
        className="flex items-center gap-1 text-xs text-destructive"
        title={source.error ?? "Ingestion failed"}
      >
        <AlertCircle className="h-3 w-3" />
      </span>
    );
  }
  return null;
}

function DeleteSourceDialog({
  source,
  onOpenChange,
  onConfirm,
}: {
  source: Source | null;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => Promise<void>;
}) {
  const [loading, setLoading] = React.useState(false);

  const confirm = async () => {
    setLoading(true);
    try {
      await onConfirm();
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to delete source"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={source !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete source</DialogTitle>
          <DialogDescription>
            Permanently delete{" "}
            <span className="font-medium text-foreground">{source?.filename}</span> and its indexed
            content? This cannot be undone.
          </DialogDescription>
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
