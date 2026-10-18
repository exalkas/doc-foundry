import { WorkspaceProvider } from "@/contexts/workspace-context";
import { AuthProvider } from "@/contexts/auth-context";
import { Header } from "@/components/app/header";
import { Sidebar } from "@/components/app/sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <WorkspaceProvider>
        <div className="min-h-screen bg-background">
          <Header />
          <div className="flex">
            <Sidebar />
            <main className="flex-1 p-6 lg:p-8">{children}</main>
          </div>
        </div>
      </WorkspaceProvider>
    </AuthProvider>
  );
}
