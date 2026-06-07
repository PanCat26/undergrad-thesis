"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Loader2, MoreVertical, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { RenameProjectDialog } from "@/components/projects/rename-project-dialog";
import { DeleteProjectDialog } from "@/components/projects/delete-project-dialog";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Project } from "@/lib/types";

export function ProjectsView() {
  const { request } = useAuth();
  const router = useRouter();

  const [projects, setProjects] = React.useState<Project[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [renaming, setRenaming] = React.useState<Project | null>(null);
  const [deleting, setDeleting] = React.useState<Project | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProjects(await request<Project[]>("/api/projects"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }, [request]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const handleCreate = async (name: string) => {
    const project = await request<Project>("/api/projects", { method: "POST", body: { name } });
    setProjects((prev) => [project, ...prev]);
    toast.success("Project created");
    router.push(`/projects/${project.id}`);
  };

  const handleRename = async (name: string) => {
    if (!renaming) return;
    const updated = await request<Project>(`/api/projects/${renaming.id}`, {
      method: "PATCH",
      body: { name },
    });
    setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    toast.success("Project renamed");
    setRenaming(null);
  };

  const handleDelete = async () => {
    if (!deleting) return;
    await request(`/api/projects/${deleting.id}`, { method: "DELETE" });
    setProjects((prev) => prev.filter((p) => p.id !== deleting.id));
    toast.success("Project deleted");
    setDeleting(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Projects</h1>
        <CreateProjectDialog onCreate={handleCreate}>
          <Button>
            <Plus />
            New project
          </Button>
        </CreateProjectDialog>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button variant="outline" onClick={() => void load()}>
            Try again
          </Button>
        </div>
      ) : projects.length === 0 ? (
        <div className="rounded-lg border border-dashed py-16 text-center">
          <p className="text-sm text-muted-foreground">
            No projects yet. Create your first project to get started.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {projects.map((project) => (
            <li key={project.id}>
              <Card className="flex items-center justify-between p-4">
                <button
                  className="flex-1 text-left"
                  onClick={() => router.push(`/projects/${project.id}`)}
                >
                  <span className="font-medium">{project.name}</span>
                  <span className="block text-xs text-muted-foreground">
                    Updated {new Date(project.updated_at).toLocaleString()}
                  </span>
                </button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" aria-label="Project actions">
                      <MoreVertical />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onSelect={() => setRenaming(project)}>Rename</DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onSelect={() => setDeleting(project)}
                    >
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <RenameProjectDialog
        project={renaming}
        onOpenChange={(open) => !open && setRenaming(null)}
        onRename={handleRename}
      />
      <DeleteProjectDialog
        project={deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        onConfirm={handleDelete}
      />
    </div>
  );
}
