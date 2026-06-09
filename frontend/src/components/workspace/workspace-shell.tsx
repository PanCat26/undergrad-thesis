"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ImperativePanelGroupHandle } from "react-resizable-panels";

import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { Tooltip } from "@/components/ui/tooltip";
import { AssistantPanel } from "@/components/workspace/assistant-panel";
import { EditorPane } from "@/components/workspace/editor-pane";
import { FileTree } from "@/components/workspace/file-tree";
import { PdfPreview } from "@/components/workspace/pdf-preview";
import { SourcesPanel } from "@/components/workspace/sources-panel";
import { SourceViewer } from "@/components/workspace/source-viewer";
import { ApiError, getErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Project, ProjectFile, ProjectFileContent, Source } from "@/lib/types";

const OUTER_LAYOUT = [22, 53, 25];
const COLUMN_LAYOUT = [55, 45];

export function WorkspaceShell({ projectId }: { projectId: string }) {
  const { request, requestRaw } = useAuth();
  const router = useRouter();

  const [project, setProject] = React.useState<Project | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [files, setFiles] = React.useState<ProjectFile[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [content, setContent] = React.useState("");
  const [baseContent, setBaseContent] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [compiling, setCompiling] = React.useState(false);
  const [pdfUrl, setPdfUrl] = React.useState<string | null>(null);
  const [compileLog, setCompileLog] = React.useState<string | null>(null);
  const [viewingSource, setViewingSource] = React.useState<Source | null>(null);

  const dirty = content !== baseContent;
  const pdfUrlRef = React.useRef<string | null>(null);

  const outerRef = React.useRef<ImperativePanelGroupHandle>(null);
  const leftColRef = React.useRef<ImperativePanelGroupHandle>(null);
  const centerColRef = React.useRef<ImperativePanelGroupHandle>(null);

  const base = `/api/projects/${projectId}`;

  const openFile = React.useCallback(
    async (fileId: string) => {
      const file = await request<ProjectFileContent>(`${base}/files/${fileId}`);
      setSelectedId(file.id);
      setContent(file.content);
      setBaseContent(file.content);
    },
    [base, request]
  );

  // Initial load: project metadata + file list, then open main.tex.
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const proj = await request<Project>(base);
        if (cancelled) return;
        setProject(proj);
        const list = await request<ProjectFile[]>(`${base}/files`);
        if (cancelled) return;
        setFiles(list);
        const first = list.find((f) => f.path === "main.tex") ?? list[0];
        if (first) await openFile(first.id);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          router.replace("/projects");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Failed to load project");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [base, request, openFile, router]);

  React.useEffect(() => {
    return () => {
      if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current);
    };
  }, []);

  const saveCurrent = async () => {
    if (!selectedId || !dirty) return;
    const saved = content;
    await request(`${base}/files/${selectedId}`, { method: "PUT", body: { content: saved } });
    setBaseContent(saved);
  };

  const handleSave = async () => {
    if (!selectedId || !dirty) return;
    setSaving(true);
    try {
      await saveCurrent();
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to save"));
    } finally {
      setSaving(false);
    }
  };

  const handleSelect = async (file: ProjectFile) => {
    if (file.id === selectedId) return;
    try {
      await saveCurrent();
      await openFile(file.id);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const refreshFiles = async (): Promise<ProjectFile[]> => {
    const list = await request<ProjectFile[]>(`${base}/files`);
    setFiles(list);
    return list;
  };

  const handleCreate = async (path: string) => {
    const file = await request<ProjectFileContent>(`${base}/files`, {
      method: "POST",
      body: { path },
    });
    await refreshFiles();
    await openFile(file.id);
  };

  const handleRename = async (file: ProjectFile, path: string) => {
    await request(`${base}/files/${file.id}`, { method: "PATCH", body: { path } });
    await refreshFiles();
  };

  const handleDelete = async (file: ProjectFile) => {
    await request(`${base}/files/${file.id}`, { method: "DELETE" });
    const list = await refreshFiles();
    if (selectedId === file.id) {
      const next = list[0];
      if (next) {
        await openFile(next.id);
      } else {
        setSelectedId(null);
        setContent("");
        setBaseContent("");
      }
    }
  };

  const handleDeleteFolder = async (prefix: string) => {
    const inFolder = files.filter((f) => f.path.startsWith(`${prefix}/`));
    for (const f of inFolder) {
      await request(`${base}/files/${f.id}`, { method: "DELETE" });
    }
    const list = await refreshFiles();
    if (inFolder.some((f) => f.id === selectedId)) {
      const next = list[0];
      if (next) {
        await openFile(next.id);
      } else {
        setSelectedId(null);
        setContent("");
        setBaseContent("");
      }
    }
  };

  const handleCompile = async () => {
    setCompiling(true);
    try {
      if (dirty) await saveCurrent();
      const resp = await requestRaw(`${base}/compile`, { method: "POST" });
      if (resp.ok) {
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current);
        pdfUrlRef.current = url;
        setPdfUrl(url);
        setCompileLog(null);
      } else {
        let message = "Compilation failed";
        let detail = "";
        try {
          const body = await resp.json();
          message = body?.error?.message ?? message;
          detail = typeof body?.error?.detail === "string" ? body.error.detail : "";
        } catch {
          // non-JSON error body; fall back to the generic message
        }
        setCompileLog(detail || message);
        toast.error(message);
      }
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to compile"));
    } finally {
      setCompiling(false);
    }
  };

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        {error}
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const handleViewSourceById = async (sourceId: string) => {
    try {
      const source = await request<Source>(`${base}/sources/${sourceId}`);
      setViewingSource(source);
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to open source"));
    }
  };

  const handleOpenFileByPath = (path: string) => {
    const file = files.find((f) => f.path === path);
    if (!file) return;
    setViewingSource(null);
    void handleSelect(file);
  };

  const handleEditApplied = async (path: string) => {
    try {
      const list = await request<ProjectFile[]>(`${base}/files`);
      setFiles(list);
      const target = list.find((f) => f.path === path);
      if (target && target.id === selectedId) {
        const fresh = await request<ProjectFileContent>(`${base}/files/${target.id}`);
        setContent(fresh.content);
        setBaseContent(fresh.content);
      }
    } catch {
      // best effort; the file was written regardless
    }
  };

  const selectedFile = files.find((f) => f.id === selectedId) ?? null;

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex h-10 shrink-0 items-center gap-2 border-b px-3 text-sm">
        <Tooltip label="Back">
          <Button variant="ghost" size="icon" className="h-7 w-7" asChild aria-label="Back to projects">
            <Link href="/projects">
              <ArrowLeft />
            </Link>
          </Button>
        </Tooltip>
        <span className="font-medium">{project.name}</span>
      </div>
      <ResizablePanelGroup ref={outerRef} direction="horizontal" className="flex-1">
        <ResizablePanel defaultSize={OUTER_LAYOUT[0]} minSize={15}>
          <ResizablePanelGroup ref={leftColRef} direction="vertical">
            <ResizablePanel defaultSize={COLUMN_LAYOUT[0]} minSize={20}>
              <FileTree
                files={files}
                selectedId={selectedId}
                onSelect={handleSelect}
                onCreate={handleCreate}
                onRename={handleRename}
                onDelete={handleDelete}
                onDeleteFolder={handleDeleteFolder}
              />
            </ResizablePanel>
            <ResizableHandle withHandle onDoubleClick={() => leftColRef.current?.setLayout(COLUMN_LAYOUT)} />
            <ResizablePanel defaultSize={COLUMN_LAYOUT[1]} minSize={20}>
              <SourcesPanel
                projectId={projectId}
                viewingSourceId={viewingSource?.id ?? null}
                onView={setViewingSource}
                onSourceDeleted={(id) =>
                  setViewingSource((cur) => (cur?.id === id ? null : cur))
                }
              />
            </ResizablePanel>
          </ResizablePanelGroup>
        </ResizablePanel>

        <ResizableHandle withHandle onDoubleClick={() => outerRef.current?.setLayout(OUTER_LAYOUT)} />

        <ResizablePanel defaultSize={OUTER_LAYOUT[1]} minSize={30}>
          {viewingSource ? (
            <SourceViewer
              projectId={projectId}
              source={viewingSource}
              onClose={() => setViewingSource(null)}
            />
          ) : (
            <ResizablePanelGroup ref={centerColRef} direction="vertical">
              <ResizablePanel defaultSize={COLUMN_LAYOUT[0]} minSize={20}>
                <EditorPane
                  file={selectedFile}
                  content={content}
                  dirty={dirty}
                  saving={saving}
                  onChange={setContent}
                  onSave={handleSave}
                />
              </ResizablePanel>
              <ResizableHandle withHandle onDoubleClick={() => centerColRef.current?.setLayout(COLUMN_LAYOUT)} />
              <ResizablePanel defaultSize={COLUMN_LAYOUT[1]} minSize={20}>
                <PdfPreview
                  pdfUrl={pdfUrl}
                  compileLog={compileLog}
                  compiling={compiling}
                  onCompile={handleCompile}
                />
              </ResizablePanel>
            </ResizablePanelGroup>
          )}
        </ResizablePanel>

        <ResizableHandle withHandle onDoubleClick={() => outerRef.current?.setLayout(OUTER_LAYOUT)} />

        <ResizablePanel defaultSize={OUTER_LAYOUT[2]} minSize={18}>
          <AssistantPanel
            projectId={projectId}
            onViewSource={handleViewSourceById}
            onOpenFile={handleOpenFileByPath}
            onEditApplied={handleEditApplied}
          />
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
