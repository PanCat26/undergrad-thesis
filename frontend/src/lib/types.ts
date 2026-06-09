export interface Project {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectFile {
  id: string;
  path: string;
  updated_at: string;
}

export interface ProjectFileContent extends ProjectFile {
  content: string;
}

export type SourceStatus = "processing" | "ready" | "failed";

export interface Source {
  id: string;
  filename: string;
  kind: "paper" | "dataset";
  ext: string;
  size_bytes: number;
  status: SourceStatus;
  error: string | null;
  chunk_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface SourcePreview {
  view: "pdf" | "text" | "table" | "json";
  text?: string | null;
  columns?: string[] | null;
  rows?: string[][] | null;
}

export interface ChatSession {
  id: string;
  title: string;
  mode: "qa" | "agentic";
  created_at: string;
  updated_at: string;
}

export interface Citation {
  index: number;
  kind: "source" | "draft";
  filename: string;
  loc: { page?: number };
  source_id: string | null;
  file_id: string | null;
}

export interface ProposedEdit {
  path: string;
  diff: string;
  content: string;
  status: "pending" | "applied" | "rejected";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  created_at: string;
  // Tool-call chain + proposed edits, shown live during streaming (not persisted).
  steps?: string[];
  proposals?: ProposedEdit[];
}
