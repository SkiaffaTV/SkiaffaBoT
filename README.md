# Pump Fun Bot

**WARNNING ON SCAMS IN ISSUES COMMENT SECTION**  
*The issues comment section is often targeted by scam bots willing to redirect you to an external resource and drain your funds. I have enabled a GitHub Actions script to detect common patterns and tag them, which obviously is not 100% accurate. This is also why you will see deleted comments in the issues—I only delete the scam bot comments targeting your private keys. The official maintainers are in the MAINTAINERS.md file. Not everyone is a scammer though, sometimes there are helpful outside devs who comment, and I absolutely appreciate it.*  

**END OF WARNING**

Development is ongoing in the `refactored/main-v2` branch. As of May 8, 2025, the bot from the `refactored/main-v2` branch is significantly improved over the main version, so the suggestion is to FAFO with v2. Leave your feedback by opening Issues.

**A word of warning: Not For Production (NFP)**  
This code is not intended for production use. Feel free to take the source, modify it to your needs, and most importantly, learn from it. We assume no responsibility for the code or its usage. This is our public service contribution to the community and Web3.

## Pump.fun Bot Development Roadmap

| Stage | Feature | Comments | Implementation Status |
|-------|---------|----------|-----------------------|
| **Stage 1: General updates & QoL** | | | |
| | Lib updates | Updating to the latest libraries | ✅ |
| | Error handling | Improving error handling (shutdown errors resolved on Windows) | ✅ |
| | Configurable RPS | Ability to set RPS in the config to match your provider's and plan RPS (preferably Chainstack 🤩) | WIP |
| | Dynamic priority fees | Ability to set dynamic priority fees | ✅ |
| | Review & optimize json, jsonParsed, base64 | Improve speed and traffic for calls, not just getBlock. Helpful overview | ✅ |
| | Cross-platform compatibility | Ensure bot stability on Windows and Linux (verified on Ubuntu) | ✅ |
| **Stage 2: Bonding curve and migration management** | | | |
| | logsSubscribe integration | Integrate logsSubscribe instead of blockSubscribe for sniping minted tokens into the main bot | ✅ |
| | Dual subscription methods | Keep both logsSubscribe & blockSubscribe in the main bot for flexibility and adapting to Solana node architecture changes | ✅ |
| | Transaction retries | Do retries instead of cooldown and/or keep the cooldown. Enhanced with detailed logging and specific error handling (e.g., blockhash not found) | ✅ |
| | Bonding curve status tracking | Checking a bonding curve status progress. Predict how soon a token will start the migration process. Added get_progress method and configurable progress thresholds | ✅ |
| | Account closure script | Script to close the associated bonding curve account if the rest of the flow txs fails | ✅ |
| | PumpSwap migration listening | Pump.fun migrated to their own DEX—PumpSwap, so we need to FAFO with that instead of Raydium (and attempt logSubscribe implementation) | ✅ |
| **Stage 3: Trading experience** | | | |
| | Take profit/stop loss | Implement take profit, stop loss exit strategies | ✅ (Implemented as FAFO, includes fixed-time sell) |
| | Market cap-based selling | Sell when a specific market cap has been reached | Not started |
| | Copy trading | Enable copy trading functionality | Not started |
| | Token analysis script | Script for basic token analysis (market cap, creator investment, liquidity, token age) | Not started |
| | Archive node integration | Use Solana archive nodes for historical analysis (accounts that consistently print tokens, average mint to Raydium time) | Not started |
| | Geyser implementation | Leverage Solana Geyser for real-time data stream processing | ✅ |
| | Multi Match String | Support for multiple match strings in token filtering | Not started |
| | Trailing Stop Loss | Implement trailing stop loss for dynamic exit strategies | Not started |
| **Stage 4: Minting experience** | | | |
| | Token minting | Ability to mint tokens (based on user request—someone minted 18k tokens) | FAFO |
| **Stage 5: Performance and analytics** | | | |
| | Enhanced Performance | Improve speed and efficiency of token detection and trading with `uvloop` for faster async event loop | WIP |
| | Price Impact Calculation | Calculate price impact for trades to optimize slippage | Not started |
| | Dynamic Buy Amount Adjustment | Adjust buy amount dynamically based on market conditions | Not started |
| | Parameter Optimization | Optimize bot parameters for better performance | Not started |
| **Stage 6: Learning examples** | | | |
| | Bonding curve state check | `check_bonding_curve_status.py` — checks the state of the bonding curve associated with a token | ✅ |
| | Raydium migration listener | `listen_to_raydium_migration.py` — listens to migration events from pump.fun to Raydium | ✅ |
| | Compute associated bonding curve | `compute_associated_bonding_curve.py` — computes the associated bonding curve for a given token | ✅ |
| | Listen new direct full details | `listen_new_direct_full_details.py` — listens to new token events using logsSubscribe and computes associated bonding curve address | ✅ |

## Development Timeline

- **Development begins**: Week of March 10, 2025
- **Implementation approach**: Gradual rollout in separate branch
- **Priority**: Stages progress from simple to complex features
- **Completion guarantee**: Full completion of Stage 1 and Stage 2 (achieved as of May 6, 2025), other stages dependent on feedback and feasibility

For the full walkthrough, see [Solana: Creating a trading and sniping pump.fun bot](https://docs.chainstack.com/docs/solana-creating-a-trading-and-sniping-pump-fun-bot). For near-instantaneous transaction propagation, you can use the [Chainstack Solana Trader nodes](https://chainstack.com/). Sign up with Chainstack.

## 🚀 Getting Started

### Prerequisites
Install `uv`, a fast Python package manager. If Python is already installed, `uv` will detect and use it automatically.

### Installation
1️⃣ **Install Python (if needed)**  
```bash
uv python install
```
*Why?* `uv` will fetch and install the required Python version for your system.

2️⃣ **Clone the repository**  
```bash
git clone https://github.com/chainstacklabs/pump-fun-bot.git
cd pump-fun-bot
```

3️⃣ **Set up a virtual environment**  
```bash
# Create virtual environment
uv venv

# Activate (Unix/macOS)
source .venv/bin/activate  

# Activate (Windows)
.venv\Scripts\activate
```
*Why?* Virtual environments help keep dependencies isolated and prevent conflicts.

4️⃣ **Install dependencies**  
```bash
uv pip install -e .
```
*Why `-e` (editable mode)?* Lets you modify the code without reinstalling the package—useful for development!

5️⃣ **Install `uvloop` for performance**  
```bash
uv pip install uvloop
```
*Why?* `uvloop` replaces the default asyncio event loop with a faster C-based implementation, improving bot performance.

6️⃣ **Configure the bot**  
```bash
# Copy example config
cp .env.example .env  # Unix/macOS
copy .env.example .env  # Windows
```
Edit the `.env` file and add your Solana RPC endpoints and private key. Example:
```bash
RPC_ENDPOINT=https://solana-mainnet.core.chainstack.com
WSS_ENDPOINT=wss://solana-mainnet.core.chainstack.com
PRIVATE_KEY=your_private_key_here
```
Edit `config.yaml` to set trading parameters. Example:
```yaml
trade_settings:
  buy_amount: 0.001
  buy_slippage: 0.25
  sell_slippage: 0.25
  min_progress_to_buy: 5.0
  max_progress_to_buy: 40.0
```

### Running the Bot
```bash
# Option 1: run as installed package
pump_bot --help

# Option 2: run directly
python -m src.cli --help
```
You're all set! 🎉 Logs are saved in the `logs/` directory (e.g., `logs/bot-sniper-2_YYYYMMDD_HHMMSS.log`).

## New Features

### Robust Transaction Confirmation
- **Description**: Improved transaction confirmation in `client.py` to prevent false positives (e.g., transactions reported as confirmed despite failing due to slippage).
- **Implementation**: Added `get_signature_statuses` to `confirm_transaction`, checking `status.err` for errors like `TooMuchSolRequired` (error code 6002).
- **Usage**: Ensures accurate reporting of transaction outcomes in logs. Monitor logs for errors like:
  ```
  2025-05-08 12:34:56 - core.client - ERROR - Transaction 5y...xZ failed: {'InstructionError': [4, 'Custom: 6002']}
  ```

### Enhanced ATA Handling
- **Description**: Added explicit Associated Token Account (ATA) creation in `buyer.py` and robust ATA verification in `seller.py`.
- **Implementation**:
  - `buyer.py`: Creates ATAs before buying using `spl.token.instructions.create_associated_token_account`.
  - `seller.py`: Increased ATA synchronization timeout to 20 seconds and retry attempts to 5, with detailed logging.
- **Configuration**: No changes needed; uses existing `config.yaml` settings.
- **Usage**: Reduces "ATA not found" errors on slow RPC nodes (e.g., Chainstack). Check logs for:
  ```
  2025-05-08 12:34:56 - trading.seller - INFO - Waiting 20 seconds for RPC node to synchronize ATA...
  2025-05-08 12:35:16 - trading.seller - DEBUG - ATA 4sdu8x...yzdx3x found on attempt 1/5
  ```

### Slippage Adjustment
- **Description**: Increased default slippage to 25% to handle rapid bonding curve movements.
- **Configuration**: Set in `config.yaml`:
  ```yaml
  trade_settings:
    buy_slippage: 0.25
    sell_slippage: 0.25
  ```
- **Usage**: Reduces transaction failures due to `TooMuchSolRequired`. Verify in logs:
  ```
  2025-05-08 12:34:56 - trading.buyer - INFO - Minimum token output (with 25.0% slippage): 12345.678901 tokens
  ```

## Performance Optimization

### uvloop Integration
- **Description**: Added support for `uvloop`, a high-performance replacement for the default asyncio event loop.
- **Installation**:
  ```bash
  uv pip install uvloop
  ```
- **Usage**: Automatically used when installed, improving async operation speed. Verify:
  ```bash
  uv pip list | grep uvloop
  ```
  Check logs for absence of:
  ```
  INFO:trading.trader:uvloop not available, using default asyncio event loop
  ```

### VM Configuration
- **Description**: Optimized VM settings for better bot performance.
- **Recommendations**:
  - **CPU**: Minimum 2 cores, recommended 4 cores for concurrent RPC calls and WebSocket monitoring.
  - **RAM**: Minimum 4 GB, recommended 8 GB for Python async operations and logging.
  - **Network**: Low-latency connection to Solana RPC node (<100ms ping). Test:
    ```bash
    ping wss.solana-mainnet.core.chainstack.com
    ```
    Consider QuickNode or Alchemy if latency is high or WebSocket reconnections occur.
  - **Storage**: At least 10 GB for logs and dependencies.
- **Verification**:
  ```bash
  lscpu
  free -m
  ```

## Note on Limits
Solana is an amazing piece of Web3 architecture, but it's also complex to maintain. Chainstack is daily (literally, including weekends) working on optimizing our Solana infrastructure to make it the best in the industry. That said, all node providers have their own setup recommendations & limits, like method availability, requests per second (RPS), free and paid plan-specific limitations, and so on. Please consult the docs of your node provider. For Chainstack, all details and limits are consolidated here: [Limits](https://docs.chainstack.com/docs/limits). Public RPC nodes won't work for heavy use cases like this bot.

## Changelog
- **May 8, 2025**:
  - **Fixed False Transaction Confirmations**:
    - Updated `client.py` to use `get_signature_statuses` in `confirm_transaction`, checking `status.err` to detect errors like slippage (`custom program error: 6002`).
    - Resolves issue where failed transactions (e.g., token "AW") were reported as confirmed.
  - **Resolved `ImportError` in `buyer.py`**:
    - Replaced `solders.token.create_associated_token_account_instruction` with `spl.token.instructions.create_associated_token_account` to fix import error.
    - Ensured compatibility with existing `solana-py` and `spl-token` dependencies.
  - **Enhanced ATA Handling**:
    - `buyer.py`: Added explicit ATA creation before buying to prevent "ATA not found" errors.
    - `seller.py`: Increased ATA sync timeout to 20 seconds and retries to 5, with improved error handling for `ValueError` from `get_account_info`.
  - **Slippage Adjustment**:
    - Set default `buy_slippage` and `sell_slippage` to 0.25 in `config.yaml` to reduce `TooMuchSolRequired` errors.
  - **Performance Optimization**:
    - Added `uvloop` installation instructions to improve async event loop performance.
    - Provided VM optimization guidelines (CPU, RAM, network) to minimize latency and WebSocket reconnections.
  - **Documentation**:
    - Updated `READMESkiaffaTVv2.md` with new features, performance optimizations, and troubleshooting tips.

## Troubleshooting
- **ImportError for `solders.token`**:
  - Ensure `solders` is up-to-date:
    ```bash
    uv pip install solders --upgrade
    ```
  - Verify `spl-token` is installed:
    ```bash
    uv pip install spl-token
    ```

- **"ATA not found" Errors**:
  - Increase the synchronization timeout in `seller.py` (e.g., to 30 seconds) if using a slow RPC node.
  - Check node latency:
    ```bash
    ping wss.solana-mainnet.core.chainstack.com
    ```
  - Switch to QuickNode or Alchemy if issues persist.

- **WebSocket Reconnections**:
  - Monitor logs for:
    ```
    WARNING:monitoring.logs_listener:WebSocket connection closed
    ```
  - Upcoming `logs_listener.py` update will add exponential backoff for reconnections.

- **Slippage Errors**:
  - Ensure `buy_slippage` and `sell_slippage` are set to 0.25 in `config.yaml`.
  - Monitor logs for:
    ```
    ERROR:core.client - Transaction ... failed: {'InstructionError': [4, 'Custom: 6002']}
    ```

- **Slow Performance**:
  - Install `uvloop`:
    ```bash
    uv pip install uvloop
    ```
  - Verify VM resources:
    ```bash
    lscpu
    free -m
    ```

## Contributing
Contributions are welcome! Please submit pull requests or open issues on the [GitHub repository](https://github.com/chainstacklabs/pump-fun-bot).

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.