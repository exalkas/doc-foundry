import { render, screen } from "@testing-library/react";
import { WorkspaceTable } from "../admin/workspace-table";
import type { Workspace } from "@/lib/types";

const mockWorkspaces: Workspace[] = [
  {
    id: "1",
    name: "Test Workspace 1",
    owner_email: "owner1@example.com",
    plan: "pro",
    status: "active",
    created_at: "2024-01-01T00:00:00Z",
  },
  {
    id: "2",
    name: "Test Workspace 2",
    owner_email: "owner2@example.com",
    plan: "basic",
    status: "suspended",
    created_at: "2024-01-02T00:00:00Z",
  },
];

describe("WorkspaceTable", () => {
  it("should render loading state", () => {
    render(<WorkspaceTable workspaces={[]} isLoading={true} />);
    expect(screen.getByText("Loading workspaces...")).toBeInTheDocument();
  });

  it("should render empty state", () => {
    render(<WorkspaceTable workspaces={[]} isLoading={false} />);
    expect(screen.getByText("No workspaces found")).toBeInTheDocument();
  });

  it("should render workspaces table", () => {
    render(<WorkspaceTable workspaces={mockWorkspaces} isLoading={false} />);

    expect(screen.getByText("Test Workspace 1")).toBeInTheDocument();
    expect(screen.getByText("Test Workspace 2")).toBeInTheDocument();
    expect(screen.getByText("owner1@example.com")).toBeInTheDocument();
    expect(screen.getByText("owner2@example.com")).toBeInTheDocument();
    expect(screen.getByText("pro")).toBeInTheDocument();
    expect(screen.getByText("basic")).toBeInTheDocument();
  });

  it("should render workspace status badges", () => {
    render(<WorkspaceTable workspaces={mockWorkspaces} isLoading={false} />);

    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("suspended")).toBeInTheDocument();
  });

  it("should render view buttons", () => {
    render(<WorkspaceTable workspaces={mockWorkspaces} isLoading={false} />);

    const viewButtons = screen.getAllByText("View");
    expect(viewButtons).toHaveLength(2);
  });

  it("should handle missing optional fields", () => {
    const workspaceWithoutOptional: Workspace = {
      id: "3",
      name: "Workspace Without Optional",
      status: "active",
      created_at: "2024-01-03T00:00:00Z",
    };

    render(
      <WorkspaceTable
        workspaces={[workspaceWithoutOptional]}
        isLoading={false}
      />
    );

    expect(screen.getByText("Workspace Without Optional")).toBeInTheDocument();
    // Should show "-" for missing owner_email and plan
    const cells = screen.getAllByText("-");
    expect(cells.length).toBeGreaterThan(0);
  });
});
