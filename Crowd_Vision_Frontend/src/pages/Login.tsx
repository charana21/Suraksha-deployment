import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { Loader2, Lock, User,Eye,EyeOff } from 'lucide-react';
import { cn } from "@/lib/utils";
import { userLocationApi } from "@/services/userLocationApi";

const Login = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();
    const { toast } = useToast();
    const [showPassword, setShowPassword] = useState(false);
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!email || !password) {
            toast({
                variant: "destructive",
                title: "Validation Error",
                description: "Please enter both email and password.",
                duration: 4000,
            });
            return;
        }

        setLoading(true);
        try {
            const response = await login(email, password);
            toast({
                title: "Login Successful",
                description: response?.responseMsg || "Logged in successfully.",
                duration: 4000,
            });
        } catch (error) {
            const message = error instanceof Error ? error.message : "Invalid email or password.";
            toast({
                variant: "destructive",
                title: "Login Failed",
                description: message,
                duration: 4000,
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen w-full flex items-center justify-center bg-[#020617] relative overflow-hidden">
            {/* Background Ambient Effects */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
                <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-500/10 rounded-full blur-[100px]" />
                <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/10 rounded-full blur-[100px]" />
            </div>

            <div className="w-full max-w-md p-8 relative z-10">
                <div className="mb-8 text-center">
                    <h1 className="text-4xl font-black tracking-tight text-foreground mb-2">
                        SURAKSHA<span className="text-blue-500">AI</span>
                    </h1>
                    <p className="text-slate-400">Secure Access Portal</p>
                </div>

                <div className="bg-[#0B0F1A]/80 backdrop-blur-xl border border-white/5 rounded-2xl p-8 shadow-2xl">
                    <form onSubmit={handleSubmit} className="space-y-6">
                        <div className="space-y-2">
                            <Label htmlFor="email" className="text-slate-300">Email</Label>
                            <div className="relative">
                                <User className="absolute left-3 top-2.5 h-5 w-5 text-slate-500" />
                                <Input
                                    id="email"
                                    type="email"
                                    placeholder="Enter your email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="pl-10 bg-slate-950/50 border-slate-800 focus:border-blue-500 text-foreground placeholder:text-slate-600 transition-all"
                                    disabled={loading}
                                />
                            </div>
                        </div>

    <div className="space-y-2">
    <Label htmlFor="password" className="text-slate-300">Password</Label>

    <div className="relative">
        {/* Left Lock Icon */}
        <Lock className="absolute left-3 top-2.5 h-5 w-5 text-slate-500" />

        {/* Input */}
        <Input
        id="password"
        type={showPassword ? "text" : "password"}
        placeholder="Enter your password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="pl-10 pr-10 bg-slate-950/50 border-slate-800 focus:border-blue-500 text-foreground placeholder:text-slate-600 transition-all"
        disabled={loading}
        />

        {/* Eye Icon */}
        <button
        type="button"
        onClick={() => setShowPassword(prev => !prev)}
        className="absolute right-3 top-2.5 text-slate-500 hover:text-foreground transition-colors"
        tabIndex={-1}
        >
        {showPassword ? (
            <EyeOff className="h-5 w-5" />
        ) : (
            <Eye className="h-5 w-5" />
        )}
        </button>
    </div>
    </div>

                        <Button
                            type="submit"
                            className={cn(
                                "w-full bg-blue-600 hover:bg-blue-500 text-foreground font-bold py-6 rounded-xl transition-all duration-300 shadow-lg shadow-blue-900/20",
                                loading && "opacity-70 cursor-not-allowed"
                            )}
                            disabled={loading}
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                                    Authenticating...
                                </>
                            ) : (
                                "Sign In"
                            )}
                        </Button>

                        <div className="relative mt-6">
                            <div className="absolute inset-0 flex items-center">
                                <span className="w-full border-t border-slate-800" />
                            </div>
                            <div className="relative flex justify-center text-xs uppercase">
                                <span className="bg-[#0B0F1A] px-2 text-slate-500">
                                    Protected System
                                </span>
                            </div>
                        </div>
                    </form>
                </div>

                <p className="mt-8 text-center text-xs text-slate-600">
                    &copy; 2026 SURAKSHA AI. All rights reserved.
                </p>
            </div>
        </div>
    );
};

export default Login;
