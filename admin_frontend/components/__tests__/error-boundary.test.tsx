import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ErrorBoundary } from "../error-boundary";

// Component that throws an error
const ThrowError = ({ shouldThrow = false }: { shouldThrow?: boolean }) => {
  if (shouldThrow) {
    throw new Error("Test error");
  }
  return <div>No error</div>;
};

describe("ErrorBoundary", () => {
  beforeEach(() => {
    // Suppress console.error for error boundary tests
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("should render children when there is no error", () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText("No error")).toBeInTheDocument();
  });

  it("should render error UI when error occurs", () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(
      screen.getByText(
        "An unexpected error occurred. Please try again or return to the dashboard."
      )
    ).toBeInTheDocument();
  });

  it("should show error details in development mode", () => {
    const originalEnv = process.env.NODE_ENV;
    // Temporarily override NODE_ENV for this test
    // @ts-expect-error - NODE_ENV is read-only but we need to test development mode
    process.env.NODE_ENV = "development";

    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    // Error details should be visible in development - there are multiple elements with "Error:" text
    const errorElements = screen.getAllByText(/Error:/);
    expect(errorElements.length).toBeGreaterThan(0);

    // @ts-expect-error - Restore original value
    process.env.NODE_ENV = originalEnv;
  });

  it("should call onError callback when error occurs", () => {
    const onError = jest.fn();

    render(
      <ErrorBoundary onError={onError}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(onError).toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({
        componentStack: expect.any(String),
      })
    );
  });

  it("should render custom fallback when provided", () => {
    const customFallback = <div>Custom error message</div>;

    render(
      <ErrorBoundary fallback={customFallback}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText("Custom error message")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });

  it("should reset error state when Try again is clicked", async () => {
    const user = userEvent.setup();

    const { rerender } = render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    // First, rerender with non-throwing children
    rerender(
      <ErrorBoundary>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );

    // The error boundary still shows error UI because it hasn't been reset yet
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    // Now click "Try again" to reset the error boundary state
    const tryAgainButton = screen.getByText("Try again");
    await user.click(tryAgainButton);

    // After clicking reset, the error boundary should render children (which now don't throw)
    await waitFor(() => {
      expect(screen.getByText("No error")).toBeInTheDocument();
    });
  });
});
