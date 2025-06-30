// This is a Client Component because it uses state and interacts with APIs.
'use client';

import React, { useState, useEffect, useCallback } from 'react';

// --- Mock Data and Types ---
// In a real app, these would be imported or defined in a separate types file.
interface User {
    id: number;
    username: string;
    role: 'admin' | 'user';
}

const MOCK_USERS_DB: User[] = [
    { id: 1, username: 'super_admin', role: 'admin' },
    { id: 2, username: 'jane_doe', role: 'user' },
    { id: 3, username: 'john_smith', role: 'user' },
    { id: 4, username: 'peter_jones', role: 'user' },
    { id: 5, username: 'mary_jane', role: 'user' },
    { id: 6, username: 'dev_admin', role: 'admin' },
];

// --- Mock Implementations for Dependencies ---
// Mocking the router to prevent compilation errors and simulate navigation.
const useMockRouter = () => ({
    push: (path: string) => {
        console.log(`Simulating navigation to: ${path}`);
        // In a real Next.js app, this would change the URL. Here, we just log it.
    },
});

// Mocking jwt-decode to simulate token validation without the actual library.
const mockJwtDecode = (token: string): { role: string } => {
    console.log(`Decoding mock token: ${token}`);
    if (token === 'valid_admin_token') {
        return { role: 'admin' };
    }
    if (token === 'valid_user_token') {
        return { role: 'user' };
    }
    // Simulate an invalid token by throwing an error.
    throw new Error('Invalid token');
};

export default function AdminPanel() {
    const [users, setUsers] = useState<User[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const router = useMockRouter();

    // State for the new user form
    const [newUsername, setNewUsername] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [newRole, setNewRole] = useState<'user' | 'admin'>('user');
    
    // --- Mocked API/Data fetching ---
    // This function simulates fetching data from a database.
    const fetchUsers = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        console.log("Fetching users from mock database...");
        // Simulate network delay
        await new Promise(resolve => setTimeout(resolve, 500)); 
        setUsers(MOCK_USERS_DB);
        setIsLoading(false);
    }, []);

    // Initial check for authentication and role. This now uses the mock functions.
    useEffect(() => {
        // In a real app, you'd get this from localStorage. We'll hardcode a mock token.
        const mockToken = 'valid_admin_token'; 
        
        if (!mockToken) {
            router.push('/login');
            return;
        }
        
        try {
            const decoded = mockJwtDecode(mockToken);
            if (decoded.role !== 'admin') {
                setError("Access denied. You must be an admin to view this page.");
                setTimeout(() => router.push('/'), 3000);
                return;
            }
            // If user is an admin, fetch the list of users.
            fetchUsers();
        } catch (e) {
            // This would run if the mock token was invalid
            router.push('/login');
        }
    }, [router, fetchUsers]);

    const handleCreateUser = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        
        if (!newUsername.trim() || !newPassword.trim()) {
            setError("Username and password cannot be empty.");
            return;
        }

        const newUser: User = {
            id: Math.max(0, ...MOCK_USERS_DB.map(u => u.id)) + 1, // Simulate auto-incrementing ID
            username: newUsername,
            role: newRole,
        };
        
        // Add the new user to the mock database array.
        MOCK_USERS_DB.push(newUser);
        // Refresh the user list from the "database"
        fetchUsers();
        console.log("Created new user (mock):", newUser);

        // Reset form
        setNewUsername('');
        setNewPassword('');
        setNewRole('user');
    };

    const handleDeleteUser = async (userId: number) => {
        if (userId === 1) { // Rule to prevent deleting the primary admin
             setError("The primary admin account cannot be deleted.");
             return;
        }
        if (!window.confirm("Are you sure you want to delete this user?")) {
            return;
        }
        // Simulate a successful deletion by filtering the user from mock DB.
        const userIndex = MOCK_USERS_DB.findIndex(user => user.id === userId);
        if (userIndex > -1) {
            MOCK_USERS_DB.splice(userIndex, 1);
        }
        // Refresh the user list from the "database"
        fetchUsers();
        console.log(`Deleted user with ID (mock): ${userId}`);
    };

    return (
        <main className="min-h-screen p-4 sm:p-6 lg:p-8 bg-gray-900 text-white">
            <div className="max-w-4xl mx-auto">
                <header className="mb-8 flex justify-between items-center">
                    <div>
                        <h1 className="text-4xl font-bold">Admin Panel</h1>
                        <p className="text-gray-400">User Management (Mock Environment)</p>
                    </div>
                    <button onClick={() => router.push('/')} className="bg-blue-500 text-white font-bold py-2 px-4 rounded-lg hover:bg-blue-600">
                        &larr; Back to Dashboard
                    </button>
                </header>

                {error && <div className="bg-red-500/20 text-red-400 p-4 rounded-lg mb-6">{error}</div>}
                
                <div className="bg-gray-800 p-6 rounded-lg mb-8">
                    <h2 className="text-2xl font-semibold mb-4">Create New User</h2>
                    <form onSubmit={handleCreateUser} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                        <div className="md:col-span-1">
                            <label className="block text-sm font-medium text-gray-300">Username</label>
                            <input type="text" value={newUsername} onChange={(e) => setNewUsername(e.target.value)} required className="mt-1 block w-full bg-gray-700 border-gray-600 rounded-md shadow-sm p-2"/>
                        </div>
                        <div className="md:col-span-1">
                            <label className="block text-sm font-medium text-gray-300">Password</label>
                            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required placeholder="••••••••" className="mt-1 block w-full bg-gray-700 border-gray-600 rounded-md shadow-sm p-2"/>
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
                                <tr><td colSpan={4} className="text-center p-4 text-gray-400">Loading users...</td></tr>
                            ) : users.length > 0 ? users.map((user) => (
                                <tr key={user.id} className="hover:bg-gray-700/50">
                                    <td className="px-6 py-4">{user.id}</td>
                                    <td className="px-6 py-4">{user.username}</td>
                                    <td className="px-6 py-4"><span className={`px-2 py-1 text-xs font-semibold rounded-full ${user.role === 'admin' ? 'bg-yellow-500/20 text-yellow-300' : 'bg-blue-500/20 text-blue-300'}`}>{user.role}</span></td>
                                    <td className="px-6 py-4 text-right">
                                        <button onClick={() => handleDeleteUser(user.id)} className="text-red-400 hover:text-red-300 font-semibold">Delete</button>
                                    </td>
                                </tr>
                            )) : (
                                <tr><td colSpan={4} className="text-center p-4 text-gray-500">No users found.</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </main>
    );
}
