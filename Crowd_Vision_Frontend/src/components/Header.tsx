import React from "react";
import { Shield, Activity } from "lucide-react";

export const Header: React.FC = () => {
  return (
    <header className="border-b border-border bg-card/50 backdrop-blur-xl sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          {/* Left: Logo + Title */}
          <div className="flex items-center gap-3">
            <img
              src="/image.png" // <-- TRIDE logo
              alt="TRIDE Logo"
              className="h-10 w-auto object-contain"
            />

            <div>
              <h1 className="text-lg font-bold text-foreground tracking-tight">
                TRIDE
              </h1>

              {/* Subtitle with bright white color */}
              <p className="text-xs text-white/90">
                Intelligent Crowd Analysis with Real-Time Data Analytics
              </p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
