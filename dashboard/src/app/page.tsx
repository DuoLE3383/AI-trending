// Thêm dòng này ở đầu để báo cho Next.js đây là một Client Component
'use client';

import React, { useState, useEffect } from 'react';
import { StatCard, TradesTable, WinLossPieChart } from '@/components/dashboard';
import type { Stats, Trade } from '@/lib/types';

// --- Định nghĩa kiểu dữ liệu với TypeScript ---
// --- Dữ liệu giả (Dùng khi không kết nối được backend) ---
const MOCK_STATS: Stats = {
    win_rate: 0,
    total_completed_trades: 0,
    wins: 0,
    losses: 0
};
const MOCK_TRADES: Trade[] = [];

// --- Component chính của ứng dụng ---
export default function Home() {
    const [stats, setStats] = useState<Stats>(MOCK_STATS);
    const [activeTrades, setActiveTrades] = useState<Trade[]>(MOCK_TRADES);
    const [closedTrades, setClosedTrades] = useState<Trade[]>(MOCK_TRADES);
    const [error, setError] = useState<string | null>(null);
    
    // Địa chỉ IP của backend đang chạy
    const API_BASE_URL = 'http://35.228.208.66:5000';

    const fetchData = async () => {
        try {
            const [statsRes, activeRes, closedRes] = await Promise.all([
                fetch(`${API_BASE_URL}/api/stats`),
                fetch(`${API_BASE_URL}/api/trades?status=active`),
                fetch(`${API_BASE_URL}/api/trades?status=closed&limit=15`)
            ]);

            if (!statsRes.ok || !activeRes.ok || !closedRes.ok) {
                throw new Error('One or more network responses were not ok');
            }
            
            const statsData = await statsRes.json();
            const activeTradesData = await activeRes.json();
            const closedTradesData = await closedRes.json();
            
            setStats(statsData);
            setActiveTrades(activeTradesData);
            setClosedTrades(closedTradesData);
            
            setError(null);
        } catch (err) {
            console.error("Error fetching data:", err);
            setError("Could not connect to the backend server. Displaying fallback data.");
            // Quay về dữ liệu giả khi có lỗi
            setStats(MOCK_STATS);
            setActiveTrades(MOCK_TRADES);
            setClosedTrades(MOCK_TRADES);
        }
    };

    // Fetch dữ liệu khi component được tải và sau đó cập nhật sau mỗi 5 giây
    useEffect(() => {
        fetchData(); 
        const interval = setInterval(fetchData, 5000); 
        return () => clearInterval(interval); // Dọn dẹp interval khi component bị hủy
    }, []);


    return (
        <main className="min-h-screen p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <header className="mb-8 flex justify-between items-center">
                    <div>
                        <h1 className="text-4xl font-bold">AI Trading Bot Dashboard</h1>
                        <p className="text-gray-400">Real-time performance statistics</p>
                    </div>
                    <div className="w-4 h-4 rounded-full bg-green-500 animate-pulse" title="Live Status"></div>
                </header>

                {error && (
                    <div className="bg-red-500/20 text-red-400 p-4 rounded-lg mb-6">
                        <strong>Connection Error:</strong> {error}
                    </div>
                )}

                {/* Stat Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                    <StatCard title="Win Rate" value={stats.win_rate ? stats.win_rate.toFixed(2) : '0.00'} unit="%" icon="🏆" color="text-yellow-400" />
                    <StatCard title="Total Closed Trades" value={stats.total_completed_trades} unit="" icon="📈" color="text-blue-400" />
                    <StatCard title="Trades Won" value={stats.wins} unit="" icon="✅" color="text-green-400" />
                    <StatCard title="Trades Lost" value={stats.losses} unit="" icon="❌" color="text-red-400" />
                </div>

                {/* Main Content Area */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <div className="lg:col-span-2">
                        <TradesTable title="Active Trades" trades={activeTrades} type="active" />
                    </div>
                    <div>
                        <WinLossPieChart data={stats} />
                    </div>
                    <div className="lg:col-span-3">
                         <TradesTable title="Recent Trade History" trades={closedTrades} type="closed" />
                    </div>
                </div>

                 {/* Footer */}
                <footer className="text-center text-gray-500 mt-12">
                    <p>AI Signal Pro</p>
                </footer>
            </div>
        </main>
    );
}
