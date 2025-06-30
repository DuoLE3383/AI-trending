// Thêm dòng này ở đầu để báo cho Next.js đây là một Client Component
'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { StatCard } from '../components/components/StatCard';
import { TradesTable } from '../components/components/TradesTable';
import type { Stats, Trade } from '@/lib/types';

// Mock data to use as initial state or as a fallback
const MOCK_STATS: Stats = {
    win_rate: 0,
    total_completed_trades: 0,
    wins: 0,
    losses: 0
};
const MOCK_TRADES: Trade[] = [];

// Dynamically import the chart component to reduce initial bundle size.
// A loading placeholder is shown while the component is being fetched.
const DynamicWinLossPieChart = dynamic(
    () => import('../components/components/WinLossPieChart').then((mod) => mod.WinLossPieChart),
    { 
        ssr: false, // This component does not need to be rendered on the server
        loading: () => <div className="bg-gray-800 rounded-lg p-6 h-full flex items-center justify-center min-h-[300px]"><p className="text-gray-400">Loading Chart...</p></div>
    }
);

// --- The main Dashboard Component ---
export default function Home() {
    const [stats, setStats] = useState<Stats>(MOCK_STATS);
    const [activeTrades, setActiveTrades] = useState<Trade[]>(MOCK_TRADES);
    const [closedTrades, setClosedTrades] = useState<Trade[]>(MOCK_TRADES);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const router = useRouter(); // Hook for programmatic navigation

    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

    // A memoized function to fetch all dashboard data.
    const fetchData = useCallback(async () => {
        setIsLoading(true);

        // Check if the user is logged in by looking for the token.
        const token = localStorage.getItem('authToken');
        if (!token) {
            router.push('/login'); // Redirect to login if no token is found.
            return;
        }

        // Include the token in the Authorization header for all API requests.
        const headers = {
            'Authorization': `Bearer ${token}`
        };
        
        try {
            const results = await Promise.allSettled([
                fetch(`${API_BASE_URL}/api/stats`, { headers }),
                fetch(`${API_BASE_URL}/api/trades?status=active`, { headers }),
                fetch(`${API_BASE_URL}/api/trades?status=closed&limit=15`, { headers })
            ]);
            
            // Check if the token has expired or is invalid.
            for (const result of results) {
                if (result.status === 'fulfilled' && result.value.status === 401) {
                    setError("Your session has expired. Please log in again.");
                    localStorage.removeItem('authToken'); // Clear the bad token
                    router.push('/login');
                    return;
                }
            }
            
            // Process the results from the API calls
            let anyError = false;
            const [statsResult, activeTradesResult, closedTradesResult] = results;

            if (statsResult.status === 'fulfilled' && statsResult.value.ok) {
                setStats(await statsResult.value.json());
            } else { anyError = true; }

            if (activeTradesResult.status === 'fulfilled' && activeTradesResult.value.ok) {
                setActiveTrades(await activeTradesResult.value.json());
            } else { anyError = true; }

            if (closedTradesResult.status === 'fulfilled' && closedTradesResult.value.ok) {
                setClosedTrades(await closedTradesResult.value.json());
            } else { anyError = true; }

            if (anyError) {
                setError("Some data could not be loaded. Connection may be unstable.");
            } else {
                setError(null);
            }
        } catch (err) {
            setError("A network error occurred. Could not reach the server.");
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    }, [router, API_BASE_URL]);

    // This hook now only runs the fetchData function on component mount.
    // The automatic refresh interval has been removed.
    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Function to handle user logout.
    const handleLogout = () => {
        localStorage.removeItem('authToken');
        router.push('/login');
    };

    return (
        <main className="min-h-screen p-4 sm:p-6 lg:p-8 bg-gray-900 text-white">
            <div className="max-w-7xl mx-auto">
                <header className="mb-8 flex justify-between items-center">
                    <div>
                        <h1 className="text-4xl font-bold">AI Trading Bot Dashboard</h1>
                        <p className="text-gray-400">Real-time performance statistics</p>
                    </div>
                    <div className="flex items-center space-x-4">
                       {/* The new refresh button */}
                       <button
                           onClick={fetchData}
                           disabled={isLoading}
                           className="bg-indigo-600 text-white font-bold py-2 px-4 rounded-lg hover:bg-indigo-700 disabled:bg-indigo-400 disabled:cursor-not-allowed transition-colors"
                       >
                           {isLoading ? 'Refreshing...' : 'Refresh'}
                       </button>
                       <button onClick={handleLogout} className="bg-red-500 text-white font-bold py-2 px-4 rounded-lg hover:bg-red-600 transition-colors">
                           Logout
                       </button>
                       <div className="w-4 h-4 rounded-full bg-green-500 animate-pulse" title="Live Status"></div>
                    </div>
                </header>

                {error && (
                    <div className="bg-red-500/20 text-red-400 p-4 rounded-lg mb-6">
                        <strong>Error:</strong> {error}
                    </div>
                )}

                {/* Stat Cards with loading skeleton */}
                {isLoading ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                        <div className="bg-gray-800 rounded-lg p-6 h-32 animate-pulse"></div>
                        <div className="bg-gray-800 rounded-lg p-6 h-32 animate-pulse"></div>
                        <div className="bg-gray-800 rounded-lg p-6 h-32 animate-pulse"></div>
                        <div className="bg-gray-800 rounded-lg p-6 h-32 animate-pulse"></div>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                        <StatCard title="Win Rate" value={stats.win_rate ? stats.win_rate.toFixed(2) : '0.00'} unit="%" icon="🏆" color="text-yellow-400" />
                        <StatCard title="Total Closed Trades" value={stats.total_completed_trades} unit="" icon="📈" color="text-blue-400" />
                        <StatCard title="Trades Won" value={stats.wins} unit="" icon="✅" color="text-green-400" />
                        <StatCard title="Trades Lost" value={stats.losses} unit="" icon="❌" color="text-red-400" />
                    </div>
                )}

                {/* Main Content Area with loading skeletons */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <div className="lg:col-span-2">
                        {isLoading ? (
                            <div className="bg-gray-800 rounded-lg p-6 min-h-[300px] animate-pulse"></div>
                        ) : (
                            <TradesTable title="Active Trades" trades={activeTrades} type="active" />
                        )}
                    </div>
                    <div>
                        <DynamicWinLossPieChart data={stats} />
                    </div>
                    <div className="lg:col-span-3">
                        {isLoading ? (
                            <div className="bg-gray-800 rounded-lg p-6 min-h-[300px] animate-pulse"></div>
                        ) : (
                            <TradesTable title="Recent Trade History" trades={closedTrades} type="closed" />
                        )}
                    </div>
                </div>

                 <footer className="text-center text-gray-500 mt-12">
                    <p>AI Signal Pro</p>
                </footer>
            </div>
        </main>
    );
}
