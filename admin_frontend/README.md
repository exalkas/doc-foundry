# DocFoundry Admin App

Separate admin frontend application for platform administration. This is a Next.js 14+ application built with TypeScript, Tailwind CSS, and shadcn/ui components.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Development](#development)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Overview

The Admin App is a separate frontend application specifically designed for platform administrators. It provides comprehensive management capabilities for:

- **Phase 1 (Completed)**: Foundation, authentication, layout, dashboard
- **Phase 2 (Planned)**: Workspace management (suspend, unsuspend, impersonate)
- **Phase 2 (Planned)**: User management
- **Phase 2 (Planned)**: Affiliate program management
- **Phase 3 (Planned)**: Commission and payout management
- **Phase 3 (Planned)**: Support tools (documents, jobs, webhooks)
- **Phase 4 (Planned)**: System monitoring and metrics
- **Phase 4 (Planned)**: Audit logs

### Key Features

- **Separate from Main App**: Complete isolation from user-facing application
- **Admin-Only Access**: Protected by admin role verification
- **Comprehensive Management**: Full CRUD operations for platform entities
- **Real-time Metrics**: System health and performance monitoring
- **Audit Trail**: Complete logging of all admin actions

## Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js**: 18.0.0 or higher
- **npm**: 9.0.0 or higher (or yarn/pnpm)
- **Git**: For version control
- **Backend API**: The FastAPI backend must be running and accessible

## Getting Started

### 1. Clone the Repository

```bash
git clone <repository-url>
cd generated_apps/docdata_saas/admin_frontend
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Configure Environment Variables

Create a `.env.local` file in the root directory:

```env
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000
BACKEND_URL=http://localhost:8000

# Optional: Admin app URL (for development)
NEXT_PUBLIC_ADMIN_APP_URL=http://localhost:3001
```

### 4. Start Development Server

```bash
npm run dev
```

The admin app will be available at `http://localhost:3001` by default.

### 5. Access the Application

1. Navigate to `http://localhost:3001`
2. You will be redirected to the login page
3. Log in with an admin account (user must have `role: "admin"`)
4. You'll see the dashboard with workspace overview and system metrics

**Current Status:** Phase 1 (Foundation) is complete. The app includes:

- ✅ Authentication system with admin role verification
- ✅ Protected routes via middleware
- ✅ Dashboard with workspace overview
- ✅ Navigation structure ready for Phase 2 features

## Development

### Available Scripts

- `npm run dev` - Start development server on port 3001
- `npm run build` - Build production bundle
- `npm run start` - Start production server
- `npm run lint` - Run ESLint

### Development Workflow

1. **Start Backend**: Ensure the FastAPI backend is running on port 8000
2. **Start Admin App**: Run `npm run dev` in the admin_frontend directory
3. **Make Changes**: Edit files in `app/`, `components/`, `lib/`, etc.
4. **Hot Reload**: Next.js will automatically reload on file changes
5. **Check Console**: Monitor browser console and terminal for errors

### Code Style

- **TypeScript**: Strict mode enabled
- **ESLint**: Next.js recommended configuration
- **Formatting**: Prettier (recommended)
- **Components**: Use functional components with hooks
- **Naming**: PascalCase for components, camelCase for functions/variables

### Common Patterns

#### API Calls

```typescript
import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api-client";

const { data, isLoading, error } = useQuery({
  queryKey: ["workspaces"],
  queryFn: () => get<Workspace[]>("/api/admin/workspaces"),
});
```

#### Authentication

```typescript
import { useAdminAuthContext } from "@/contexts/admin-auth-context";

const { user, loading, logout } = useAdminAuthContext();
```

#### Error Handling

The app includes error boundaries and error pages. See [Architecture Documentation](./docs/ARCHITECTURE.md) for details.

## Environment Variables

### Required Variables

| Variable              | Description                       | Default                 |
| --------------------- | --------------------------------- | ----------------------- |
| `NEXT_PUBLIC_API_URL` | Backend API base URL              | `http://localhost:8000` |
| `BACKEND_URL`         | Backend API URL (for server-side) | `http://localhost:8000` |

### Optional Variables

| Variable                    | Description                   | Default                 |
| --------------------------- | ----------------------------- | ----------------------- |
| `NEXT_PUBLIC_ADMIN_APP_URL` | Admin app URL (for redirects) | `http://localhost:3001` |

### Production Variables

For production deployment, set:

```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
BACKEND_URL=https://api.yourdomain.com
NEXT_PUBLIC_ADMIN_APP_URL=https://admin.yourdomain.com
```

## Project Structure

```
admin_frontend/
├── app/                    # Next.js App Router
│   ├── layout.tsx         # Root layout with providers
│   ├── page.tsx           # Dashboard homepage
│   ├── error.tsx          # Error page
│   ├── login/             # Login page
│   ├── workspaces/         # Workspace management
│   ├── users/             # User management
│   ├── affiliates/        # Affiliate management
│   └── ...
├── components/            # React components
│   ├── ui/               # shadcn/ui components
│   ├── layout/           # Layout components (header, sidebar)
│   └── error-boundary.tsx # Error boundary component
├── contexts/             # React contexts
│   └── admin-auth-context.tsx
├── hooks/               # Custom React hooks
│   └── use-admin-auth.ts
├── lib/                 # Utilities
│   ├── api-client.ts    # API client with error handling
│   ├── auth.ts          # Authentication utilities
│   ├── types.ts         # TypeScript type definitions
│   └── utils.ts        # Helper functions
├── middleware.ts        # Next.js middleware for route protection
├── next.config.js       # Next.js configuration
├── tailwind.config.js   # Tailwind CSS configuration
├── tsconfig.json        # TypeScript configuration
└── package.json         # Dependencies and scripts
```

For detailed architecture information, see [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Deployment

### Build for Production

```bash
npm run build
```

This creates an optimized production bundle in the `.next` directory.

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine AS runner
WORKDIR /app
ENV NODE_ENV production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs
USER nextjs
EXPOSE 3001
CMD ["npm", "start"]
```

### Environment Setup

Ensure production environment variables are set:

```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
BACKEND_URL=https://api.yourdomain.com
NEXT_PUBLIC_ADMIN_APP_URL=https://admin.yourdomain.com
```

### Nginx Configuration

Example Nginx configuration for admin app:

```nginx
server {
    listen 80;
    server_name admin.yourdomain.com;

    location / {
        proxy_pass http://admin_frontend:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Troubleshooting

### Common Issues

#### 1. Cannot Connect to Backend

**Problem**: API calls fail with connection errors.

**Solution**:

- Verify backend is running on port 8000
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Ensure CORS is configured on backend
- Check browser console for specific error messages

#### 2. Authentication Not Working

**Problem**: Login fails or redirects immediately.

**Solution**:

- Verify user has `role: "admin"` in backend
- Check browser cookies (should have `auth_token`)
- Verify backend `/api/auth/login` endpoint is working
- Check middleware.ts is correctly configured

#### 3. Port Already in Use

**Problem**: `Error: Port 3001 is already in use`

**Solution**:

```bash
# Find process using port 3001
lsof -i :3001  # macOS/Linux
netstat -ano | findstr :3001  # Windows

# Kill process or use different port
npm run dev -- -p 3002
```

#### 4. Build Errors

**Problem**: `npm run build` fails.

**Solution**:

- Clear `.next` directory: `rm -rf .next`
- Clear node_modules: `rm -rf node_modules && npm install`
- Check TypeScript errors: `npx tsc --noEmit`
- Check ESLint errors: `npm run lint`

#### 5. Styling Issues

**Problem**: Styles not loading or Tailwind classes not working.

**Solution**:

- Verify `tailwind.config.js` includes all content paths
- Check `globals.css` imports Tailwind directives
- Restart development server
- Clear browser cache

### Getting Help

- Check [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for architecture details
- Check [docs/DEVELOPMENT.md](./docs/DEVELOPMENT.md) for development guidelines
- Review browser console and terminal output for error messages
- Check backend API documentation

## Contributing

### Development Guidelines

1. **Follow TypeScript**: Use proper types, avoid `any`
2. **Component Structure**: Keep components small and focused
3. **Error Handling**: Always handle errors gracefully
4. **Testing**: Write tests for new features (when test setup is added)
5. **Documentation**: Update docs when adding features

### Code Review Process

1. Create a feature branch
2. Make changes with clear commit messages
3. Ensure code passes linting
4. Test locally with backend running
5. Submit pull request with description

### Commit Message Format

```
type(scope): subject

body (optional)

footer (optional)
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Additional Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [React Query Documentation](https://tanstack.com/query/latest)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [shadcn/ui Components](https://ui.shadcn.com/)
- [TypeScript Documentation](https://www.typescriptlang.org/docs/)

## License

[Your License Here]
