import { AppHeader } from "@/components/app-header";
import { AuthGuard } from "@/components/auth-guard";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default async function ProjectWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <AuthGuard>
      <div className="flex h-screen flex-col overflow-hidden">
        <AppHeader />
        <WorkspaceShell projectId={id} />
      </div>
    </AuthGuard>
  );
}
