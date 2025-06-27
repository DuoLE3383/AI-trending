// Thêm dòng này ở đầu để báo cho Next.js đây là một Client Component
'use client';

import React, { useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
// Corrected paths, using absolute imports relative to the /src directory
import {StatCard} from '../components/components/StatCard';
import {TradesTable} from '../components/components/TradesTable';

import type { Stats, Trade } from '@/lib/types';

const MOCK_STATS: Stats = {
    win_rate: 0,
    total_completed_trades: 0,
    wins: 0,
    losses: 0
};
const MOCK_TRADES: Trade[] = [];

// Tối ưu hóa: Dynamic import cho WinLossPieChart để giảm kích thước bundle
const DynamicWinLossPieChart = dynamic(
    // Sửa lỗi đường dẫn: Trỏ trực tiếp đến file component để tree-shaking hiệu quả hơn
    () => import('../components/components/WinLossPieChart').then((mod) => mod.WinLossPieChart),
    { 
        ssr: false,
        loading: () => <div className="bg-gray-800 rounded-lg p-6 h-full flex items-center justify-center min-h-[300px]"><p className="text-gray-400">Loading Chart...</p></div>
});

// --- Component chính của ứng dụng ---
export default function Home() {
    const [stats, setStats] = useState<Stats>(MOCK_STATS);
    const [activeTrades, setActiveTrades] = useState<Trade[]>(MOCK_TRADES);
    const [closedTrades, setClosedTrades] = useState<Trade[]>(MOCK_TRADES);
    const [error, setError] = useState<string | null>(null); // Consider using a more specific error type
    const [isLoading, setIsLoading] = useState<boolean>(true); // Add loading state
    
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL; 

    // Helper function to handle individual fetch results
    const handleFetchResult = useCallback(async <T,>(
        result: PromiseSettledResult<Response>,
        setter: React.Dispatch<React.SetStateAction<T>>,
        mockData: T,
        errorMessage: string
    ): Promise<boolean> => {
        if (result.status === 'fulfilled' && result.value.ok) {
            const data = await result.value.json(); // Consider adding type validation here
            setter(data);
            return false; // No error for this specific fetch
        } else {
            console.error(errorMessage, result.status === 'rejected' ? result.reason : 'Response not OK');
            setter(mockData); // Fallback to mock data
            return true; // Error occurred for this specific fetch
        }
    }, []);

    // useCallback để tối ưu, tránh tạo lại hàm mỗi lần render
    const fetchData = useCallback(async () => {
        setIsLoading(true); // Set loading to true at the start of fetch

        // Validate API_BASE_URL - Consider moving this validation to build time
        if (!API_BASE_URL) {
            console.error("API_BASE_URL is not defined. Please check your .env.local file.");
            setError("Cấu hình API không đúng. Vui lòng kiểm tra biến môi trường.");
            setStats(MOCK_STATS);
            setActiveTrades(MOCK_TRADES);
            setClosedTrades(MOCK_TRADES);
            setIsLoading(false);
            return;
        }

        // Sử dụng Promise.allSettled để tất cả các API call có thể hoàn thành, - Good practice!
        // ngay cả khi một trong số chúng thất bại.
        const results = await Promise.allSettled([
            fetch(`${API_BASE_URL}/api/stats`),
            fetch(`${API_BASE_URL}/api/trades?status=active`),
            fetch(`${API_BASE_URL}/api/trades?status=closed&limit=15`)
        ]);
        
        let anyError = false;

        anyError = await handleFetchResult<Stats>(results[0], setStats, MOCK_STATS, "Lỗi khi lấy dữ liệu thống kê (stats):") || anyError;
        anyError = await handleFetchResult<Trade[]>(results[1], setActiveTrades, MOCK_TRADES, "Lỗi khi lấy giao dịch đang hoạt động (active trades):") || anyError;
        anyError = await handleFetchResult<Trade[]>(results[2], setClosedTrades, MOCK_TRADES, "Lỗi khi lấy lịch sử giao dịch (closed trades):") || anyError;

        if (anyError) {
            setError("Không thể kết nối đến một hoặc nhiều dịch vụ. Hiển thị dữ liệu dự phòng cho các thành phần bị lỗi.");
        } else {
            setError(null);
        }
        setIsLoading(false); // Set loading to false after all fetches
    }, [handleFetchResult]);

    // Fetch dữ liệu khi component được tải và sau đó cập nhật sau mỗi 5 giây
    useEffect(() => {
        fetchData(); 
        const interval = setInterval(fetchData, 5000); 
        return () => clearInterval(interval); // Dọn dẹp interval khi component bị hủy
    }, [fetchData]);


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
                {isLoading ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                        {/* Simple loading skeletons for StatCards */}
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

                {/* Main Content Area */}
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

                 {/* Footer */}
                <footer className="text-center text-gray-500 mt-12">
                    <p>AI Signal Pro</p>
                </footer>
            </div>
        </main>
    );
}
