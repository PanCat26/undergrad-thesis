import { AppHeader } from "@/components/app-header";
import { AuthGuard } from "@/components/auth-guard";
import { ProjectsView } from "@/components/projects/projects-view";

export default function ProjectsPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-col">
        <AppHeader />
        <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-8">
          <ProjectsView />
        </main>
      </div>
    </AuthGuard>
  );
}
