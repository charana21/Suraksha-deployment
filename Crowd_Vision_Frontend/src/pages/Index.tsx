import React from "react";
import { Header } from "@/components/Header";
import { VideoUploader } from "@/components/VideoUploader";
import { AnalysisResults } from "@/components/AnalysisResults";
import { useVideoAnalysis } from "@/hooks/useVideoAnalysis";
import { Radar, Shield, Cpu, BarChart3 } from "lucide-react";

const Index = () => {
  const { uploadState, result, uploadVideo, cancelUpload, resetAnalysis } =
    useVideoAnalysis();

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Background grid pattern */}
      <div className="fixed inset-0 bg-grid-pattern bg-grid opacity-[0.02] pointer-events-none" />

      {/* Gradient glow effect */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-gradient-radial from-primary/10 via-transparent to-transparent pointer-events-none" />

      <Header />

      <main className="container mx-auto px-4 py-8 relative flex-1">
        {result ? (
          <AnalysisResults result={result} onNewAnalysis={resetAnalysis} />
        ) : (
          // <LiveAnalysisResults result={result} onNewAnalysis={resetAnalysis} />
          <div className="max-w-4xl mx-auto space-y-12">
            {/* Hero Section */}
            <div className="text-center space-y-4 animate-fade-in-up">
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm font-medium">
                <Cpu className="w-4 h-4" />
                <span>AI-Powered Analysis</span>
              </div>

              <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight">
                Crowd Density
                <span className="text-primary"> Analysis</span>
              </h1>

              <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                Upload surveillance footage for real-time crowd analysis. Get
                instant risk assessments, density heatmaps, and safety alerts
                powered by advanced neural networks.
              </p>
            </div>

            {/* Upload Section */}
            <VideoUploader
              onUpload={uploadVideo}
              uploadState={uploadState}
              onCancel={cancelUpload}
            />

            {/* Features */}
            <div
              className="grid md:grid-cols-3 gap-6 animate-fade-in-up"
              style={{ animationDelay: "200ms" }}
            >
              <div className="glass-panel p-6 space-y-3">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <Radar className="w-6 h-6 text-primary" />
                </div>
                <h3 className="font-semibold text-foreground">
                  Real-time Detection
                </h3>
                <p className="text-sm text-muted-foreground">
                  YOLOv8 neural network for accurate person detection and
                  tracking across video frames.
                </p>
              </div>

              <div className="glass-panel p-6 space-y-3">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <BarChart3 className="w-6 h-6 text-primary" />
                </div>
                <h3 className="font-semibold text-foreground">
                  Density Heatmaps
                </h3>
                <p className="text-sm text-muted-foreground">
                  Gaussian and neural density estimation with visual heatmap
                  overlays for crowd hotspots.
                </p>
              </div>

              <div className="glass-panel p-6 space-y-3">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <Shield className="w-6 h-6 text-primary" />
                </div>
                <h3 className="font-semibold text-foreground">
                  Risk Assessment
                </h3>
                <p className="text-sm text-muted-foreground">
                  Zone-based risk scoring with automatic alerts for critical
                  density thresholds.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t bg-primary bg-card text-foreground">
        <div className="container mx-auto px-4 py-8">
          <div className="flex flex-col md:flex-row justify-between gap-8">
            {/* Logo + TRIDE Title + Address */}
            <div className="flex flex-col gap-3 max-w-sm">
              <div className="flex items-center gap-3">
                <img
                  src="/image.png"
                  alt="TRIDE Logo"
                  className="h-10 w-auto object-contain"
                />
                <h2 className="text-xl font-bold tracking-wide">TRIDE</h2>
              </div>

             <p className="text-sm text-muted-foreground">
                4th Floor, Plot No.29, Matha Bhuvaneswari Society, Madhapur,
                Hyderabad, Telangana 500084.
              </p>
            </div>

            {/* Contact */}
            <div className="flex flex-col gap-2 text-sm text-muted-foreground">
              <p className="font-semibold text-foreground">Contact</p>
              <p>For sales and business inquiries:</p>
              <p className="text-foreground font-medium">sales@tridemobility.com</p>

              <p className="mt-2">Call Us On</p>
              <p className="text-foreground font-medium">+91 8978881573</p>
            </div>

            {/* Useful Links */}
            <div className="flex flex-col gap-2 text-sm text-muted-foreground"></div>

            {/* Risk Pulse Indicator */}
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-risk-low animate-pulse"></span>
              </span>
            </div>
          </div>

          {/* Bottom Section */}
          <div className="border-tbg-primary mt-6 pt-4 flex flex-col md:flex-row justify-between text-xs text-muted-foreground">
            <span>©2026 ALL RIGHTS RESERVED</span>
            <span>Designed by TRIDE</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Index;
