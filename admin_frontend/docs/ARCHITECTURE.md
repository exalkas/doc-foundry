# Admin App Architecture

This document describes the technical architecture, design patterns, and key implementation details of the DocFoundry Admin App.

## Table of Contents

- [Overview](#overview)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Component Architecture](#component-architecture)
- [State Management](#state-management)
- [API Client](#api-client)
- [Authentication Flow](#authentication-flow)
- [Error Handling](#error-handling)
- [Routing](#routing)
- [Styling](#styling)

## Overview

The Admin App is a separate Next.js 14+ application built with:

- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript (strict mode)
- **UI Library**: shadcn/ui (Radix UI primitives)
- **Styling**: Tailwind CSS
- **State Management**: React Query (server state) + React Context (client state)
- **Icons**: Lucide React

### Implementation Status

**Phase 1 (Foundation) - ✅ COMPLETED**

All foundation components have been implemented:

- ✅ Project structure and configuration
- ✅ Authentication system (`AdminAuthProvider`, `useAdminAuth`)
- ✅ API client (`lib/api-client.ts`) with CSRF token handling
- ✅ Layout components (`AdminLayout`, `Header`, `Sidebar`)
- ✅ Dashboard page with workspace overview
- ✅ Route protection middleware
- ✅ Error handling and loading states

**Ready for Phase 2:** Core features (workspace management, user management, affiliate management)

## Technology Stack

### Core Dependencies

- **next**: ^14.0.0 - React framework with App Router
- **react**: ^18.2.0 - UI library
- **typescript**: ^5.3.0 - Type safety
- **@tanstack/react-query**: ^5.0.0 - Server state management
- **tailwindcss**: ^3.4.0 - Utility-first CSS
- **zod**: ^3.22.0 - Schema validation

### UI Components

- **@radix-ui/\*** - Accessible component primitives
- **lucide-react**: ^0.294.0 - Icon library
- **class-variance-authority**: ^0.7.0 - Component variants
- **tailwind-merge**: ^2.0.0 - Tailwind class merging

## Project Structure

```
admin_frontend/
├── app/                    # Next.js App Router
│   ├── layout.tsx         # Root layout with providers
│   ├── page.tsx           # Dashboard homepage
│   ├── error.tsx          # Error page (route-level)
│   ├── providers.tsx      # React Query provider
│   ├── login/             # Login page
│   └── [routes]/          # Feature routes
├── components/
│   ├── ui/               # shadcn/ui components
│   ├── layout/           # Layout components
│   └── error-boundary.tsx # React error boundary
├── contexts/             # React contexts
│   └── admin-auth-context.tsx
├── hooks/               # Custom React hooks
│   └── use-admin-auth.ts
├── lib/                 # Utilities
│   ├── api-client.ts    # API client
│   ├── auth.ts          # Auth utilities
│   ├── types.ts         # TypeScript types
│   └── utils.ts        # Helper functions
└── middleware.ts        # Route protection
```

## Component Architecture

### Component Hierarchy

```
RootLayout
├── ErrorBoundary (global)
│   └── Providers (React Query)
│       └── AdminAuthProvider
│           └── Page Components
│               └── AdminLayout (for authenticated pages)
│                   ├── Header
│                   ├── Sidebar
│                   └── Main Content
```

### Component Types

#### 1. Layout Components

Located in `components/layout/`:

- **AdminLayout**: Main layout wrapper for authenticated pages
- **Header**: Top navigation with user menu
- **Sidebar**: Side navigation with menu items

#### 2. UI Components

Located in `components/ui/`:

- shadcn/ui components (Button, Card, Table, etc.)
- Reusable, accessible components
- Follow Radix UI patterns

#### 3. Feature Components

Located in feature-specific directories:

- Admin-specific components (tables, modals, forms)
- Organized by domain (workspaces, affiliates, etc.)

### Component Patterns

#### Server Components vs Client Components

- **Server Components** (default): Use for static content, data fetching
- **Client Components** (`"use client"`): Use for interactivity, hooks, browser APIs

Example:

```typescript
// Server Component (default)
export default function Page() {
  return <div>Static content</div>;
}

// Client Component
"use client";
export default function InteractiveComponent() {
  const [state, setState] = useState();
  return <button onClick={() => setState(...)}>Click</button>;
}
```

## State Management

### Server State (React Query)

Use React Query for all API calls:

```typescript
import { useQuery, useMutation } from "@tanstack/react-query";
import { get, post } from "@/lib/api-client";

// Query (GET)
const { data, isLoading, error } = useQuery({
  queryKey: ["workspaces"],
  queryFn: () => get<Workspace[]>("/api/admin/workspaces"),
});

// Mutation (POST/PUT/DELETE)
const mutation = useMutation({
  mutationFn: (data) => post("/api/admin/workspaces/123/suspend", data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["workspaces"] });
  },
});
```

**Benefits**:

- Automatic caching
- Background refetching
- Optimistic updates
- Error handling

### Client State (React Context)

Use Context for:

- Authentication state (`AdminAuthContext`)
- UI state (theme, sidebar open/closed)

Example:

```typescript
const { user, loading, logout } = useAdminAuthContext();
```

### Local State (useState)

Use `useState` for:

- Form inputs
- Component-specific UI state
- Temporary state

## API Client

Located in `lib/api-client.ts`.

### Features

- **Automatic Auth**: Includes JWT token in headers
- **CSRF Protection**: Fetches and includes CSRF token for mutations
- **Error Handling**: Consistent error format
- **Request Timeout**: 30-second timeout
- **Cookie Support**: Includes credentials for cookie-based auth

### Usage

```typescript
import { get, post, put, del } from "@/lib/api-client";

// GET request
const workspaces = await get<Workspace[]>("/api/admin/workspaces");

// POST request
const result = await post("/api/admin/workspaces/123/suspend", {
  reason: "Payment issue",
});

// Error handling
try {
  await post("/api/admin/endpoint", data);
} catch (error) {
  if (error instanceof ApiClientError) {
    console.error(error.message, error.status);
  }
}
```

### Error Types

```typescript
class ApiClientError extends Error {
  status?: number;
  code?: string;
  details?: any;
}
```

## Authentication Flow

### 1. Login Process

```
User enters credentials
  ↓
POST /api/auth/login
  ↓
Backend validates and returns JWT token
  ↓
Token stored in cookie (via setAuthToken)
  ↓
Redirect to dashboard (or redirect parameter)
```

### 2. Route Protection

**Middleware** (`middleware.ts`):

- Checks for `auth_token` cookie
- Decodes JWT to verify admin role
- Redirects to `/login` if not authenticated or not admin

**Auth Context** (`AdminAuthContext`):

- Fetches current user from `/api/auth/me`
- Verifies admin role
- Provides user state throughout app

### 3. Token Management

- **Storage**: Cookie (httpOnly-like, client-side)
- **Expiration**: Handled by backend
- **Refresh**: Not implemented (tokens are long-lived)
- **Logout**: Clears cookie and redirects to login

### Implementation

```typescript
// Login
const response = await post("/api/auth/login", { email, password });
setAuthToken(response.token);

// Check auth
const token = getAuthToken();
if (!token) redirectToLogin();

// Logout
removeAuthToken();
router.push("/login");
```

## Error Handling

### Error Boundaries

**Global Error Boundary** (`components/error-boundary.tsx`):

- Catches React component errors
- Displays user-friendly error UI
- Provides retry functionality
- Logs errors for debugging

**Route Error Page** (`app/error.tsx`):

- Handles errors in page components
- Next.js App Router error handling
- Provides reset functionality

### Error Handling Patterns

#### API Errors

```typescript
try {
  await post("/api/admin/endpoint", data);
} catch (error) {
  if (error instanceof ApiClientError) {
    if (error.status === 401) {
      // Redirect to login
    } else if (error.status === 403) {
      // Show permission denied
    } else {
      // Show generic error
    }
  }
}
```

#### Component Errors

```typescript
// Wrapped in ErrorBoundary automatically
<ErrorBoundary>
  <ComponentThatMightError />
</ErrorBoundary>
```

### Error Logging

- **Development**: Full error details in console
- **Production**: Errors logged to console (can integrate Sentry)

## Routing

### Route Structure

```
/                    → Dashboard
/login              → Login page
/workspaces         → Workspace list
/workspaces/[id]    → Workspace detail
/users              → User list
/affiliates         → Affiliate list
...
```

### Route Protection

All routes except `/login` are protected by:

1. **Middleware**: Checks authentication and admin role
2. **Auth Context**: Verifies user on mount
3. **Backend**: Validates on every API call

### Navigation

Use Next.js `Link` component or `useRouter`:

```typescript
import Link from "next/link";
import { useRouter } from "next/navigation";

// Link component
<Link href="/workspaces">Workspaces</Link>;

// Programmatic navigation
const router = useRouter();
router.push("/workspaces");
```

## Styling

### Tailwind CSS

- **Utility-first**: Use Tailwind utility classes
- **Dark Mode**: Class-based dark mode (`dark:` variant)
- **Responsive**: Mobile-first breakpoints (`sm:`, `md:`, `lg:`)

### Component Styling

```typescript
// Tailwind utilities
<div className="flex items-center gap-2 p-4 bg-white dark:bg-slate-800">

// Component variants (using CVA)
<Button variant="default" size="sm">
```

### Theme Configuration

Configured in `tailwind.config.js`:

- Custom colors (primary, secondary, accent)
- Custom spacing and typography
- Dark mode support

### CSS Variables

Used for theme colors (defined in `globals.css`):

- `--primary`, `--secondary`, `--accent`
- `--background`, `--foreground`
- `--border`, `--muted`

## Best Practices

### 1. Type Safety

- Always use TypeScript types
- Avoid `any` type
- Define interfaces for API responses

### 2. Component Composition

- Keep components small and focused
- Compose complex components from simple ones
- Use props for configuration

### 3. Error Handling

- Always handle errors gracefully
- Provide user-friendly error messages
- Log errors for debugging

### 4. Performance

- Use React Query caching
- Lazy load heavy components
- Optimize images with Next.js Image

### 5. Accessibility

- Use semantic HTML
- Include ARIA labels where needed
- Ensure keyboard navigation works
- Test with screen readers

## Future Enhancements

- **Testing**: Add unit and integration tests
- **Error Tracking**: Integrate Sentry or similar
- **Real-time Updates**: WebSocket for live metrics
- **Advanced Filtering**: Complex filter builder
- **Bulk Actions**: Multi-select operations
- **Export**: CSV/Excel export functionality
