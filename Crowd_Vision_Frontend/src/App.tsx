import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/context/ThemeContext";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import { useEffect, useRef } from "react";

import Dashboard from "./pages/Dashboard";
import Cameras from "./pages/Cameras";
import Alerts from "./pages/Alerts";
import Reports from "./pages/Reports";
import SecLayout from "./pages/SecLayout";
import FootfallInsights from "./pages/FootfallInsights";
import PASystem from "./pages/PAXsystem";
import Heatmaps from "./pages/Heatmaps";
import NotFound from "./pages/NotFound";
import Login from "./pages/Login";

import { AuthProvider, useAuth } from "./context/AuthContext";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";

import RolePage from "./pages/master_modules/Roles";
import ModulePage from "./pages/master_modules/Modules";
import UserPage from "./pages/master_modules/Users";
import SystemAudits from "./pages/master_modules/SystemAudits";
import WhatsAppAudits from "./pages/master_modules/WhatsApp_audits";

import DigitalTwinPage from "./pages/Digital_Twin";

const queryClient = new QueryClient();

function DashboardRoute() {
  const {
    isLoading,
    canViewPath,
    getLandingPath,
  } = useAuth();

  if (isLoading) {
    return null;
  }

  if (!canViewPath("/dashboard")) {
    return <Navigate to={getLandingPath()} replace />;
  }

  return <Dashboard />;
}

function ReportsExitListener() {
  const location = useLocation();

  const prevPath = useRef(location.pathname);

  useEffect(() => {
    if (
      prevPath.current === "/reports" &&
      location.pathname !== "/reports"
    ) {
      if (typeof window !== "undefined") {
        const event =
          typeof window.CustomEvent === "function"
            ? new CustomEvent("crowdvision:reports-exit")
            : new Event("crowdvision:reports-exit");

        window.dispatchEvent(event);
      }
    }

    prevPath.current = location.pathname;
  }, [location.pathname]);

  return null;
}

const App = () => {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <Toaster />
          <Sonner />

          <BrowserRouter>
            <ReportsExitListener />

            <AuthProvider>
              <Routes>
                {/* Public Routes */}
                <Route
                  path="/login"
                  element={<Login />}
                />

                {/* Protected Dashboard */}
                <Route
                  path="/"
                  element={
                    <ProtectedRoute>
                      <DashboardRoute />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute>
                      <DashboardRoute />
                    </ProtectedRoute>
                  }
                />

                {/* Cameras */}
                {/*
                <Route
                  path="/cameras"
                  element={
                    <ProtectedRoute>
                      <Cameras />
                    </ProtectedRoute>
                  }
                />
                */}

                {/* Alerts */}
                <Route
                  path="/alerts"
                  element={
                    <ProtectedRoute>
                      <Alerts />
                    </ProtectedRoute>
                  }
                />

                {/* Reports */}
                <Route
                  path="/reports"
                  element={
                    <ProtectedRoute>
                      <Reports />
                    </ProtectedRoute>
                  }
                />

                {/* Security Layout */}
                {/*
                <Route
                  path="/sec-layout"
                  element={
                    <ProtectedRoute>
                      <SecLayout />
                    </ProtectedRoute>
                  }
                />
                */}

                {/* Calendar / Footfall Insights */}
                <Route
                  path="/calendar"
                  element={
                    <ProtectedRoute>
                      <FootfallInsights />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/calendar-insight"
                  element={
                    <ProtectedRoute>
                      <FootfallInsights />
                    </ProtectedRoute>
                  }
                />

                {/* Digital Twin */}
                <Route
                  path="/digitalTwin"
                  element={
                    <ProtectedRoute>
                      <DigitalTwinPage />
                    </ProtectedRoute>
                  }
                />

                {/* PA System */}
                {/*
                <Route
                  path="/pa-system"
                  element={
                    <ProtectedRoute>
                      <PASystem />
                    </ProtectedRoute>
                  }
                />
                */}

                {/* Heatmaps */}
                <Route
                  path="/heatmaps"
                  element={
                    <ProtectedRoute>
                      <Heatmaps />
                    </ProtectedRoute>
                  }
                />

                {/* Old Digital Twin Route */}
                {/*
                <Route
                  path="/digital-twin"
                  element={
                    <ProtectedRoute>
                      <DigitalTwinPage />
                    </ProtectedRoute>
                  }
                />
                */}

                {/* Master Modules */}
                <Route
                  path="/roles"
                  element={
                    <ProtectedRoute>
                      <RolePage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/modules"
                  element={
                    <ProtectedRoute>
                      <ModulePage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/user"
                  element={
                    <ProtectedRoute>
                      <UserPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/audits"
                  element={
                    <ProtectedRoute>
                      <SystemAudits />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/whatsapp_audits"
                  element={
                    <ProtectedRoute>
                      <WhatsAppAudits />
                    </ProtectedRoute>
                  }
                />

                {/* Catch-all */}
                <Route
                  path="*"
                  element={<NotFound />}
                />
              </Routes>
            </AuthProvider>
          </BrowserRouter>
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
};

export default App;