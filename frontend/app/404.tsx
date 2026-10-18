import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { FileQuestion } from "lucide-react";
import { ROUTES } from "@/lib/constants";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="max-w-md w-full text-center">
        <CardHeader>
          <FileQuestion className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
          <CardTitle>Page not found</CardTitle>
          <CardDescription>
            The page you're looking for doesn't exist or you don't have access.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link href={ROUTES.DASHBOARD}>Back to dashboard</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
