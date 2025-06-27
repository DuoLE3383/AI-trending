export interface Stats {
    win_rate: number;
    total_completed_trades: number;
    wins: number;
    losses: number;
}

export interface Trade {
    symbol: string;
    status: string;
    pnl_percent?: number;
    trend?: string;
    entry_price?: number;
}