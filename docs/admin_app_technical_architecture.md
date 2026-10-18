# Admin App Technical Architecture

**Version:** 1.0  
**Date:** 2024  
**Status:** Draft  
**Project:** DocFoundry Admin Platform

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Decision: Separate App](#architecture-decision-separate-app)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Authentication & Authorization](#authentication--authorization)
6. [State Management](#state-management)
7. [API Client](#api-client)
8. [Routing Structure](#routing-structure)
9. [Component Architecture](#component-architecture)
10. [Shared Code Strategy](#shared-code-strategy)
11. [Deployment Architecture](#deployment-architecture)
12. [Development Workflow](#development-workflow)

---

## Overview

The Admin App is a **separate Next.js application** built specifically for platform administrators. It shares the same backend API as the main user-facing app but has a completely independent frontend codebase optimized for admin workflows.

### Key Principles

1. **Separation**: Complete separation from user-facing app
2. **Shared Backend**: Uses same FastAPI backend (`/api/admin/*` endpoints)
3. **Shared Auth**: Same JWT-based authentication system
4. **Code Reuse**: Shared UI components and utilities where appropriate
5. **Independent Deployment**: Can be deployed separately

---

## Architecture Decision: Separate App

### Why Separate App?

**Benefits:**

- **Security**: Admin code isolated from user-facing code
- **Performance**: Smaller bundle size for regular users (no admin code)
- **Scalability**: Admin features can grow independently
- **Deployment**: Independent versioning and deployment
- **UX**: Optimized UI/UX for admin workflows (different from user workflows)

**Trade-offs:**

- **Code Duplication**: Some shared code (components, utilities) needs to be managed
- **Deployment Complexity**: Two apps to deploy instead of one
- **Maintenance**: Two codebases to maintain

### Decision: Separate App ✅

Given the security and scalability benefits, a separate admin app is the right choice.

---

## Technology Stack

### Core Framework

- **Next.js 14+** (App Router)
- **TypeScript** (strict mode)
- **React 18+**

### UI & Styling

- **Tailwind CSS** (same as main app)
- **shadcn/ui** (shared component library)
- **Lucide React** (icons, same as main app)

### State Management

- **React Query (TanStack Query)** - Server state (API calls)
- **React Context** - Client state (auth, UI state)
- **Zustand** (optional) - Complex client state if needed

### API Client

- **Fetch API** (native) or **Axios**
- **Custom API client wrapper** (shared with main app if possible)

### Form Handling

- **React Hook Form** (if forms needed)
- **Zod** (schema validation)

### Testing

- **Vitest** - Unit tests
- **React Testing Library** - Component tests
- **Playwright** - E2E tests (optional)

---

## Project Structure

### Proposed Directory Structure

```
admin_frontend/
├── app/                          # Next.js App Router
│   ├── layout.tsx               # Root layout
│   ├── page.tsx                  # Dashboard/home
│   ├── login/                   # Login page
│   │   └── page.tsx
│   ├── workspaces/              # Workspace management
│   │   ├── page.tsx             # List workspaces
│   │   └── [id]/                # Workspace detail
│   │       ├── page.tsx
│   │       ├── usage/           # Usage analytics
│   │       └── abuse/           # Abuse detection
│   ├── users/                   # User management
│   │   ├── page.tsx
│   │   └── [id]/
│   │       └── page.tsx
│   ├── affiliates/              # Affiliate management
│   │   ├── page.tsx             # List affiliates
│   │   ├── [id]/                # Affiliate detail
│   │   │   └── page.tsx
│   │   ├── commissions/         # Commission management
│   │   │   └── page.tsx
│   │   └── payouts/              # Payout management
│   │       └── page.tsx
│   ├── billing/                 # Billing/subscriptions
│   │   └── page.tsx
│   ├── support/                 # Support tools
│   │   ├── documents/
│   │   ├── jobs/
│   │   └── webhooks/
│   └── system/                  # System management
│       ├── audit-logs/
│       └── metrics/
├── components/                   # React components
│   ├── ui/                      # shadcn/ui components (shared)
│   ├── admin/                   # Admin-specific components
│   │   ├── workspace-table.tsx
│   │   ├── affiliate-table.tsx
│   │   ├── commission-table.tsx
│   │   ├── audit-log-viewer.tsx
│   │   └── ...
│   └── layout/                  # Layout components
│       ├── header.tsx
│       ├── sidebar.tsx
│       └── dashboard-layout.tsx
├── lib/                         # Utilities
│   ├── api-client.ts            # API client (shared)
│   ├── auth.ts                  # Auth utilities (shared)
│   ├── types.ts                 # TypeScript types
│   └── utils.ts                 # Helper functions
├── hooks/                       # Custom React hooks
│   ├── use-admin-auth.ts
│   ├── use-workspaces.ts
│   ├── use-affiliates.ts
│   └── ...
├── contexts/                    # React contexts
│   └── admin-auth-context.tsx
├── types/                       # TypeScript type definitions
│   ├── workspace.ts
│   ├── affiliate.ts
│   ├── commission.ts
│   └── ...
├── public/                      # Static assets
├── tests/                       # Test files
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── next.config.js
├── tailwind.config.js
├── tsconfig.json
├── package.json
└── README.md
```

---

## Authentication & Authorization

### Authentication Flow

1. **Login**: Admin logs in via `/api/auth/login` (same endpoint as main app)
2. **Token Storage**: JWT stored in HTTP-only cookie (same as main app)
3. **Token Validation**: Backend validates token and checks `role == "admin"`
4. **Session Management**: Same session management as main app

### Implementation

**Auth Context (`contexts/admin-auth-context.tsx`):**

```typescript
// Simplified example
export function AdminAuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if admin user
    fetch("/api/auth/me")
      .then((res) => res.json())
      .then((data) => {
        if (data.user?.role === "admin") {
          setUser(data.user);
        } else {
          // Redirect to login
        }
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <AdminAuthContext.Provider value={{ user, loading }}>
      {children}
    </AdminAuthContext.Provider>
  );
}
```

**Middleware (`middleware.ts`):**

```typescript
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("auth_token")?.value;

  // Check admin role
  if (token) {
    const payload = decodeJWT(token);
    if (payload?.role !== "admin") {
      return NextResponse.redirect(new URL("/login", request.url));
    }
  } else {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!login|api|_next/static|_next/image|favicon.ico).*)"],
};
```

### Authorization

- **Backend**: All admin endpoints use `require_global_admin` dependency
- **Frontend**: Middleware checks role, but backend is source of truth
- **Failed Auth**: Redirects to `/login` with error message

---

## State Management

### Server State (React Query)

Use React Query for all API calls:

```typescript
// hooks/use-workspaces.ts
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export function useWorkspaces(filters?: WorkspaceFilters) {
  return useQuery({
    queryKey: ["workspaces", filters],
    queryFn: () => apiClient.get("/api/admin/workspaces", { params: filters }),
  });
}
```

### Client State (React Context)

Use Context for:

- **Auth state**: Current admin user
- **UI state**: Sidebar open/closed, theme, etc.

### Complex State (Zustand - Optional)

If needed for complex state:

- **Filters**: Complex filter state across pages
- **Selection**: Multi-select state for bulk actions

---

## API Client

### Shared API Client

Create a shared API client that can be used by both apps (or copy and adapt):

**`lib/api-client.ts`:**

```typescript
class ApiClient {
  private baseURL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  async get(endpoint: string, options?: RequestInit) {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      credentials: "include", // Include cookies
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new ApiError(response.status, await response.json());
    }

    return response.json();
  }

  async post(endpoint: string, data?: any, options?: RequestInit) {
    return this.get(endpoint, {
      ...options,
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // ... other methods
}

export const apiClient = new ApiClient();
```

### Error Handling

```typescript
class ApiError extends Error {
  constructor(public status: number, public data: { detail: string }) {
    super(data.detail);
  }
}

// Usage in components
try {
  await apiClient.post("/api/admin/workspaces/123/suspend", { reason });
} catch (error) {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      // Not authorized - redirect to login
    } else if (error.status === 404) {
      // Not found - show error message
    }
  }
}
```

---

## Routing Structure

### Route Mapping

```
/admin                          → Dashboard (overview)
/admin/login                    → Login page
/admin/workspaces               → List workspaces
/admin/workspaces/[id]          → Workspace detail
/admin/workspaces/[id]/usage    → Usage analytics
/admin/workspaces/[id]/abuse    → Abuse detection
/admin/users                    → List users
/admin/users/[id]               → User detail
/admin/affiliates               → List affiliates
/admin/affiliates/[id]          → Affiliate detail
/admin/affiliates/commissions   → Commission management
/admin/affiliates/payouts       → Payout management
/admin/billing                  → Subscriptions/billing
/admin/support/documents        → Document management
/admin/support/jobs             → Job management
/admin/support/webhooks         → Webhook management
/admin/system/audit-logs        → Audit log viewer
/admin/system/metrics            → System metrics
```

### Route Protection

All routes except `/login` are protected by middleware that checks:

1. User is authenticated (has valid token)
2. User has `admin` role

---

## Component Architecture

### Component Hierarchy

```
App Layout
├── Header (admin branding, user menu)
├── Sidebar (navigation)
└── Main Content
    ├── Page Layout
    │   ├── Page Header (title, breadcrumbs)
    │   ├── Filters/Actions Bar
    │   └── Content Area
    │       ├── Data Table
    │       ├── Detail View
    │       └── Forms/Modals
```

### Reusable Components

**Data Tables:**

- `components/admin/data-table.tsx` - Generic table with sorting, filtering, pagination
- `components/admin/workspace-table.tsx` - Workspace-specific table
- `components/admin/affiliate-table.tsx` - Affiliate-specific table

**Forms/Modals:**

- `components/admin/suspend-workspace-modal.tsx`
- `components/admin/approve-affiliate-modal.tsx`
- `components/admin/adjust-commission-modal.tsx`

**Layout:**

- `components/layout/admin-layout.tsx` - Main admin layout wrapper
- `components/layout/sidebar.tsx` - Navigation sidebar
- `components/layout/header.tsx` - Top header

---

## Shared Code Strategy

### Option 1: Monorepo with Shared Packages (Recommended)

```
docdata_saas/
├── packages/
│   ├── shared-ui/              # Shared UI components
│   │   ├── components/
│   │   ├── lib/
│   │   └── package.json
│   ├── shared-api-client/      # Shared API client
│   │   ├── src/
│   │   └── package.json
│   └── shared-types/           # Shared TypeScript types
│       ├── src/
│       └── package.json
├── frontend/                    # Main user app
├── admin_frontend/              # Admin app
└── backend/                     # Backend API
```

**Benefits:**

- True code sharing
- Single source of truth
- Easier maintenance

**Setup:**

- Use npm/yarn workspaces or pnpm
- Shared packages published internally or linked locally

### Option 2: Copy & Adapt (Simpler, Less Ideal)

- Copy shared components from main app
- Adapt as needed for admin app
- Manual sync when main app updates

**When to Use:**

- Quick MVP
- Admin app needs significant customization
- Shared code is minimal

### Option 3: Git Submodules (Not Recommended)

- Complex to manage
- Version conflicts
- Not recommended for this use case

### Recommendation: Option 1 (Monorepo)

For long-term maintainability, use a monorepo with shared packages.

---

## Deployment Architecture

### Separate Deployment

**Admin App:**

- **Domain**: `admin.docfoundry.com` (or `admin.yourdomain.com`)
- **Container**: Separate Docker container
- **Build**: `next build && next start`
- **Port**: 3001 (or different port)

**Main App:**

- **Domain**: `app.docfoundry.com` (or `yourdomain.com`)
- **Container**: Separate Docker container
- **Port**: 3000

### Nginx Configuration

```nginx
# Admin app
server {
    listen 80;
    server_name admin.docfoundry.com;

    location / {
        proxy_pass http://admin_frontend:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Main app
server {
    listen 80;
    server_name app.docfoundry.com;

    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Docker Compose

```yaml
services:
  backend:
    # ... existing backend config

  frontend:
    # ... existing frontend config

  admin_frontend:
    build: ./admin_frontend
    ports:
      - "3001:3001"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend

  nginx:
    # ... nginx config with both apps
```

### Environment Variables

**Admin App `.env.local`:**

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_ADMIN_APP_URL=http://localhost:3001
```

**Production:**

```env
NEXT_PUBLIC_API_URL=https://api.docfoundry.com
NEXT_PUBLIC_ADMIN_APP_URL=https://admin.docfoundry.com
```

---

## Development Workflow

### Local Development

1. **Start Backend:**

   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   ```

2. **Start Admin Frontend:**

   ```bash
   cd admin_frontend
   npm run dev
   ```

3. **Access:**
   - Admin app: `http://localhost:3001`
   - Backend API: `http://localhost:8000`
   - API docs: `http://localhost:8000/api/docs`

### Code Organization

**File Naming:**

- Components: `kebab-case.tsx` (e.g., `workspace-table.tsx`)
- Hooks: `use-kebab-case.ts` (e.g., `use-workspaces.ts`)
- Types: `kebab-case.ts` (e.g., `workspace-types.ts`)

**Import Paths:**

- Use TypeScript path aliases:
  ```json
  {
    "compilerOptions": {
      "paths": {
        "@/*": ["./*"],
        "@/components/*": ["./components/*"],
        "@/lib/*": ["./lib/*"],
        "@/hooks/*": ["./hooks/*"]
      }
    }
  }
  ```

### Testing Strategy

**Unit Tests:**

- Components: Test rendering, user interactions
- Hooks: Test state management, API calls
- Utilities: Test helper functions

**Integration Tests:**

- API integration: Test API client with mock server
- Workflows: Test complete admin workflows (approve affiliate, suspend workspace)

**E2E Tests (Optional):**

- Critical workflows: Login, suspend workspace, approve affiliate
- Use Playwright or Cypress

---

## Security Considerations

### Frontend Security

1. **No Sensitive Data in Client:**

   - Never expose API keys, secrets, or sensitive config
   - All sensitive operations go through backend

2. **XSS Protection:**

   - Sanitize user input
   - Use React's built-in XSS protection
   - Avoid `dangerouslySetInnerHTML`

3. **CSRF Protection:**

   - Backend handles CSRF (same as main app)
   - Include CSRF token in requests if required

4. **Content Security Policy:**
   - Set CSP headers in Next.js config
   - Restrict inline scripts, external resources

### Authentication Security

1. **Token Storage:**

   - HTTP-only cookies (handled by backend)
   - Never store tokens in localStorage

2. **Token Validation:**

   - Backend validates on every request
   - Frontend checks role but backend is source of truth

3. **Session Timeout:**
   - Backend enforces token expiration
   - Frontend handles expired tokens gracefully

---

## Performance Optimization

### Code Splitting

- **Route-based splitting**: Next.js automatically splits by route
- **Component lazy loading**: Lazy load heavy components
- **Dynamic imports**: Import heavy libraries dynamically

### Data Fetching

- **React Query caching**: Cache API responses
- **Pagination**: Load data in pages (not all at once)
- **Optimistic updates**: Update UI optimistically for better UX

### Bundle Size

- **Tree shaking**: Remove unused code
- **Code splitting**: Split large bundles
- **Image optimization**: Use Next.js Image component

---

## Monitoring & Observability

### Error Tracking

- **Sentry** (or similar): Track frontend errors
- **Error boundaries**: Catch React errors gracefully
- **Error logging**: Log errors to backend

### Analytics

- **Admin actions**: Track admin actions (already logged in backend)
- **Performance**: Track page load times, API call times
- **Usage**: Track which admin features are used most

---

## Migration from Current Setup

### Current State

- Admin functionality exists in main app at `/app/admin`
- Backend endpoints already implemented
- Need to extract admin code to separate app

### Migration Steps

1. **Create Admin App Structure:**

   - Initialize new Next.js app
   - Set up project structure
   - Configure TypeScript, Tailwind

2. **Extract Admin Components:**

   - Copy admin pages from main app
   - Adapt for separate app context
   - Update imports and paths

3. **Set Up Shared Code:**

   - Create shared packages (or copy)
   - Set up API client
   - Set up auth utilities

4. **Update Routing:**

   - Move routes to admin app structure
   - Update navigation
   - Update links

5. **Deploy:**

   - Set up separate deployment
   - Configure Nginx routing
   - Test end-to-end

6. **Remove from Main App:**
   - Remove admin routes from main app
   - Remove admin components
   - Update main app navigation

---

## Future Enhancements

### Potential Improvements

1. **Real-time Updates:**

   - WebSocket connection for live metrics
   - Real-time notifications for admin actions

2. **Advanced Filtering:**

   - Complex filter builder UI
   - Saved filter presets

3. **Bulk Actions:**

   - Select multiple items
   - Bulk approve/reject/suspend

4. **Export Functionality:**

   - Export data to CSV/Excel
   - Generate reports

5. **Dashboard Customization:**
   - Customizable dashboard widgets
   - Drag-and-drop layout

---

**Document End**
