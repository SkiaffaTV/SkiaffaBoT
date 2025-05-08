Getting Started with Pump.fun Trading Bot
This guide provides step-by-step instructions to set up and run the pump-fun-bot, a trading bot designed for sniping and trading tokens on the pump.fun platform using Solana. The bot is developed in the refactored/main-v2 branch of the repository (GitHub) and is not intended for production use (Not For Production - NFP).
Prerequisites
Before starting, ensure you have the following:

Python 3.8+: The bot requires Python 3.8 or higher. Download it from python.org if not already installed.
uv Package Manager: A fast Python package manager to manage dependencies and virtual environments. Install it using:curl -LsSf https://astral.sh/uv/install.sh | sh

Alternatively, follow the instructions at uv documentation.
Git: Required to clone the repository. Install it from git-scm.com or your package manager (e.g., apt install git on Ubuntu, brew install git on macOS).
Solana Node Access: You need access to a Solana RPC and WebSocket endpoint. Recommended: Chainstack Solana Trader nodes for near-instantaneous transaction propagation. Public RPC nodes are not suitable for this bot due to rate limits and reliability issues.
Solana Wallet: A Solana wallet with a private key for signing transactions. Ensure the wallet has sufficient SOL for trading and transaction fees.
Operating System: The bot is tested on Windows and Ubuntu (Linux). macOS should work but is not officially verified.

Installation
Follow these steps to set up the bot:
1. Install Python (if needed)
If Python 3.8+ is not installed, use uv to install it:
uv python install

This command fetches and installs a compatible Python version for your system. Verify the installation:
python --version

2. Clone the Repository
Clone the pump-fun-bot repository from GitHub:
git clone https://github.com/chainstacklabs/pump-fun-bot.git
cd pump-fun-bot

Switch to the refactored/main-v2 branch:
git checkout refactored/main-v2

3. Set Up a Virtual Environment
Create and activate a virtual environment to isolate dependencies:
# Create virtual environment
uv venv

# Activate (Unix/macOS)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

Why? Virtual environments prevent conflicts between project dependencies and system-wide packages.
4. Install Dependencies
Install the bot's dependencies in editable mode:
uv pip install -e .

Why -e (editable mode)? Allows you to modify the code without reinstalling the package, useful for development and debugging.
5. Configure the Bot
The bot requires configuration files to specify Solana endpoints, wallet details, and trading parameters.
Configure .env
Copy the example environment file:
# Unix/macOS
cp .env.example .env

# Windows
copy .env.example .env

Edit .env with your Solana RPC and WebSocket endpoints, private key, and optional Geyser settings. Example:
SOLANA_NODE_RPC_ENDPOINT=https://your-chainstack-rpc-endpoint
SOLANA_NODE_WSS_ENDPOINT=wss://your-chainstack-wss-endpoint
SOLANA_PRIVATE_KEY=your-solana-private-key
GEYSER_ENDPOINT=https://your-geyser-endpoint
GEYSER_API_TOKEN=your-geyser-api-token

Notes:

Obtain endpoints from your node provider (e.g., Chainstack). Public endpoints are not recommended.
Keep your private key secure and never share it.
Geyser settings are optional unless using the "geyser" listener type.

Configure bot-sniper-2-logs.yaml
The bot uses a YAML configuration file (bots/bot-sniper-2-logs.yaml) for trading parameters. Review and adjust the settings to match your strategy:
nano bots/bot-sniper-2-logs.yaml  # Unix/macOS
notepad bots\bot-sniper-2-logs.yaml  # Windows

Key parameters to configure:

trade.buy_amount: Amount of SOL to spend per trade (default: 0.001).
trade.buy_slippage and sell_slippage: Slippage tolerance (default: 0.15 = 15%).
filters.listener_type: Method for detecting tokens ("logs", "blocks", or "geyser"; default: "logs").
trade.min_progress_to_buy and max_progress_to_buy: Bonding curve progress range for buying (default: 0.0 to 100.0%).
trade.enable_progress_sell and progress_sell_threshold: Enable selling based on bonding curve progress (default: false, 95.0%).
retries.max_attempts: Number of transaction retry attempts (default: 3).

Example configuration for an "Early Bird" strategy:
trade:
  buy_amount: 0.002
  buy_slippage: 0.15
  sell_slippage: 0.15
  min_progress_to_buy: 0.0
  max_progress_to_buy: 20.0
  enable_progress_sell: true
  progress_sell_threshold: 90.0
  enable_take_profit: true
  take_profit_percentage: 0.50
  stop_loss_percentage: 0.15
filters:
  listener_type: "logs"
retries:
  max_attempts: 5

Notes:

Ensure enabled: true in the YAML file to run the bot.
Adjust parameters based on your risk tolerance and node provider limits.

Running the Bot
Once configured, you can run the bot in two ways:
Option 1: Run as Installed Package
pump_bot --help

This command shows available options. To start the bot with the default configuration (bots/bot-sniper-2-logs.yaml):
pump_bot

Option 2: Run Directly
python -m src.cli --help

Start the bot:
python -m src.cli

Notes:

The bot will load the configuration from bots/bot-sniper-2-logs.yaml and .env.
Logs are saved in the logs directory with filenames like bot-sniper-2_YYYYMMDD_HHMMSS.log.
Use Ctrl+C to stop the bot gracefully.

Monitoring and Debugging

Logs: Check the log files in the logs directory for detailed information on token detection, trades, and transaction attempts. Example log entry:2025-05-06 12:34:56 - trading.seller - INFO - Transaction sell attempt 1/3 for token XYZ: Success, signature: 5y...xZ
2025-05-06 12:34:58 - trading.buyer - WARNING - Transaction buy attempt 2/3 for token ABC: Failed, error: blockhash not found


Trade Logs: Trade details (buy/sell actions, prices, amounts) are saved in trades/trades.log.
Common Issues:
"blockhash not found": The bot automatically retries with a fresh blockhash. Check logs to confirm.
Rate limits: Ensure your node provider (e.g., Chainstack) supports the required RPS (default: 25 in bot-sniper-2-logs.yaml).
Insufficient SOL: Verify your wallet has enough SOL for trades and fees.


Debugging: If the bot fails to detect tokens or execute trades, check:
Correctness of RPC/WebSocket endpoints in .env.
Validity of the private key.
Configuration parameters in bot-sniper-2-logs.yaml (e.g., listener_type, max_token_age).



Notes on Solana Node Limits
Solana is a complex blockchain with high-performance requirements. Node providers impose limits on:

Requests per Second (RPS): Ensure your plan supports at least 25 RPS (configurable in node.max_rps).
Method Availability: Some providers may not support blockSubscribe (used in "blocks" listener type). The default "logs" listener uses logsSubscribe, which is widely supported.
Plan Limitations: Free or low-tier plans may have restrictions unsuitable for trading bots.

For optimal performance, use Chainstack Solana Trader nodes. Check their Limits documentation for details on RPS, methods, and plan-specific constraints.
Warning: Public RPC nodes (e.g., api.mainnet-beta.solana.com) are unreliable for trading bots due to rate limits and latency. Avoid using them.
Additional Resources

Repository: https://github.com/chainstacklabs/pump-fun-bot/tree/refactored/main-v2
File Updates: Latest files are available on Google Drive.
Documentation: Solana: Creating a trading and sniping pump.fun bot.
Support: Open issues on GitHub for feedback or questions. Be cautious of scam bots in the issues section (see README for details).

Troubleshooting

Bot not starting: Verify Python version (python --version), virtual environment activation, and dependency installation (uv pip list).
No tokens detected: Check filters.listener_type and max_token_age in bot-sniper-2-logs.yaml. Ensure WebSocket endpoint is correct.
Transaction failures: Monitor logs for errors like "blockhash not found" or "insufficient funds". Increase retries.max_attempts if needed.
Performance issues: Reduce node.max_rps or contact your node provider to upgrade your plan.

You're all set to start trading with the pump-fun-bot! 🎉
