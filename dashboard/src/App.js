import React, { useState, useEffect } from 'react';
// FIX: Removed unused imports like BarChart, XAxis, etc.
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
// FIX: Removed the import for App.css as it's not needed in this environment and was causing a build error.

// --- MOCK DATA ---
// This data is now only used as a fallback when the backend cannot be reached.
const MOCK_STATS = {
    win_rate: 0,
    total_completed_trades: 0,
    wins: 0,
    losses: 0
};
const MOCK_CLOSED_TRADES = [];
const MOCK_ACTIVE_TRADES = [];
// ------------------------------------


// --- UI Components ---

const StatCard = ({ title, value, unit, icon, color }) => (
    <div className="bg-gray-800 p-6 rounded-lg shadow-lg flex items-center">
        <div className={`text-4xl mr-4 ${color}`}>{icon}</div>
        <div>
            <div className="text-sm text-gray-400">{title}</div>
            <div className="text-2xl font-bold text-white">{value}{unit}</div>
        </div>
    </div>
);

const TradesTable = ({ title, trades, type }) => {
    const isClosed = type === 'closed';
    return (
        <div className="bg-gray-800 p-6 rounded-lg shadow-lg h-full">
            <h2 className="text-xl font-bold text-white mb-4">{title}</h2>
            <div className="overflow-y-auto max-h-80">
                <table className="w-full text-left">
                    <thead>
                        <tr className="border-b border-gray-700">
                            <th className="p-2 text-gray-400">Pair</th>
                            {isClosed ? (
                                <>
                                    <th className="p-2 text-gray-400">Result</th>
                                    <th className="p-2 text-gray-400 text-right">Profit (%)</th>
                                </>
                            ) : (
                                <>
                                    <th className="p-2 text-gray-400">Trend</th>
                                    <th className="p-2 text-gray-400 text-right">Entry Price</th>
                                </>
                            )}
                        </tr>
                    </thead>
                    <tbody>
                        {trades.map((trade, index) => (
                            <tr key={index} className="border-b border-gray-700 last:border-b-0 hover:bg-gray-700/50">
                                <td className="p-3 font-semibold text-white">{trade.symbol}</td>
                                {isClosed ? (
                                    <>
                                        <td className="p-3">
                                            <span className={`px-2 py-1 rounded-full text-xs font-semibold ${trade.status && trade.status.includes('TP') ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                                {trade.status}
                                            </span>
                                        </td>
                                        <td className={`p-3 text-right font-mono ${trade.pnl_percent && trade.pnl_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {trade.pnl_percent ? trade.pnl_percent.toFixed(2) : 'N/A'}%
                                        </td>
                                    </>
                                ) : (
                                    <>
                                        <td className="p-3">
                                            <span className={`font-semibold ${trade.trend && trade.trend.includes('BULLISH') ? 'text-green-400' : 'text-red-400'}`}>
                                                {trade.trend ? trade.trend.replace('STRONG_', '') : 'N/A'}
                                            </span>
                                        </td>
                                        <td className="p-3 text-right font-mono">{trade.entry_price}</td>
                                    </>
                                )}
                            </tr>
                        ))}
                    </tbody>
                </table>
                 {trades.length === 0 && <p className="text-center text-gray-500 py-8">No data available</p>}
            </div>
        </div>
    );
};

const WinLossPieChart = ({ data }) => {
    const chartData = [
        { name: 'Wins', value: data.wins },
        { name: 'Losses', value: data.losses },
    ];
    const COLORS = ['#10B981', '#F43F5E'];

    return (
        <div className="bg-gray-800 p-6 rounded-lg shadow-lg h-full flex flex-col justify-center items-center">
            <h2 className="text-xl font-bold text-white mb-4">Win/Loss Ratio</h2>
            <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                    <Pie data={chartData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} fill="#8884d8" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                        {chartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #4B5563' }} />
                    <Legend />
                </PieChart>
            </ResponsiveContainer>
        </div>
    );
};


// --- Main App Component ---
export default function App() {
    const [stats, setStats] = useState(MOCK_STATS);
    const [activeTrades, setActiveTrades] = useState(MOCK_ACTIVE_TRADES);
    const [closedTrades, setClosedTrades] = useState(MOCK_CLOSED_TRADES);
    const [error, setError] = useState(null);
    // The IP address of your running backend server.
    const API_BASE_URL = 'http://35.228.208.66:5000';

    const fetchData = async () => {
        try {
            const statsResponse = await fetch(`${API_BASE_URL}/api/stats`);
            if (!statsResponse.ok) throw new Error('Network response for stats was not ok');
            const statsData = await statsResponse.json();
            setStats(statsData);

            const activeTradesResponse = await fetch(`${API_BASE_URL}/api/trades?status=active`);
            if (!activeTradesResponse.ok) throw new Error('Network response for active trades was not ok');
            const activeTradesData = await activeTradesResponse.json();
            setActiveTrades(activeTradesData);
            
            const closedTradesResponse = await fetch(`${API_BASE_URL}/api/trades?status=closed&limit=15`);
            if (!closedTradesResponse.ok) throw new Error('Network response for closed trades was not ok');
            const closedTradesData = await closedTradesResponse.json();
            setClosedTrades(closedTradesData);
            
            setError(null);
        } catch (err) {
            console.error("Error fetching data:", err);
            setError("Could not connect to the backend server. Displaying fallback data.");
            // Fallback to mock data on error
            setStats(MOCK_STATS);
            setActiveTrades(MOCK_ACTIVE_TRADES);
            setClosedTrades(MOCK_CLOSED_TRADES);
        }
    };

    // Fetch data on initial load and then set up an interval to poll for new data.
    useEffect(() => {
        fetchData(); 
        const interval = setInterval(fetchData, 5000); // Poll every 5 seconds
        return () => clearInterval(interval); // Cleanup interval on component unmount
    }, []);


    return (
        <div className="bg-gray-900 text-gray-200 min-h-screen p-4 sm:p-6 lg:p-8 font-sans">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <header className="mb-8 flex justify-between items-center">
                    <div>
                        <h1 className="text-4xl font-bold text-white">AI Trading Bot Dashboard</h1>
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
        </div>
    );
}
