

WARNNING ON SCAMS IN ISSUES COMMENT SECTION<<The issues comment section is often targeted by scam bots willing to redirect you to an external resource and drain your funds.I have enabled a GitHub actions script to detect the common patterns and tag them, which obviously is not 100% accurate.This is also why you will see deleted comments in the issues—I only delete the scam bot comments targeting your private keys.The official maintainers are in the MAINTAINERS.md file.Not everyone is a scammer though, sometimes there are helpful outside devs who comment and I absolutely appreciate it.

END OF WARNING<<



Development ongoing in the refactored/main-v2 branch.As of May 6, 2025, the bot from the refactored/main-v2 branch is significantly better over the main version, so the suggestion is to FAFO with v2.Leave your feedback by opening Issues.
A word of warning:Not For Production (NFP)This code is not intended for production use. Feel free to take the source, modify it to your needs, and most importantly, learn from it.We assume no responsibility for the code or its usage. This is our public service contribution to the community and Web3.
Pump.fun bot development roadmap



Stage
Feature
Comments
Implementation status



Stage 1: General updates & QoL
Lib updates
Updating to the latest libraries
✅



Error handling
Improving error handling (shutdown errors resolved on Windows)
✅



Configurable RPS
Ability to set RPS in the config to match your provider's and plan RPS (preferably Chainstack 🤩)
WIP



Dynamic priority fees
Ability to set dynamic priority fees
✅



Review & optimize json, jsonParsed, base64
Improve speed and traffic for calls, not just getBlock. Helpful overview
✅



Cross-platform compatibility
Ensure bot stability on Windows and Linux (verified on Ubuntu)
✅


Stage 2: Bonding curve and migration management
logsSubscribe integration
Integrate logsSubscribe instead of blockSubscribe for sniping minted tokens into the main bot
✅



Dual subscription methods
Keep both logsSubscribe & blockSubscribe in the main bot for flexibility and adapting to Solana node architecture changes
✅



Transaction retries
Do retries instead of cooldown and/or keep the cooldown. Enhanced with detailed logging and specific error handling (e.g., blockhash not found)
✅



Bonding curve status tracking
Checking a bonding curve status progress. Predict how soon a token will start the migration process. Added get_progress method and configurable progress thresholds
✅



Account closure script
Script to close the associated bonding curve account if the rest of the flow txs fails
✅



PumpSwap migration listening
pump_fun migrated to their own DEX — PumpSwap, so we need to FAFO with that instead of Raydium (and attempt logSubscribe implementation)
✅


Stage 3: Trading experience
Take profit/stop loss
Implement take profit, stop loss exit strategies
✅ (Implemented as FAFO, includes fixed-time sell)



Market cap-based selling
Sell when a specific market cap has been reached
Not started



Copy trading
Enable copy trading functionality
Not started



Token analysis script
Script for basic token analysis (market cap, creator investment, liquidity, token age)
Not started



Archive node integration
Use Solana archive nodes for historical analysis (accounts that consistently print tokens, average mint to raydium time)
Not started



Geyser implementation
Leverage Solana Geyser for real-time data stream processing
✅



Multi Match String
Support for multiple match strings in token filtering
Not started



Trailing Stop Loss
Implement trailing stop loss for dynamic exit strategies
Not started


Stage 4: Minting experience
Token minting
Ability to mint tokens (based on user request - someone minted 18k tokens)
FAFO


Stage 5: Performance and analytics
Enhanced Performance
Improve speed and efficiency of token detection and trading
Not started



Price Impact Calculation
Calculate price impact for trades to optimize slippage
Not started



Dynamic Buy Amount Adjustment
Adjust buy amount dynamically based on market conditions
Not started



Parameter Optimization
Optimize bot parameters for better performance
Not started


Stage 6: Learning examples
Bonding curve state check
check_boding_curve_status.py — checks the state of the bonding curve associated with a token
✅



Raydium migration listener
listen_to_raydium_migration.py — listens to migration events from pump_fun to Raydium
✅



Compute associated bonding curve
compute_associated_bonding_curve.py — computes the associated bonding curve for a given token
✅



Listen new direct full details
listen_new_direct_full_details.py — listens to new token events using logsSubscribe and computes associated bonding curve address
✅


Development Timeline

Development begins: Week of March 10, 2025
Implementation approach: Gradual rollout in separate branch
Priority: Stages progress from simple to complex features
Completion guarantee: Full completion of Stage 1 and Stage 2 (achieved as of May 6, 2025), other stages dependent on feedback and feasibility

For the full walkthrough, see Solana: Creating a trading and sniping pump.fun bot.For near-instantaneous transaction propagation, you can use the Chainstack Solana Trader nodes.Sign up with Chainstack.
🚀 Getting started
Prerequisites
Install uv, a fast Python package manager.
If Python is already installed, uv will detect and use it automatically.
Installation
1️⃣ Install Python (if needed)  
uv python install

Why? uv will fetch and install the required Python version for your system.
2️⃣ Clone the repository  
git clone https://github.com/chainstacklabs/pump-fun-bot.git
cd pump-fun-bot

3️⃣ Set up a virtual environment  
# Create virtual environment
uv venv

# Activate (Unix/macOS)
source .venv/bin/activate  

# Activate (Windows)
.venv\Scripts\activate

Why? Virtual environments help keep dependencies isolated and prevent conflicts.
4️⃣ Install dependencies  
uv pip install -e .

Why -e (editable mode)? Lets you modify the code without reinstalling the package—useful for development!
5️⃣ Configure the bot  
# Copy example config
cp .env.example .env  # Unix/macOS

# Windows
copy .env.example .env

Edit the .env file and add your Solana RPC endpoints and private key.
Running the bot
# Option 1: run as installed package
pump_bot --help

# Option 2: run directly
python -m src.cli --help

You're all set! 🎉 Now you can start using the bot. Check --help for available commands. 🚀
New Features
Bonding Curve Progress Tracking

Description: The bot now tracks the progress of a token's bonding curve using the get_progress method in curve.py. Progress is calculated as 1 - (real_token_reserves / INITIAL_REAL_TOKEN_RESERVES), where INITIAL_REAL_TOKEN_RESERVES is set to 793100000000000.
Configuration: Added new parameters in bot-sniper-2-logs.yaml under the trade section:
min_progress_to_buy: Minimum bonding curve progress (%) to buy a token (default: 0.0).
max_progress_to_buy: Maximum bonding curve progress (%) to buy a token (default: 100.0).
enable_progress_sell: Enable selling based on bonding curve progress (default: false).
progress_sell_threshold: Progress threshold (%) to trigger a sell (default: 95.0).


Usage: Configure these parameters to filter tokens by their bonding curve progress or sell when nearing migration to Raydium (e.g., 95% progress). Example:trade:
  min_progress_to_buy: 10.0
  max_progress_to_buy: 50.0
  enable_progress_sell: true
  progress_sell_threshold: 90.0


Integration: The bot checks progress before buying (in trader.py) and during monitoring (with Take Profit/Stop Loss), allowing strategies like buying early-stage tokens or selling pre-migration.

Enhanced Transaction Retries

Description: Transaction retries in buyer.py and seller.py now include detailed logging and specific error handling (e.g., refreshing blockhash for "blockhash not found" errors).
Logging: Uses log_transaction_attempt in logger.py to record each attempt, including attempt number, success/failure, error message, and transaction signature.
Configuration: Controlled by retries.max_attempts in bot-sniper-2-logs.yaml (default: 3).
Usage: Monitor logs in the logs directory to debug transaction issues. Example log:2025-05-06 12:34:56 - trading.seller - INFO - Transaction sell attempt 1/3 for token XYZ: Success, signature: 5y...xZ
2025-05-06 12:34:58 - trading.buyer - WARNING - Transaction buy attempt 2/3 for token ABC: Failed, error: blockhash not found



Note on limits
Solana is an amazing piece of web3 architecture, but it's also very complex to maintain.Chainstack is daily (literally, including weekends) working on optimizing our Solana infrastructure to make it the best in the industry.That said, all node providers have their own setup recommendations & limits, like method availability, requests per second (RPS), free and paid plan specific limitations and so on.So please make sure you consult the docs of the node provider you are going to use for the bot here. And obviously the public RPC nodes won't work for the heavier use case scenarios like this bot.For Chainstack, all of the details and limits you need to be aware of are consolidated here: Limits <— we are always keeping this piece up to date so you can rely on it.
Changelog
Quick note on a couple of new scripts in /learning-examples:(this is basically a changelog now)Also, here's a quick doc: Listening to pump.fun migrations to Raydium
Bonding curve state check
check_boding_curve_status.py — checks the state of the bonding curve associated with a token. When the bonding curve state is completed, the token is migrated to Raydium.To run:
python check_boding_curve_status.py TOKEN_ADDRESS

Listening to the Raydium migration
When the bonding curve state completes, the liquidity and the token graduate to Raydium.listen_to_raydium_migration.py — listens to the migration events of the tokens from pump_fun to Raydium and prints the signature of the migration, the token address, and the liquidity pool address on Raydium.Note that it's using the blockSubscribe method that not all providers support, but Chainstack does and I (although obviously biased) found it pretty reliable.To run:
python listen_to_raydium_migration.py

The following two new additions are based on this question associatedBondingCurve #26You can take the compute the associatedBondingCurve address following the Solana docs PDA description logic. Take the following as input as seed (order seems to matter):

bondingCurve address
the Solana system token program address: TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA
the token mint address

And compute against the Solana system associated token account program address: ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL.The implications of this are kinda huge:

you can now use logsSubscribe to snipe the tokens and you are not limited to the blockSubscribe method
see which one is faster
not every provider supports blockSubscribe on lower tier plans or at all, but everyone supports logsSubscribe

The following script showcase the implementation.
Compute associated bonding curve
compute_associated_bonding_curve.py — computes the associated bonding curve for a given token.To run:
python compute_associated_bonding_curve.py

and then enter the token mint address.
Listen to new direct full details
listen_new_direct_full_details.py — listens to the new direct full details events and prints the signature, the token address, the user, the bonding curve address, and the associated bonding curve address using just the logsSubscribe method. Basically everything you need for sniping using just logsSubscribe and no extra calls like doing getTransaction to get the missing data. It's just computed on the fly now.To run:
python listen_new_direct_full_details.py

So now you can run listen_create_from_blocksubscribe.py and listen_new_direct_full_details.py at the same time and see which one is faster.Also here's a doc on this: Solana: Listening to pump.fun token mint using only logsSubscribe
