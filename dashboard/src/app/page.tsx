// Thêm dòng này ở đầu để báo cho Next.js đây là một Client Component
'use client';

import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { StatCard, TradesTable } from '@/components/dashboard';

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

// Dynamic import cho WinLossPieChart để giảm kích thước bundle ban đầu
const DynamicWinLossPieChart = dynamic(() => import('@/components/dashboard').then(mod => mod.WinLossPieChart), {
    ssr: false, // Đảm bảo component này chỉ được render ở client
});

// --- Component chính của ứng dụng ---
export default function Home() {
    const [stats, setStats] = useState<Stats>(MOCK_STATS);
    const [activeTrades, setActiveTrades] = useState<Trade[]>(MOCK_TRADES);
    const [closedTrades, setClosedTrades] = useState<Trade[]>(MOCK_TRADES);
    const [error, setError] = useState<string | null>(null);
    
    // Địa chỉ IP của backend đang chạy
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL

    const fetchData = async () => {
        // Sử dụng Promise.allSettled để tất cả các API call có thể hoàn thành,
        // ngay cả khi một trong số chúng thất bại.
        const results = await Promise.allSettled([
            fetch(`${API_BASE_URL}/api/stats`),
            fetch(`${API_BASE_URL}/api/trades?status=active`),
            fetch(`${API_BASE_URL}/api/trades?status=closed&limit=15`)
        ]);

        const [statsResult, activeTradesResult, closedTradesResult] = results;
        let hasError = false;

        // Xử lý kết quả của /api/stats
        if (statsResult.status === 'fulfilled' && statsResult.value.ok) {
            const statsData = await statsResult.value.json();
            setStats(statsData);
        } else {
            console.error("Lỗi khi lấy dữ liệu thống kê (stats):", statsResult.status === 'rejected' ? statsResult.reason : 'Response not OK');
            setStats(MOCK_STATS); // Quay về dữ liệu giả khi có lỗi
            hasError = true;
        }

        // Xử lý kết quả của /api/trades?status=active
        if (activeTradesResult.status === 'fulfilled' && activeTradesResult.value.ok) {
            const activeTradesData = await activeTradesResult.value.json();
            setActiveTrades(activeTradesData);
        } else {
            console.error("Lỗi khi lấy giao dịch đang hoạt động (active trades):", activeTradesResult.status === 'rejected' ? activeTradesResult.reason : 'Response not OK');
            setActiveTrades(MOCK_TRADES); // Quay về dữ liệu giả khi có lỗi
            hasError = true;
        }

        // Xử lý kết quả của /api/trades?status=closed
        if (closedTradesResult.status === 'fulfilled' && closedTradesResult.value.ok) {
            const closedTradesData = await closedTradesResult.value.json();
            setClosedTrades(closedTradesData);
        } else {
            console.error("Lỗi khi lấy lịch sử giao dịch (closed trades):", closedTradesResult.status === 'rejected' ? closedTradesResult.reason : 'Response not OK');
            setClosedTrades(MOCK_TRADES); // Quay về dữ liệu giả khi có lỗi
            hasError = true;
        }

        if (hasError) {
            setError("Không thể kết nối đến một hoặc nhiều dịch vụ. Hiển thị dữ liệu dự phòng cho các thành phần bị lỗi.");
        } else {
            setError(null);
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
                        <DynamicWinLossPieChart data={stats} />
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
