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
