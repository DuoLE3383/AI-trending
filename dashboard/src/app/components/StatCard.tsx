'use client';

// Giao diện (interface) cho props
interface StatCardProps {
    title: string;
    value: string | number;
    unit?: string;
    icon: string;
    color: string;
}

const StatCard = ({ title, value, unit, icon, color }: StatCardProps) => (
    <div className="bg-gray-800 p-6 rounded-lg shadow-lg flex items-center">
        <div className={`text-4xl mr-4 ${color}`}>{icon}</div>
        <div>
            <div className="text-sm text-gray-400">{title}</div>
            <div className="text-2xl font-bold text-white">{value}{unit}</div>
        </div>
    </div>
);

export default StatCard;
