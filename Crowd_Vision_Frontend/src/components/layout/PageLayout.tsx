import { ReactNode } from 'react';
import { TopNav } from './TopNav';
import { cn } from '@/lib/utils';

interface PageLayoutProps {
  children: ReactNode;
  bgClassName?: string;
}

export function PageLayout({ children, bgClassName }: PageLayoutProps) {
  return (
    <div className={cn("min-h-screen flex flex-col transition-colors duration-300", bgClassName || "bg-background")}>
      <TopNav />
      <main className="flex-1 px-3 py-3 sm:px-4 sm:py-6">
        {children}
      </main>
      <footer className="border-t border-border bg-card py-4">
        <div className="container mx-auto px-4 flex justify-between items-center text-xs text-muted-foreground">
          <span>© 2025 TRIDE - Crowd Analytics Platform</span>

        </div>
      </footer>
    </div>
  );
}
