import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def analyze_trades(trades_file: str) -> None:
    """
    Analyze trades from trades.log and print statistics.
    
    Args:
        trades_file: Path to trades.log
    """
    trades = []
    try:
        with open(trades_file, "r") as f:
            for line in f:
                trades.append(json.loads(line.strip()))
    except FileNotFoundError:
        print(f"Error: {trades_file} not found")
        return
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {trades_file}: {e}")
        return

    # Group trades by token_address
    token_trades = defaultdict(list)
    for trade in trades:
        token_trades[trade["token_address"]].append(trade)

    total_profit = 0.0
    successful_trades = 0
    failed_sales = 0
    token_stats = []

    for token_address, trades in token_trades.items():
        buy_trade = None
        sell_trade = None
        for trade in trades:
            if trade["action"] == "buy":
                buy_trade = trade
            elif trade["action"] == "sell":
                sell_trade = trade
            elif trade["action"] == "sell_failed":
                failed_sales += 1

        if buy_trade and sell_trade:
            buy_cost = buy_trade["amount"] * buy_trade["price"]
            sell_revenue = sell_trade["amount"] * sell_trade["price"]
            profit = sell_revenue - buy_cost
            profit_percentage = (profit / buy_cost) * 100 if buy_cost > 0 else 0

            token_stats.append({
                "symbol": buy_trade["symbol"],
                "token_address": token_address,
                "buy_price": buy_trade["price"],
                "sell_price": sell_trade["price"],
                "amount": buy_trade["amount"],
                "profit": profit,
                "profit_percentage": profit_percentage,
                "buy_time": buy_trade["timestamp"],
                "sell_time": sell_trade["timestamp"],
                "reason": sell_trade.get("reason", "Unknown")
            })

            total_profit += profit
            successful_trades += 1

    # Print statistics
    print(f"\nTrade Analysis for {trades_file}")
    print(f"Total Trades: {successful_trades}")
    print(f"Failed Sales: {failed_sales}")
    print(f"Total Profit/Loss: {total_profit:.9f} SOL")
    print("\nPer-Token Statistics:")
    print("-" * 80)
    print(f"{'Symbol':<10} {'Profit (SOL)':<12} {'Profit %':<10} {'Buy Price':<15} {'Sell Price':<15} {'Reason':<15} {'Buy Time'}")
    print("-" * 80)

    for stat in sorted(token_stats, key=lambda x: x["profit"], reverse=True):
        print(
            f"{stat['symbol']:<10} "
            f"{stat['profit']:<12.9f} "
            f"{stat['profit_percentage']:<10.2f}% "
            f"{stat['buy_price']:<15.9f} "
            f"{stat['sell_price']:<15.9f} "
            f"{stat['reason']:<15} "
            f"{stat['buy_time']}"
        )

if __name__ == "__main__":
    trades_file = "trades/trades.log"
    analyze_trades(trades_file)