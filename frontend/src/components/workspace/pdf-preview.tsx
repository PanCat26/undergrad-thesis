"use client";

import { Loader2, Play } from "lucide-react";

import { Button } from "@/components/ui/button";

interface PdfPreviewProps {
  pdfUrl: string | null;
  compileLog: string | null;
  compiling: boolean;
  onCompile: () => void;
}

export function PdfPreview({ pdfUrl, compileLog, compiling, onCompile }: PdfPreviewProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-9 shrink-0 items-center justify-between border-b px-3">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Preview
        </span>
        <Button size="sm" className="h-7" onClick={onCompile} disabled={compiling}>
          {compiling ? <Loader2 className="animate-spin" /> : <Play />}
          Compile
        </Button>
      </div>
      <div className="min-h-0 flex-1">
        {compileLog ? (
          <pre className="h-full overflow-auto whitespace-pre-wrap p-3 text-xs text-destructive">
            {compileLog}
          </pre>
        ) : pdfUrl ? (
          <iframe title="Compiled PDF" src={pdfUrl} className="h-full w-full border-0" />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
            Compile to see the PDF
          </div>
        )}
      </div>
    </div>
  );
}
