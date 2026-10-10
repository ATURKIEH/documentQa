import { useState } from "react";
import { API_URL } from "../config";

export function LoginForm({ onLogin, onSwitchToSignup, notice }: { onLogin: (accessToken: string, refreshToken: string) => void; onSwitchToSignup: () => void; notice?: string | null }) {
    const [email, setEmail] = useState<string>("");
    const [password, setPassword] = useState<string>("");
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setError(null);
        setIsSubmitting(true);
        try {
            const response = await fetch(`${API_URL}/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: new URLSearchParams({ username: email, password }),
            });
            if (response.status === 401) {
                setError("Invalid email or password.");
                return;
            }
            if (!response.ok) {
                setError("Something went wrong. Please try again.");
                return;
            }
            const data = await response.json();
            onLogin(data.access_token, data.refresh_token);
        } catch {
            setError("Could not reach the server.");
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <form
                onSubmit={handleSubmit}
                className="w-80 bg-surface border border-gray-200 rounded-2xl p-6 space-y-4"
            >
                <h1 className="text-lg font-semibold text-center">Document Q&A</h1>
                <input
                    type="email"
                    required
                    placeholder="Email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full border border-gray-300 rounded-full px-4 py-2 text-sm focus:outline-none focus:border-blue-500"
                />
                <input
                    type="password"
                    required
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full border border-gray-300 rounded-full px-4 py-2 text-sm focus:outline-none focus:border-blue-500"
                />
                <p className="text-xs text-gray-500">
                    Create an account{" "}
                    <button
                        type="button"
                        onClick={onSwitchToSignup}
                        className="text-blue-600 hover:underline"
                    >
                        Sign up
                    </button>
                </p>
                {notice && <p className="text-sm text-green-600">{notice}</p>}
                {error && <p className="text-sm text-red-600">{error}</p>}
                
                <button
                    type="submit"
                    disabled={isSubmitting}
                    className="w-full bg-blue-600 text-white rounded-full py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                    {isSubmitting ? "Signing in..." : "Sign in"}
                </button>
            </form>
        </div>
    );
}


