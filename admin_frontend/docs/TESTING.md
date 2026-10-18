# Testing Guide

This document provides information about testing in the Admin Frontend application.

## Overview

The application uses Jest and React Testing Library for unit and component testing. Tests are located alongside the code they test in `__tests__` directories.

## Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage
```

## Test Structure

Tests are organized as follows:

```
hooks/
  __tests__/
    use-workspaces.test.ts
    use-workspace.test.ts
    use-users.test.ts
components/
  __tests__/
    workspace-table.test.tsx
    error-boundary.test.tsx
    suspend-workspace-modal.test.tsx
```

## Writing Tests

### Testing Hooks

Hooks are tested using `renderHook` from `@testing-library/react`. The test utilities automatically wrap hooks with React Query providers.

Example:

```typescript
import { renderHook, waitFor } from "@testing-library/react";
import { useWorkspaces } from "../use-workspaces";

describe("useWorkspaces", () => {
  it("should fetch workspaces", async () => {
    const { result } = renderHook(() => useWorkspaces(), {
      wrapper: createWrapper(), // Provides React Query context
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toBeDefined();
  });
});
```

### Testing Components

Components are tested using `render` from `@testing-library/react`. The test utilities provide React Query context automatically.

Example:

```typescript
import { render, screen } from "@testing-library/react";
import { WorkspaceTable } from "../admin/workspace-table";

describe("WorkspaceTable", () => {
  it("should render workspaces", () => {
    render(<WorkspaceTable workspaces={mockWorkspaces} />);
    expect(screen.getByText("Workspace 1")).toBeInTheDocument();
  });
});
```

### Mocking API Calls

API calls are mocked using Jest's `jest.mock()`:

```typescript
jest.mock("@/lib/api-client", () => ({
  get: jest.fn(),
}));

const mockGet = apiClient.get as jest.MockedFunction<typeof apiClient.get>;

beforeEach(() => {
  mockGet.mockResolvedValue(mockData);
});
```

## Test Utilities

The `tests/utils.tsx` file provides:

- `render()` - Custom render function with React Query provider
- `createWrapper()` - Creates a test QueryClient wrapper
- `mockApiClient` - Mock API client utilities

## Coverage Requirements

- **Target:** 60%+ coverage for critical paths
- **Critical paths include:**
  - Hooks (data fetching and mutations)
  - Components (user interactions, form validation)
  - Error handling (error boundaries, API errors)

## Best Practices

1. **Test user behavior, not implementation details**

   - Focus on what users see and interact with
   - Avoid testing internal state or implementation

2. **Use descriptive test names**

   - Test names should describe what is being tested
   - Example: "should display error message when API call fails"

3. **Keep tests isolated**

   - Each test should be independent
   - Use `beforeEach` to reset mocks and state

4. **Test error scenarios**

   - Test both success and failure cases
   - Test edge cases (empty data, loading states, etc.)

5. **Mock external dependencies**
   - Mock API calls, external libraries, and browser APIs
   - Keep mocks simple and focused

## Common Patterns

### Testing Async Operations

```typescript
it("should handle async data fetching", async () => {
  const { result } = renderHook(() => useWorkspaces());

  expect(result.current.isLoading).toBe(true);

  await waitFor(() => {
    expect(result.current.isLoading).toBe(false);
  });

  expect(result.current.data).toBeDefined();
});
```

### Testing User Interactions

```typescript
import userEvent from "@testing-library/user-event";

it("should submit form on button click", async () => {
  const user = userEvent.setup();
  const onSubmit = jest.fn();

  render(<Form onSubmit={onSubmit} />);

  await user.type(screen.getByLabelText("Name"), "Test");
  await user.click(screen.getByText("Submit"));

  expect(onSubmit).toHaveBeenCalledWith({ name: "Test" });
});
```

### Testing Error States

```typescript
it("should display error message on API failure", async () => {
  mockGet.mockRejectedValue(new Error("API Error"));

  const { result } = renderHook(() => useWorkspaces());

  await waitFor(() => {
    expect(result.current.isError).toBe(true);
  });

  expect(result.current.error).toBeDefined();
});
```

## Debugging Tests

- Use `screen.debug()` to see the rendered output
- Use `console.log(result.current)` to inspect hook state
- Use `--verbose` flag for detailed test output: `npm test -- --verbose`

## Continuous Integration

Tests should pass before merging code. The CI pipeline runs:

```bash
npm test -- --coverage --watchAll=false
```

## Resources

- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/)
- [React Query Testing](https://tanstack.com/query/latest/docs/react/guides/testing)
