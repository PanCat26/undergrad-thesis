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
