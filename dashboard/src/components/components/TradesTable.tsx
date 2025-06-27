import React from 'react';
import type { Trade } from '@/lib/types';

export const TradesTable = ({ title, trades, type }: { title: string, trades: Trade[], type: 'active' | 'closed' }) => {
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
                                            <span className={`px-2 py-1 rounded-full text-xs font-semibold ${trade.status?.includes('TP') ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
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
                                            <span className={`font-semibold ${trade.trend?.includes('BULLISH') ? 'text-green-400' : 'text-red-400'}`}>
                                                {trade.trend ? trade.trend.replace('STRONG_', '') : 'N/A'}
                                            </span>
                                        </td>
                                        <td className="p-3 text-right font-mono">{trade.entry_price || 'N/A'}</td>
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