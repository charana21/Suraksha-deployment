import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { User, authApi, LoginResponse } from '@/services/authApi';
import { UserModule, UserModuleActions, userApi } from '@/services/userDetails';
import { useNavigate } from 'react-router-dom';

export type PermissionAction = keyof UserModuleActions;

interface AuthContextType {
    user: User | null;
    modules: UserModule[];
    isAuthenticated: boolean;
    isLoading: boolean;
    login: (email: string, password: string) => Promise<LoginResponse>;
    logout: () => Promise<void>;
    hasModulePermission: (moduleKey: string, action?: PermissionAction) => boolean;
    canViewPath: (path: string) => boolean;
    getLandingPath: (userModules?: UserModule[]) => string;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [modules, setModules] = useState<UserModule[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const navigate = useNavigate();

    const normalizeModulePath = (urlName: string) => {
        if (!urlName) return '';
        if (/^https?:\/\//i.test(urlName)) return urlName;
        if (urlName === '/dashboard') return '/';
        return urlName.startsWith('/') ? urlName : `/${urlName}`;
    };

    const applyUserDetails = (details: {
        userId: string;
        userName: string;
        roleName: string;
        email: string;
        modules: UserModule[];
    }) => {
        setUser({
            userID: details.userId,
            email: details.email,
            full_name: details.userName,
            role: details.roleName.toLowerCase(),
        });
        setModules(details.modules || []);
    };

    const findModule = (moduleKey: string) => {
        const normalizedKey = moduleKey.trim().toLowerCase();
        const normalizedPath = normalizeModulePath(moduleKey).trim().toLowerCase();

        return modules.find((module) => {
            const moduleName = module.moduleName.trim().toLowerCase();
            const urlName = normalizeModulePath(module.urlName).trim().toLowerCase();

            return (
                moduleName === normalizedKey ||
                urlName === normalizedPath ||
                moduleName === normalizedPath
            );
        });
    };

    const hasModulePermission = (
        moduleKey: string,
        action: PermissionAction = 'view',
    ) => {
        const module = findModule(moduleKey);
        return Boolean(module?.actions?.[action] === 1);
    };

    const canViewPath = (path: string) => hasModulePermission(path, 'view');

    const getLandingPath = (userModules: UserModule[] = modules) => {
        const normalizeForCompare = (value: string) =>
            normalizeModulePath(value).trim().toLowerCase();

        const dashboardModule = userModules.find((module) => {
            const moduleName = module.moduleName.trim().toLowerCase();
            const urlName = normalizeForCompare(module.urlName);
            return moduleName === 'dashboard' || urlName === '/';
        });

        if (dashboardModule?.actions?.view === 1) {
            return '/';
        }

        const firstAccessibleModule = userModules.find(
            (module) => module.actions?.view === 1 && !module.master,
        );

        if (!firstAccessibleModule) {
            return '/login';
        }

        return normalizeModulePath(firstAccessibleModule.urlName) || '/login';
    };

    useEffect(() => {
        const restoreSession = async () => {
            const token =
                localStorage.getItem('access_token') ||
                localStorage.getItem('auth_token');
            if (!token) {
                setIsLoading(false);
                return;
            }

            try {
                const details = await userApi.getUserDetails(token);
                applyUserDetails(details);
            } catch {
                localStorage.removeItem('access_token');
                localStorage.removeItem('auth_token');
                setUser(null);
                setModules([]);
            } finally {
                setIsLoading(false);
            }
        };

        restoreSession();
    }, []);

    const login = async (email: string, password: string) => {
        setIsLoading(true);
        try {
            const response = await authApi.login(email, password);
            localStorage.setItem('access_token', response.token);
            localStorage.setItem('auth_token', response.token);
            const details = await userApi.getUserDetails(response.token);
            applyUserDetails(details);
            navigate(getLandingPath(details.modules));
            return response;
        } catch (error) {
            localStorage.removeItem('access_token');
            localStorage.removeItem('auth_token');
            setUser(null);
            setModules([]);
            throw error;
        } finally {
            setIsLoading(false);
        }
    };

    const logout = async () => {
        try {
            await authApi.logout();
        } finally {
            localStorage.removeItem('access_token');
            localStorage.removeItem('auth_token');
            setUser(null);
            setModules([]);
            navigate('/login');
        }
    };

    return (
        <AuthContext.Provider value={{
            user,
            modules,
            isAuthenticated: !!user,
            isLoading,
            login,
            logout,
            hasModulePermission,
            canViewPath,
            getLandingPath,
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
