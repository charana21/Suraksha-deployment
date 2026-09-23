
import { useEffect, useRef, useState } from "react";

import { Link, useLocation } from "react-router-dom";

import {
  LayoutDashboard,
  AlertTriangle,
  FileText,
  LogOut,
  Menu,
  X,
  Shield,
  CalendarDays,
  Cpu,
  Map,
  Users,
  Sun,
  Moon,
  LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";

import { UserModule } from "@/services/userDetails";

const DIGITAL_TWIN_URL = "https://sec-dt-dev.tride.live/";

type NavItem = {
  label: string;
  path: string;
  icon: LucideIcon;
  isExternal?: boolean;
};

const normalizePath = (urlName: string) => {
  if (!urlName) return "/";

  if (/^https?:\/\//i.test(urlName)) return urlName;

  if (urlName === "/dashboard") return "/";

  return urlName.startsWith("/") ? urlName : `/${urlName}`;
};

const iconForModule = (moduleName: string) => {
  const key = moduleName.trim().toLowerCase();

  if (key.includes("dashboard")) return LayoutDashboard;
  if (key.includes("alert")) return AlertTriangle;
  if (key.includes("report")) return FileText;
  if (key.includes("calendar")) return CalendarDays;
  if (key.includes("user")) return Users;
  if (key.includes("role")) return Shield;
  if (key.includes("module")) return Cpu;
  if (key.includes("map") || key.includes("navigation")) return Map;

  return FileText;
};

const toNavItem = (module: UserModule): NavItem => ({
  label: module.moduleName,
  path: normalizePath(module.urlName),
  icon: iconForModule(module.moduleName),
  isExternal: /^https?:\/\//i.test(module.urlName),
});

const getDisplayRole = (role?: string) => {
  if (!role) return "User";

  return role.charAt(0).toUpperCase() + role.slice(1);
};

const isDigitalTwinItem = (item: NavItem) =>
  item.label.trim().toLowerCase() === "digital twin" ||
  /digitaltwin/i.test(item.path);

export function TopNav() {
  const { logout, user, modules } = useAuth();

  // IMPORTANT:
  // Use the shared ThemeContext instead of keeping a second local theme state.
  // This makes the theme button and Google Maps use the exact same React state.
  const { theme, toggleTheme } = useTheme();

  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const isDark = theme === "dark";

  const userMenuRef = useRef<HTMLDivElement>(null);

  const location = useLocation();

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        userMenuRef.current &&
        !userMenuRef.current.contains(e.target as Node)
      ) {
        setIsUserMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);

    return () =>
      document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const moduleOrder = [
    "dashboard",
    "alerts",
    "reports",
    "calendar insight",
    "digital twin",
  ];

  const visibleModules = modules
    .filter((module) => module.actions?.view === 1)
    .sort((a, b) => {
      const aIndex = moduleOrder.indexOf(a.moduleName.toLowerCase());
      const bIndex = moduleOrder.indexOf(b.moduleName.toLowerCase());

      // If not found in order list, push to end
      return (
        (aIndex === -1 ? 999 : aIndex) -
        (bIndex === -1 ? 999 : bIndex)
      );
    });

  const desiredOrder = [
    "dashboard",
    "alert",
    "report",
    "calendar",
    "digital twin",
  ];

  const nonMasterModules = visibleModules
    .filter((module) => !module.master)
    .map(toNavItem)
    .sort((a, b) => {
      const aName = a.label.toLowerCase();
      const bName = b.label.toLowerCase();

      const aIndex = desiredOrder.findIndex((name) =>
        aName.includes(name)
      );

      const bIndex = desiredOrder.findIndex((name) =>
        bName.includes(name)
      );

      if (aIndex !== -1 && bIndex !== -1) {
        return aIndex - bIndex;
      }

      if (aIndex !== -1) return -1;

      if (bIndex !== -1) return 1;

      return 0;
    });

  const masterModules = visibleModules
    .filter((module) => module.master)
    .map(toNavItem);

  const displayName = user?.full_name || user?.email || "";

  const displayRole = getDisplayRole(user?.role);

  const avatarLetter = displayName
    ? displayName.charAt(0).toUpperCase()
    : "";

  const toggleMobileMenu = () =>
    setIsMobileMenuOpen((prev) => !prev);

  const closeMobileMenu = () =>
    setIsMobileMenuOpen(false);

  return (
    <header className="sticky top-0 z-50 bg-card border-b border-border transition-colors duration-300">
      <div className="max-w-[1600px] 2xl:max-w-[2400px] min-[2560px]:max-w-[98%] mx-auto px-4">
        <div className="flex items-center justify-between h-16">

          {/* Logo */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <img
              src="/image.png"
              alt="Logo"
              className="h-7 w-auto sm:h-8 object-contain"
            />

            <div>
              <h1 className="text-xs sm:text-sm md:text-base lg:text-lg font-semibold text-foreground">
                SURAKSHA AI
              </h1>

              <p className="text-[10px] sm:text-xs text-muted-foreground">
                Real-time Monitoring Platform
              </p>
            </div>
          </div>

          {/* Mobile Header */}
          <div className="flex xl:hidden items-center gap-2">

            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="flex items-center justify-center w-8 h-8 rounded-lg hover:bg-secondary/50 transition-colors"
              aria-label={
                isDark
                  ? "Switch to light mode"
                  : "Switch to dark mode"
              }
              title={isDark ? "Light Mode" : "Dark Mode"}
            >
              {isDark ? (
                <Sun className="w-4 h-4 text-muted-foreground" />
              ) : (
                <Moon className="w-4 h-4 text-muted-foreground" />
              )}
            </button>

            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-status-active animate-pulse" />
            </div>

            <button
              onClick={() => logout()}
              className="flex items-center justify-center w-8 h-8 rounded-lg hover:bg-secondary/50 transition-colors"
              aria-label="Logout"
            >
              <LogOut className="w-4 h-4 text-muted-foreground" />
            </button>

            <button
              onClick={toggleMobileMenu}
              className="flex items-center justify-center w-10 h-10 rounded-lg hover:bg-secondary/50 transition-colors"
              aria-label="Toggle menu"
            >
              <Menu className="w-6 h-6 text-foreground" />
            </button>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden xl:flex items-center gap-1 overflow-x-auto no-scrollbar mask-gradient px-2">
            {nonMasterModules.map((item) => {
              const Icon = item.icon;

              const digitalTwinExternal =
                isDigitalTwinItem(item);

              const isActive =
                !digitalTwinExternal &&
                location.pathname === item.path;

              if (item.isExternal || digitalTwinExternal) {
                return (
                  <div
                    key={`${item.label}-${item.path}`}
                    className="relative group"
                  >
                    <a
                      href={
                        digitalTwinExternal
                          ? DIGITAL_TWIN_URL
                          : item.path
                      }
                      target="_blank"
                      rel="noopener noreferrer"
                      className="nav-tab flex items-center justify-center gap-2 whitespace-nowrap min-h-[40px] px-3 md:px-4 text-muted-foreground hover:text-white transition-colors"
                    >
                      <Icon className="w-5 h-5 flex-shrink-0" />

                      <span>{item.label}</span>
                    </a>
                  </div>
                );
              }

              return (
                <div
                  key={`${item.label}-${item.path}`}
                  className="relative group"
                >
                  <Link
                    to={item.path}
                    className={cn(
                      "nav-tab flex items-center justify-center gap-2 whitespace-nowrap min-h-[40px] px-3 md:px-4",
                      isActive && "nav-tab-active",
                    )}
                  >
                    <Icon className="w-5 h-5 flex-shrink-0" />

                    <span>{item.label}</span>
                  </Link>
                </div>
              );
            })}
          </nav>

          {/* Desktop Right Section */}
          <div className="hidden xl:flex items-center gap-3 flex-shrink-0">

            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="flex items-center justify-center w-9 h-9 rounded-lg hover:bg-secondary/50 transition-colors"
              aria-label={
                isDark
                  ? "Switch to light mode"
                  : "Switch to dark mode"
              }
              title={isDark ? "Light Mode" : "Dark Mode"}
            >
              {isDark ? (
                <Sun className="w-5 h-5 text-muted-foreground" />
              ) : (
                <Moon className="w-5 h-5 text-muted-foreground" />
              )}
            </button>

            <span className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="w-2 h-2 rounded-full bg-status-active animate-pulse" />

              <span className="hidden lg:inline">
                System Active
              </span>
            </span>

            <div className="h-6 w-px bg-white/10" />

            {/* User Menu */}
            <div
              className="relative"
              ref={userMenuRef}
            >
              <button
                onClick={() =>
                  setIsUserMenuOpen((prev) => !prev)
                }
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-secondary/50 transition-colors"
              >
                <div className="w-8 h-8 rounded-full bg-primary/20 border border-primary/40 flex items-center justify-center text-sm font-semibold text-primary flex-shrink-0">
                  {avatarLetter}
                </div>

                <span className="hidden lg:block text-sm text-foreground max-w-[120px] truncate">
                  {displayName}
                </span>
              </button>

              {isUserMenuOpen && (
                <div className="absolute right-0 mt-2 w-72 bg-card text-foreground border border-border rounded-xl shadow-2xl shadow-black/40 overflow-hidden z-50">

                  <div className="flex flex-col items-center gap-2 px-4 py-4 bg-secondary/30 border-b border-border">
                    <div className="w-12 h-12 rounded-full bg-primary/20 border-2 border-primary/40 flex items-center justify-center text-lg font-bold text-primary">
                      {avatarLetter}
                    </div>

                    <p className="text-sm font-semibold text-foreground">
                      {displayName}
                    </p>

                    <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-destructive/15 text-destructive border border-destructive/25">
                      <Shield className="w-3 h-3" />
                      {displayRole}
                    </span>
                  </div>

                  <div className="py-1">
                    <div className="px-4 py-2">
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                        Master Modules
                      </p>
                    </div>

                    {masterModules.length > 0 ? (
                      masterModules.map((item) => {
                        const Icon = item.icon;
                        const isExternal = item.isExternal;

                        if (isExternal) {
                          return (
                            <a
                              key={`${item.label}-${item.path}`}
                              href={item.path}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="w-full flex items-center gap-3 px-4 py-2 text-sm border border-transparent hover:border-slate-300 transition-colors rounded-md"
                            >
                              <Icon className="w-4 h-4 flex-shrink-0" />
                              <span>{item.label}</span>
                            </a>
                          );
                        }

                        return (
                          <Link
                            key={`${item.label}-${item.path}`}
                            to={item.path}
                            onClick={() =>
                              setIsUserMenuOpen(false)
                            }
                            className="w-full flex items-center gap-3 px-4 py-2 text-sm border border-transparent hover:border-slate-300 transition-colors rounded-md"
                          >
                            <Icon className="w-4 h-4 flex-shrink-0" />
                            <span>{item.label}</span>
                          </Link>
                        );
                      })
                    ) : (
                      <div className="px-4 py-2 text-sm text-muted-foreground">
                        No master modules available.
                      </div>
                    )}

                    <div className="my-1 border-t border-slate-200" />

                    <button
                      onClick={() => {
                        logout();
                        setIsUserMenuOpen(false);
                      }}
                      className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-destructive hover:bg-destructive/10 transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      Logout
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      {isMobileMenuOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 xl:hidden"
            onClick={closeMobileMenu}
          />

          <div className="fixed top-0 left-0 h-full w-64 bg-card border-r border-border z-50 xl:hidden shadow-2xl animate-slide-in-left">
            <div className="flex items-center justify-between p-4 border-b border-border">

              <div className="flex items-center gap-2">
                <img
                  src="/image.png"
                  alt="Logo"
                  className="h-7 w-auto object-contain"
                />

                <h2 className="text-sm font-semibold text-foreground">
                  Menu
                </h2>
              </div>

              <button
                onClick={closeMobileMenu}
                className="flex items-center justify-center w-8 h-8 rounded-lg hover:bg-muted transition-colors"
                aria-label="Close menu"
              >
                <X className="w-5 h-5 text-muted-foreground" />
              </button>
            </div>

            <nav className="flex flex-col p-4 gap-2">

              <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-secondary/20">

                <div className="w-9 h-9 rounded-full bg-primary/20 border border-primary/40 flex items-center justify-center text-sm font-bold text-primary flex-shrink-0">
                  {avatarLetter}
                </div>

                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {displayName}
                  </p>

                  <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-destructive/15 text-destructive border border-destructive/25 mt-0.5">
                    <Shield className="w-2.5 h-2.5" />
                    {displayRole}
                  </span>
                </div>
              </div>

              {nonMasterModules.map((item) => {
                const Icon = item.icon;

                const digitalTwinExternal =
                  isDigitalTwinItem(item);

                if (item.isExternal || digitalTwinExternal) {
                  return (
                    <a
                      key={`${item.label}-${item.path}`}
                      href={
                        digitalTwinExternal
                          ? DIGITAL_TWIN_URL
                          : item.path
                      }
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={closeMobileMenu}
                      className="flex items-center gap-3 px-4 py-3 rounded-lg transition-all text-foreground hover:bg-secondary/50"
                    >
                      <Icon className="w-5 h-5 flex-shrink-0" />

                      <span className="text-sm">
                        {item.label}
                      </span>
                    </a>
                  );
                }

                const isActive =
                  location.pathname === item.path;

                return (
                  <Link
                    key={`${item.label}-${item.path}`}
                    to={item.path}
                    onClick={closeMobileMenu}
                    className={cn(
                      "flex items-center gap-3 px-4 py-3 rounded-lg transition-all",
                      isActive
                        ? "bg-primary text-primary-foreground font-semibold shadow-md"
                        : "text-foreground hover:bg-secondary/50",
                    )}
                  >
                    <Icon className="w-5 h-5 flex-shrink-0" />

                    <span className="text-sm">
                      {item.label}
                    </span>
                  </Link>
                );
              })}

              {masterModules.length > 0 && (
                <div className="mt-2 pt-2 border-t border-border">

                  <p className="px-4 pb-2 text-xs font-semibold text-slate-400 uppercase tracking-wide">
                    Master Modules
                  </p>

                  {masterModules.map((item) => {
                    const Icon = item.icon;

                    const digitalTwinExternal =
                      isDigitalTwinItem(item);

                    if (item.isExternal || digitalTwinExternal) {
                      return (
                        <a
                          key={`mobile-${item.label}-${item.path}`}
                          href={
                            digitalTwinExternal
                              ? DIGITAL_TWIN_URL
                              : item.path
                          }
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={closeMobileMenu}
                          className="flex items-center gap-3 px-4 py-3 rounded-lg transition-all text-foreground hover:bg-secondary/50"
                        >
                          <Icon className="w-5 h-5 flex-shrink-0" />

                          <span className="text-sm">
                            {item.label}
                          </span>
                        </a>
                      );
                    }

                    const isActive =
                      location.pathname === item.path;

                    return (
                      <Link
                        key={`mobile-${item.label}-${item.path}`}
                        to={item.path}
                        onClick={closeMobileMenu}
                        className={cn(
                          "flex items-center gap-3 px-4 py-3 rounded-lg transition-all",
                          isActive
                            ? "bg-primary text-primary-foreground font-semibold shadow-md"
                            : "text-foreground hover:bg-secondary/50",
                        )}
                      >
                        <Icon className="w-5 h-5 flex-shrink-0" />

                        <span className="text-sm">
                          {item.label}
                        </span>
                      </Link>
                    );
                  })}
                </div>
              )}

              <div className="mt-2 pt-2 border-t border-border">
                <button
                  onClick={() => {
                    logout();
                    closeMobileMenu();
                  }}
                  className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-destructive hover:bg-destructive/10 transition-colors"
                >
                  <LogOut className="w-5 h-5 flex-shrink-0" />

                  <span className="text-sm">
                    Logout
                  </span>
                </button>
              </div>

            </nav>
          </div>
        </>
      )}
    </header>
  );
}