
import React from "react";

import { Sun, Moon } from "lucide-react";

import { useTheme } from "@/context/ThemeContext";

export const Header: React.FC = () => {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-card/95 text-foreground backdrop-blur-xl transition-colors duration-300">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">

          {/* Left: Logo + Title */}
          <div className="flex items-center gap-3">

            <img
              src="/image.png"
              alt="TRIDE Logo"
              className="h-10 w-auto object-contain"
            />

            <div>
              <h1 className="text-lg font-bold tracking-tight text-foreground">
                TRIDE
              </h1>

              <p className="text-xs text-muted-foreground">
                Intelligent Crowd Analysis with Real-Time Data Analytics
              </p>
            </div>

          </div>

          {/* Right: Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-card text-foreground transition-all duration-200 hover:bg-secondary/50 focus:outline-none focus:ring-2 focus:ring-primary/50"
            title={
              theme === "light"
                ? "Switch to Dark Mode"
                : "Switch to Light Mode"
            }
            aria-label={
              theme === "light"
                ? "Switch to Dark Mode"
                : "Switch to Light Mode"
            }
          >
            {theme === "light" ? (
              <Moon className="h-5 w-5" />
            ) : (
              <Sun className="h-5 w-5" />
            )}
          </button>

        </div>
      </div>
    </header>
  );
};
