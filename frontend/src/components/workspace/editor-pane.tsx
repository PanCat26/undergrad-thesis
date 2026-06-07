"use client";

import * as React from "react";
import { Editor, type Monaco, type OnMount } from "@monaco-editor/react";
import { Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ProjectFile } from "@/lib/types";

interface EditorPaneProps {
  file: ProjectFile | null;
  content: string;
  dirty: boolean;
  saving: boolean;
  onChange: (value: string) => void;
  onSave: () => void;
}

function languageForPath(path: string): string {
  return /\.(tex|sty|cls)$/i.test(path) ? "latex" : "plaintext";
}

let latexRegistered = false;

function registerLatex(monaco: Monaco) {
  if (latexRegistered) return;
  latexRegistered = true;
  monaco.languages.register({ id: "latex" });
  monaco.languages.setMonarchTokensProvider("latex", {
    tokenizer: {
      root: [
        [/%.*$/, "comment"],
        [/\\[a-zA-Z@]+/, "keyword"],
        [/\\[^a-zA-Z]/, "keyword"],
        [/[{}[\]]/, "delimiter.bracket"],
        [/\$[^$]*\$/, "string"],
      ],
    },
  });
}

export function EditorPane({ file, content, dirty, saving, onChange, onSave }: EditorPaneProps) {
  const onSaveRef = React.useRef(onSave);
  onSaveRef.current = onSave;

  const handleMount: OnMount = (editor, monaco) => {
    registerLatex(monaco);
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => onSaveRef.current());
  };

  if (!file) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
        Select a file to edit
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-9 shrink-0 items-center justify-between border-b px-3 text-sm">
        <span className="flex items-center gap-1.5 truncate">
          {file.path}
          {dirty && (
            <span
              className="h-1.5 w-1.5 rounded-full bg-muted-foreground"
              aria-label="Unsaved changes"
            />
          )}
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="h-7"
          onClick={onSave}
          disabled={!dirty || saving}
        >
          {saving ? <Loader2 className="animate-spin" /> : <Save />}
          Save
        </Button>
      </div>
      <div className="min-h-0 flex-1">
        <Editor
          key={file.id}
          height="100%"
          language={languageForPath(file.path)}
          value={content}
          onChange={(value) => onChange(value ?? "")}
          onMount={handleMount}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            wordWrap: "on",
            scrollBeyondLastLine: false,
            automaticLayout: true,
          }}
        />
      </div>
    </div>
  );
}
