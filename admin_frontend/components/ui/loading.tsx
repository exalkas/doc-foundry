import { Spinner } from "./spinner";
import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
  message?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

/**
 * Shared loading spinner component for consistent loading states
 */
export function LoadingSpinner({
  message = "Loading...",
  size = "md",
  className,
}: LoadingSpinnerProps) {
  return (
    <div className={cn("flex items-center justify-center py-8", className)}>
      <Spinner size={size} />
      {message && (
        <p className="ml-2 text-sm text-muted-foreground">{message}</p>
      )}
    </div>
  );
}
