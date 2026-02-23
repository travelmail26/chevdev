import { Link } from "wouter";
import { Card, CardContent } from "@/components/ui/card";
import { AlertCircle } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md border-border/50 shadow-lg">
        <CardContent className="pt-6">
          <div className="flex mb-4 gap-2">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <h1 className="text-2xl font-bold text-foreground font-serif">404 Page Not Found</h1>
          </div>
          <p className="mt-4 text-sm text-muted-foreground mb-6">
            The page you are looking for does not exist.
          </p>

          <Link href="/">
            <button className="w-full bg-primary text-primary-foreground py-2 rounded-md hover:bg-primary/90 transition-colors">
              Return Home
            </button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
