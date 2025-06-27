'use client';

import React from 'react';
import { Pie } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js';
import type { Stats } from '@/lib/types';

ChartJS.register(ArcElement, Tooltip, Legend);

export const WinLossPieChart = ({ data }: { data: Stats }) => {
    const chartData = {
        labels: ['Wins', 'Losses'],
        datasets: [
            {
                label: '# of Trades',
                data: [data.wins || 0, data.losses || 0],
                backgroundColor: ['#10B981', '#F43F5E'],
                borderColor: '#1F2937', // bg-gray-800
                borderWidth: 2,
            },
        ],
    };

    const chartOptions: ChartOptions<'pie'> = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'bottom' as const,
                labels: {
                    color: '#d1d5db' // text-gray-300
                }
            },
            tooltip: {
                backgroundColor: '#1F2937',
                borderColor: '#4B5563',
                borderWidth: 1,
            }
        },
    };

    if (!data.wins && !data.losses) {
        return (
             <div className="bg-gray-800 p-6 rounded-lg shadow-lg h-full flex flex-col justify-center items-center">
                <h2 className="text-xl font-bold text-white mb-4">Win/Loss Ratio</h2>
                <p className="text-gray-500">Waiting for trade data...</p>
            </div>
        )
    }

    return (
        <div className="bg-gray-800 p-6 rounded-lg shadow-lg h-full flex flex-col justify-center items-center">
            <h2 className="text-xl font-bold text-white mb-4">Win/Loss Ratio</h2>
            <div className="relative w-full h-[250px]">
                 <Pie data={chartData} options={chartOptions} />
            </div>
        </div>
    );
};