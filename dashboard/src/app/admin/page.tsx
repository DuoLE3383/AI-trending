// This is a Client Component because it uses state and interacts with APIs.
'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { jwtDecode } from 'jwt-decode'; // You'll need to install this: npm install jwt-decode

// Define types for user data and the decoded token
interface User {
    id: number;
    username: string;
    role: 'admin' | 'user';
}
interface DecodedToken {
    role: string;
    // Add other token claims if needed
}

export default function AdminPanel() {
    const [users, setUsers] = useState<User[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const router = useRouter();
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

    // State for the new user form
    const [newUsername, setNewUsername] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [newRole, setNewRole] = useState<'user' | 'admin'>('user');
    
    const fetchUsers = useCallback(async (token: string) => {
        setIsLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE_URL}/api/admin/users`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!res.ok) {
                throw new Error('Failed to fetch users. You may not have admin rights.');
            }
            const data = await res.json();
            setUsers(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    }, [API_BASE_URL]);

    // Initial check for authentication and role
    useEffect(() => {
        const token = localStorage.getItem('authToken');
        if (!token) {
            router.push('/login');
            return;
        }
        
        try {
            const decoded: DecodedToken = jwtDecode(token);
            if (decoded.role !== 'admin') {
                // If the user is not an admin, redirect them away.
                router.push('/');
                return;
            }
            // If user is an admin, fetch the list of users.
            fetchUsers(token);
        } catch (e) {
            // If token is invalid
            localStorage.removeItem('authToken');
            router.push('/login');
        }
    }, [router, fetchUsers]);

    const handleCreateUser = async (e: React.FormEvent) => {
        e.preventDefault();
        const token = localStorage.getItem('authToken');
        if (!token) return;

        try {
            const res = await fetch(`${API_BASE_URL}/api/admin/users`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({ username: newUsername, password: newPassword, role: newRole }),
            });
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.msg || 'Failed to create user.');
            }
            // Reset form and refresh user list
            setNewUsername('');
            setNewPassword('');
            fetchUsers(token);
        } catch (err: any) {
            setError(err.message);
        }
    };

    const handleDeleteUser = async (userId: number) => {
        if (!window.confirm("Are you sure you want to delete this user? This cannot be undone.")) {
            return;
        }
        const token = localStorage.getItem('authToken');
        if (!token) return;

        try {
            const res = await fetch(`${API_BASE_URL}/api/admin/users/${userId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.msg || 'Failed to delete user.');
            }
            fetchUsers(token); // Refresh list on success
        } catch (err: any) {
            setError(err.message);
        }
    };

    return (
        <main className="min-h-screen p-4 sm:p-6 lg:p-8 bg-gray-900 text-white">
            <div className="max-w-4xl mx-auto">
                <header className="mb-8 flex justify-between items-center">
                    <div>
                        <h1 className="text-4xl font-bold">Admin Panel</h1>
                        <p className="text-gray-400">User Management</p>
                    </div>
                    <button onClick={() => router.push('/')} className="bg-blue-500 text-white font-bold py-2 px-4 rounded-lg hover:bg-blue-600">
                        &larr; Back to Dashboard
                    </button>
                </header>

                {error && <div className="bg-red-500/20 text-red-400 p-4 rounded-lg mb-6">{error}</div>}
                
                {/* Create User Form */}
                <div className="bg-gray-800 p-6 rounded-lg mb-8">
                    <h2 className="text-2xl font-semibold mb-4">Create New User</h2>
                    <form onSubmit={handleCreateUser} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                        <div className="md:col-span-1">
                            <label className="block text-sm font-medium text-gray-300">Username</label>
                            <input type="text" value={newUsername} onChange={(e) => setNewUsername(e.target.value)} required className="mt-1 block w-full bg-gray-700 border-gray-600 rounded-md shadow-sm p-2"/>
                        </div>
                        <div className="md:col-span-1">
                            <label className="block text-sm font-medium text-gray-300">Password</label>
                            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required className="mt-1 block w-full bg-gray-700 border-gray-600 rounded-md shadow-sm p-2"/>
                        </div>
                        <div className="md:col-span-1">
                            <label className="block text-sm font-medium text-gray-300">Role</label>
                            <select value={newRole} onChange={(e) => setNewRole(e.target.value as 'user' | 'admin')} className="mt-1 block w-full bg-gray-700 border-gray-600 rounded-md shadow-sm p-2">
                                <option value="user">User</option>
                                <option value="admin">Admin</option>
                            </select>
                        </div>
                        <div className="md:col-span-1">
                           <button type="submit" className="w-full bg-green-600 text-white font-bold py-2 px-4 rounded-lg hover:bg-green-700">Create User</button>
                        </div>
                    </form>
                </div>

                {/* Users List Table */}
                <div className="bg-gray-800 rounded-lg overflow-hidden">
                    <table className="min-w-full divide-y divide-gray-700">
                        <thead className="bg-gray-700/50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">ID</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Username</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Role</th>
                                <th className="px-6 py-3 text-right text-xs font-medium text-gray-300 uppercase">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-700">
                            {isLoading ? (
                                <tr><td colSpan={4} className="text-center p-4">Loading...</td></tr>
                            ) : users.map((user) => (
                                <tr key={user.id}>
                                    <td className="px-6 py-4">{user.id}</td>
                                    <td className="px-6 py-4">{user.username}</td>
                                    <td className="px-6 py-4"><span className={`px-2 py-1 text-xs rounded-full ${user.role === 'admin' ? 'bg-yellow-500/20 text-yellow-300' : 'bg-blue-500/20 text-blue-300'}`}>{user.role}</span></td>
                                    <td className="px-6 py-4 text-right">
                                        <button onClick={() => handleDeleteUser(user.id)} className="text-red-400 hover:text-red-300">Delete</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </main>
    );
}
