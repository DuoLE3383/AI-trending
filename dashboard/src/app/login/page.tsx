// This is a Client Component
'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const router = useRouter();
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        try {
            const res = await fetch(`${API_BASE_URL}/api/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });

            if (res.ok) {
                const data = await res.json();
                // --- Store the token ---
                localStorage.setItem('authToken', data.access_token);
                // --- Redirect to the dashboard ---
                router.push('/'); 
            } else {
                const errorData = await res.json();
                setError(errorData.msg || 'Login failed. Please check your credentials.');
            }
        } catch (err) {
            setError('Could not connect to the server. Please try again later.');
            console.error(err);
        }
    };

    return (
        <main className="min-h-screen flex items-center justify-center p-4">
            <div className="w-full max-w-md bg-gray-800 rounded-lg shadow-lg p-8">
                <h1 className="text-3xl font-bold text-center mb-2">AI Trading Bot</h1>
                <p className="text-center text-gray-400 mb-8">Please log in to continue</p>

                <form onSubmit={handleSubmit}>
                    <div className="mb-4">
                        <label className="block text-gray-300 mb-2" htmlFor="username">
                            Username
                        </label>
                        <input
                            id="username"
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-yellow-400"
                            required
                        />
                    </div>
                    <div className="mb-6">
                        <label className="block text-gray-300 mb-2" htmlFor="password">
                            Password
                        </label>
                        <input
                            id="password"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-yellow-400"
                            required
                        />
                    </div>
                    
                    {error && (
                        <div className="bg-red-500/20 text-red-400 text-sm p-3 rounded-lg mb-4 text-center">
                           {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        className="w-full bg-yellow-400 text-gray-900 font-bold py-2 px-4 rounded-lg hover:bg-yellow-500 transition-colors"
                    >
                        Login
                    </button>
                </form>
            </div>
        </main>
    );
}