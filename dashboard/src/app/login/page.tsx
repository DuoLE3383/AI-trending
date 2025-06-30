// This is a Client Component, which is necessary for using hooks like useState and useRouter.
'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
    // State to toggle between Login and Register views
    const [isRegisterMode, setIsRegisterMode] = useState(false);

    // State for user input fields
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState(''); // For registration form
    
    // State to display feedback messages to the user
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    
    // Next.js hook for programmatically changing routes
    const router = useRouter();

    // Get the API URL from environment variables
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

    /**
     * Clears all form fields and messages.
     */
    const clearForm = () => {
        setUsername('');
        setPassword('');
        setConfirmPassword('');
        setError(null);
        setSuccess(null);
    };

    /**
     * Toggles the view between login and registration forms.
     */
    const handleModeSwitch = () => {
        setIsRegisterMode(!isRegisterMode);
        clearForm();
    };

    /**
     * Handles the API call for user login.
     */
    const handleLogin = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });

            if (res.ok) {
                const data = await res.json();
                localStorage.setItem('authToken', data.access_token);
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
    
    /**
     * Handles the API call for user registration.
     */
    const handleRegister = async () => {
        if (password !== confirmPassword) {
            setError("Passwords do not match.");
            return;
        }

        try {
            // NOTE: This requires a '/api/register' endpoint on your backend.
            const res = await fetch(`${API_BASE_URL}/api/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password, role: 'user' }), // New users default to 'user' role
            });
            
            const data = await res.json();

            if (res.ok) {
                setSuccess("Registration successful! Please log in.");
                setIsRegisterMode(false); // Switch back to login view after success
                clearForm();
                setUsername(username); // Keep username for convenience
            } else {
                setError(data.msg || 'Registration failed. That username may already be taken.');
            }
        } catch (err) {
            setError('Could not connect to the server. Please try again later.');
            console.error(err);
        }
    };

    /**
     * Main submission handler that calls either login or register logic.
     * @param {React.FormEvent} e The form event.
     */
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setSuccess(null);

        if (!API_BASE_URL) {
            setError("Configuration error: The API URL is not set on the frontend.");
            return;
        }

        if (isRegisterMode) {
            await handleRegister();
        } else {
            await handleLogin();
        }
    };

    return (
        <main className="min-h-screen flex items-center justify-center p-4 bg-gray-900 text-white">
            <div className="w-full max-w-md bg-gray-800 rounded-lg shadow-lg p-8">
                <h1 className="text-3xl font-bold text-center mb-2">
                    {isRegisterMode ? 'Create an Account' : 'AI Trading Bot'}
                </h1>
                <p className="text-center text-gray-400 mb-8">
                    {isRegisterMode ? 'Sign up to access the dashboard' : 'Please log in to continue'}
                </p>

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
                    
                    {/* Conditional field for password confirmation in register mode */}
                    {isRegisterMode && (
                        <div className="mb-6">
                            <label className="block text-gray-300 mb-2" htmlFor="confirmPassword">
                                Confirm Password
                            </label>
                            <input
                                id="confirmPassword"
                                type="password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-yellow-400"
                                required
                            />
                        </div>
                    )}
                    
                    {error && (
                        <div className="bg-red-500/20 text-red-400 text-sm p-3 rounded-lg mb-4 text-center">
                           {error}
                        </div>
                    )}
                    {success && (
                        <div className="bg-green-500/20 text-green-400 text-sm p-3 rounded-lg mb-4 text-center">
                           {success}
                        </div>
                    )}

                    <button
                        type="submit"
                        className="w-full bg-yellow-400 text-gray-900 font-bold py-2 px-4 rounded-lg hover:bg-yellow-500 transition-colors"
                    >
                        {isRegisterMode ? 'Register' : 'Login'}
                    </button>
                </form>

                <div className="text-center mt-6">
                    <button
                        onClick={handleModeSwitch}
                        className="text-sm text-yellow-400 hover:text-yellow-300 underline"
                    >
                        {isRegisterMode ? 'Already have an account? Login' : "Don't have an account? Register"}
                    </button>
                </div>
            </div>
        </main>
    );
}
