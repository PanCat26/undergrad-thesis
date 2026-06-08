"use client";

import * as React from "react";
import { X } from "lucide-react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { getErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Source, SourcePreview } from "@/lib/types";

interface SourceViewerProps {
  projectId: string;
  source: Source;
  onClose: () => void;
}

export function SourceViewer({ projectId, source, onClose }: SourceViewerProps) {
  const { request, requestRaw } = useAuth();
  const base = `/api/projects/${projectId}/sources/${source.id}`;

  const [preview, setPreview] = React.useState<SourcePreview | null>(null);
  const [pdfUrl, setPdfUrl] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const pdfUrlRef = React.useRef<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setPreview(null);
    setError(null);
    (async () => {
      try {
        const result = await request<SourcePreview>(`${base}/preview`);
        if (cancelled) return;
        setPreview(result);
        if (result.view === "pdf") {
          const resp = await requestRaw(`${base}/file`);
          const blob = await resp.blob();
          if (cancelled) return;
          const url = URL.createObjectURL(blob);
          if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current);
          pdfUrlRef.current = url;
          setPdfUrl(url);
        }
      } catch (err) {
        if (!cancelled) setError(getErrorMessage(err, "Failed to open source"));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [base, request, requestRaw]);

  React.useEffect(() => {
    return () => {
      if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current);
    };
  }, []);

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-9 shrink-0 items-center justify-between border-b px-3 text-sm">
        <span className="truncate font-medium">{source.filename}</span>
        <Tooltip label="Close">
          <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="Close source" onClick={onClose}>
            <X />
          </Button>
        </Tooltip>
      </div>
      <div className="min-h-0 flex-1">
        {error ? (
          <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
            {error}
          </div>
        ) : !preview ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : preview.view === "pdf" ? (
          pdfUrl ? (
            <iframe title={source.filename} src={pdfUrl} className="h-full w-full border-0" />
          ) : (
            <div className="flex h-full items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )
        ) : preview.view === "table" ? (
          <TableView columns={preview.columns ?? []} rows={preview.rows ?? []} />
        ) : (
          <pre className="h-full overflow-auto whitespace-pre-wrap p-3 text-xs">{preview.text}</pre>
        )}
      </div>
    </div>
  );
}

function TableView({ columns, rows }: { columns: string[]; rows: string[][] }) {
  return (
    <div className="h-full overflow-auto">
      <table className="w-full border-collapse text-xs">
        <thead className="sticky top-0 bg-muted">
          <tr>
            {columns.map((col, i) => (
              <th key={i} className="border-b px-2 py-1 text-left font-medium">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r} className="hover:bg-accent">
              {row.map((cell, c) => (
                <td key={c} className="border-b px-2 py-1">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
