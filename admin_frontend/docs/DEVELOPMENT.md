# Development Guide

This guide provides detailed instructions for developing the DocFoundry Admin App.

## Project Status

**Current Phase:** Phase 1 (Foundation) - ✅ **COMPLETED**

**Completed Features:**

- ✅ Project setup and configuration
- ✅ Authentication system with admin role verification
- ✅ API client with error handling
- ✅ Layout components (header, sidebar, admin layout)
- ✅ Dashboard homepage with metrics and workspace overview
- ✅ Route protection via middleware
- ✅ Shared UI components (shadcn/ui)

**Next Phase:** Phase 2 (Core Features)

- Workspace management (list, detail, suspend, analytics)
- User management
- Affiliate management

## Table of Contents

- [Local Setup](#local-setup)
- [Development Workflow](#development-workflow)
- [Code Style Guidelines](#code-style-guidelines)
- [Common Patterns](#common-patterns)
- [Testing](#testing)
- [Debugging](#debugging)
- [Troubleshooting](#troubleshooting)

## Local Setup

### Prerequisites

- Node.js 18+ installed
- npm/yarn/pnpm installed
- Backend API running on port 8000
- Git installed

### Initial Setup

1. **Clone Repository**

   ```bash
   git clone <repository-url>
   cd generated_apps/docdata_saas/admin_frontend
   ```

2. **Install Dependencies**

   ```bash
   npm install
   ```

3. **Configure Environment**

   ```bash
   cp .env.example .env.local  # If .env.example exists
   # Or create .env.local manually
   ```

4. **Start Development Server**

   ```bash
   npm run dev
   ```

5. **Access Application**
   - Open `http://localhost:3001`
   - Log in with admin credentials

## Development Workflow

### Starting Development

1. **Start Backend** (in separate terminal):

   ```bash
   cd ../backend
   python -m uvicorn app.main:app --reload
   ```

2. **Start Admin App**:

   ```bash
   npm run dev
   ```

3. **Make Changes**:
   - Edit files in `app/`, `components/`, `lib/`, etc.
   - Next.js hot reloads automatically
   - Check browser console for errors

### File Organization

- **New Pages**: Add to `app/[route]/page.tsx`
- **New Components**: Add to `components/[category]/[component].tsx`
- **New Hooks**: Add to `hooks/use-[name].ts`
- **New Utilities**: Add to `lib/[name].ts`

### Git Workflow

1. **Create Feature Branch**:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**:

   - Write code
   - Test locally
   - Commit with clear messages

3. **Commit Messages**:

   ```
   feat(workspaces): add suspend workspace functionality
   fix(auth): handle expired token gracefully
   docs(readme): update setup instructions
   ```

4. **Push and Create PR**:
   ```bash
   git push origin feature/your-feature-name
   # Create pull request
   ```

## Code Style Guidelines

### TypeScript

- **Strict Mode**: Always enabled
- **Types**: Define types for all functions and components
- **Avoid `any`**: Use `unknown` or proper types instead
- **Interfaces**: Prefer interfaces over types for object shapes

```typescript
// Good
interface User {
  id: string;
  email: string;
}

function getUser(id: string): Promise<User> {
  // ...
}

// Bad
function getUser(id: any): Promise<any> {
  // ...
}
```

### React Components

- **Functional Components**: Always use functional components
- **Hooks**: Use hooks for state and side effects
- **Props**: Define prop types with TypeScript interfaces

```typescript
// Good
interface ButtonProps {
  label: string;
  onClick: () => void;
  variant?: "default" | "outline";
}

export function Button({ label, onClick, variant = "default" }: ButtonProps) {
  return <button onClick={onClick}>{label}</button>;
}

// Bad
export function Button(props: any) {
  return <button onClick={props.onClick}>{props.label}</button>;
}
```

### Naming Conventions

- **Components**: PascalCase (`UserTable.tsx`)
- **Hooks**: camelCase with `use` prefix (`useAdminAuth.ts`)
- **Utilities**: camelCase (`api-client.ts`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_RETRIES`)
- **Files**: kebab-case for utilities, PascalCase for components

### Import Organization

```typescript
// 1. React/Next.js imports
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

// 2. Third-party imports
import { useQuery } from "@tanstack/react-query";

// 3. Internal imports (components)
import { Button } from "@/components/ui/button";
import { AdminLayout } from "@/components/layout/admin-layout";

// 4. Internal imports (utilities)
import { get } from "@/lib/api-client";
import { useAdminAuthContext } from "@/contexts/admin-auth-context";

// 5. Types
import type { Workspace } from "@/lib/types";
```

## Common Patterns

### API Calls with React Query

```typescript
import { useQuery, useMutation } from "@tanstack/react-query";
import { get, post } from "@/lib/api-client";

// Query pattern
function useWorkspaces() {
  return useQuery({
    queryKey: ["workspaces"],
    queryFn: () => get<Workspace[]>("/api/admin/workspaces"),
    staleTime: 60 * 1000, // 1 minute
  });
}

// Mutation pattern
function useSuspendWorkspace() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      post(`/api/admin/workspaces/${id}/suspend`, { reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspaces"] });
    },
  });
}
```

### Form Handling

```typescript
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function SuspendWorkspaceForm({ workspaceId }: { workspaceId: string }) {
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const suspendMutation = useSuspendWorkspace();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await suspendMutation.mutateAsync({ id: workspaceId, reason });
  };

  return (
    <form onSubmit={handleSubmit}>
      <Input
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Reason for suspension"
        required
      />
      <Button type="submit" isLoading={suspendMutation.isPending}>
        Suspend
      </Button>
    </form>
  );
}
```

### Error Handling

```typescript
import { ApiClientError } from "@/lib/api-client";

try {
  await post("/api/admin/endpoint", data);
} catch (error) {
  if (error instanceof ApiClientError) {
    switch (error.status) {
      case 401:
        // Handle unauthorized
        router.push("/login");
        break;
      case 403:
        // Handle forbidden
        showError("You don't have permission");
        break;
      case 404:
        // Handle not found
        showError("Resource not found");
        break;
      default:
        // Handle other errors
        showError(error.message || "An error occurred");
    }
  } else {
    // Handle unexpected errors
    console.error("Unexpected error:", error);
    showError("An unexpected error occurred");
  }
}
```

### Loading States

```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ["workspaces"],
  queryFn: () => get<Workspace[]>("/api/admin/workspaces"),
});

if (isLoading) {
  return <div>Loading...</div>;
}

if (error) {
  return <div>Error: {error.message}</div>;
}

return <WorkspaceTable workspaces={data} />;
```

## Testing

### Running Tests

```bash
# Unit tests (when added)
npm run test

# E2E tests (when added)
npm run test:e2e

# Coverage
npm run test:coverage
```

### Writing Tests

```typescript
// Example test structure (when test setup is added)
import { render, screen } from "@testing-library/react";
import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("renders correctly", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText("Click me")).toBeInTheDocument();
  });
});
```

## Debugging

### Browser DevTools

- **React DevTools**: Inspect component tree and state
- **Network Tab**: Monitor API calls and responses
- **Console**: Check for errors and warnings
- **Application Tab**: Inspect cookies and localStorage

### VS Code Debugging

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Next.js: debug server-side",
      "type": "node-terminal",
      "request": "launch",
      "command": "npm run dev"
    },
    {
      "name": "Next.js: debug client-side",
      "type": "chrome",
      "request": "launch",
      "url": "http://localhost:3001"
    }
  ]
}
```

### Console Logging

```typescript
// Development logging
if (process.env.NODE_ENV === "development") {
  console.log("Debug info:", data);
}

// Error logging
console.error("Error:", error);

// API call logging
console.log("API call started: POST /api/admin/workspaces");
console.info("API call succeeded");
console.warn("API validation error:", error);
```

## Troubleshooting

### Common Issues

#### 1. Hot Reload Not Working

**Solution**:

- Restart development server
- Clear `.next` directory: `rm -rf .next`
- Check for syntax errors in console

#### 2. TypeScript Errors

**Solution**:

- Run type check: `npx tsc --noEmit`
- Check `tsconfig.json` configuration
- Ensure all imports have proper types

#### 3. Styling Issues

**Solution**:

- Verify Tailwind classes are correct
- Check `tailwind.config.js` includes file paths
- Restart dev server after config changes

#### 4. API Errors

**Solution**:

- Check backend is running
- Verify `NEXT_PUBLIC_API_URL` is correct
- Check CORS configuration on backend
- Inspect network tab for actual error

#### 5. Authentication Issues

**Solution**:

- Check cookies in browser DevTools
- Verify token is being set correctly
- Check middleware is working
- Verify backend auth endpoint

### Getting Help

1. **Check Documentation**:

   - [README.md](../README.md)
   - [ARCHITECTURE.md](./ARCHITECTURE.md)

2. **Check Logs**:

   - Browser console
   - Terminal output
   - Backend logs

3. **Debug Steps**:
   - Reproduce issue
   - Check error messages
   - Verify configuration
   - Test with minimal example

## Best Practices

1. **Write Clean Code**: Readable, maintainable, well-documented
2. **Handle Errors**: Always handle errors gracefully
3. **Type Everything**: Use TypeScript types everywhere
4. **Test Locally**: Test changes before committing
5. **Follow Patterns**: Use established patterns consistently
6. **Document Changes**: Update docs when adding features
7. **Review Code**: Get code review before merging

## Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [React Query Documentation](https://tanstack.com/query/latest)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [shadcn/ui Components](https://ui.shadcn.com/)
