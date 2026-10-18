import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SuspendWorkspaceModal } from "../admin/suspend-workspace-modal";
import * as useWorkspaceHook from "@/hooks/use-workspace";
import * as useToastHook from "@/hooks/use-toast";

// Mock the hooks
jest.mock("@/hooks/use-workspace");
jest.mock("@/hooks/use-toast");

const mockMutateAsync = jest.fn();
const mockToast = jest.fn();

describe("SuspendWorkspaceModal", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useWorkspaceHook.useSuspendWorkspace as jest.Mock) = jest.fn(() => ({
      mutateAsync: mockMutateAsync,
      isPending: false,
    }));
    (useToastHook.useToast as jest.Mock) = jest.fn(() => ({
      toast: mockToast,
    }));
  });

  it("should render modal when open", () => {
    const onOpenChange = jest.fn();
    render(
      <SuspendWorkspaceModal
        workspaceId="workspace-1"
        workspaceName="Test Workspace"
        open={true}
        onOpenChange={onOpenChange}
      />
    );

    expect(
      screen.getByRole("heading", { name: "Suspend Workspace" })
    ).toBeInTheDocument();
    // Check for the description text - it's split across elements, so we check for parts
    expect(screen.getByText(/Suspend the workspace/)).toBeInTheDocument();
    expect(screen.getByText(/Test Workspace/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Reason for suspension/)).toBeInTheDocument();
  });

  it("should not render modal when closed", () => {
    const onOpenChange = jest.fn();
    render(
      <SuspendWorkspaceModal
        workspaceId="workspace-1"
        workspaceName="Test Workspace"
        open={false}
        onOpenChange={onOpenChange}
      />
    );

    expect(screen.queryByText("Suspend Workspace")).not.toBeInTheDocument();
  });

  it("should validate minimum character length", async () => {
    const user = userEvent.setup();
    const onOpenChange = jest.fn();

    render(
      <SuspendWorkspaceModal
        workspaceId="workspace-1"
        workspaceName="Test Workspace"
        open={true}
        onOpenChange={onOpenChange}
      />
    );

    const textarea = screen.getByLabelText(/Reason for suspension/);
    const submitButton = screen.getByRole("button", {
      name: "Suspend Workspace",
    });

    // Enter text less than 20 characters
    await user.type(textarea, "Short reason");
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith({
        title: "Invalid reason",
        description: "Please provide a reason with at least 20 characters",
        variant: "destructive",
      });
    });

    expect(mockMutateAsync).not.toHaveBeenCalled();
  });

  it("should submit form with valid reason", async () => {
    const user = userEvent.setup();
    const onOpenChange = jest.fn();
    mockMutateAsync.mockResolvedValue({});

    render(
      <SuspendWorkspaceModal
        workspaceId="workspace-1"
        workspaceName="Test Workspace"
        open={true}
        onOpenChange={onOpenChange}
      />
    );

    const textarea = screen.getByLabelText(/Reason for suspension/);
    const submitButton = screen.getByRole("button", {
      name: "Suspend Workspace",
    });

    // Enter valid reason (at least 20 characters)
    await user.type(
      textarea,
      "This is a valid reason for suspending the workspace that meets the minimum length requirement"
    );
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        id: "workspace-1",
        reason: expect.stringMatching(/This is a valid reason/),
      });
    });

    expect(mockToast).toHaveBeenCalledWith({
      title: "Workspace suspended",
      description: "Test Workspace has been suspended successfully",
      variant: "success",
    });

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("should handle submission errors", async () => {
    const user = userEvent.setup();
    const onOpenChange = jest.fn();
    const error = { status: 500, message: "Server error" };
    mockMutateAsync.mockRejectedValue(error);

    render(
      <SuspendWorkspaceModal
        workspaceId="workspace-1"
        workspaceName="Test Workspace"
        open={true}
        onOpenChange={onOpenChange}
      />
    );

    const textarea = screen.getByLabelText(/Reason for suspension/);
    const submitButton = screen.getByRole("button", {
      name: "Suspend Workspace",
    });

    await user.type(
      textarea,
      "This is a valid reason for suspending the workspace"
    );
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith({
        title: "Failed to suspend workspace",
        description: expect.any(String),
        variant: "destructive",
      });
    });

    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("should reset form when cancel is clicked", async () => {
    const user = userEvent.setup();
    const onOpenChange = jest.fn();

    render(
      <SuspendWorkspaceModal
        workspaceId="workspace-1"
        workspaceName="Test Workspace"
        open={true}
        onOpenChange={onOpenChange}
      />
    );

    const textarea = screen.getByLabelText(/Reason for suspension/);
    const cancelButton = screen.getByText("Cancel");

    await user.type(textarea, "Some reason text");
    await user.click(cancelButton);

    expect(onOpenChange).toHaveBeenCalledWith(false);
    // Form should be reset (textarea should be empty)
    expect((textarea as HTMLTextAreaElement).value).toBe("");
  });

  it("should show character count", async () => {
    const user = userEvent.setup();

    render(
      <SuspendWorkspaceModal
        workspaceId="workspace-1"
        workspaceName="Test Workspace"
        open={true}
        onOpenChange={jest.fn()}
      />
    );

    const textarea = screen.getByLabelText(/Reason for suspension/);

    await user.type(textarea, "Hello");
    expect(screen.getByText("5/20 characters minimum")).toBeInTheDocument();

    await user.type(textarea, " World");
    expect(screen.getByText("11/20 characters minimum")).toBeInTheDocument();
  });

  it("should show loading state when submitting", () => {
    (useWorkspaceHook.useSuspendWorkspace as jest.Mock) = jest.fn(() => ({
      mutateAsync: mockMutateAsync,
      isPending: true,
    }));

    render(
      <SuspendWorkspaceModal
        workspaceId="workspace-1"
        workspaceName="Test Workspace"
        open={true}
        onOpenChange={jest.fn()}
      />
    );

    const submitButton = screen.getByRole("button", {
      name: "Suspend Workspace",
    });
    expect(submitButton).toBeDisabled();
  });
});
