"""
Sell operations for pump.fun tokens.
"""

import struct
import asyncio
import logging
from typing import Final

from solders.instruction import AccountMeta, Instruction
from solders.pubkey import Pubkey

from core.client import SolanaClient
from core.curve import BondingCurveManager
from core.priority_fee.manager import PriorityFeeManager
from core.pubkeys import (
    LAMPORTS_PER_SOL,
    TOKEN_DECIMALS,
    PumpAddresses,
    SystemAddresses,
)
from core.wallet import Wallet
from trading.base import TokenInfo, Trader, TradeResult
from utils.logger import get_logger, log_transaction_attempt

# Set httpx logging level to WARNING to reduce noise
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = get_logger(__name__)

# Discriminator for the sell instruction
EXPECTED_DISCRIMINATOR: Final[bytes] = struct.pack("<Q", 12502976635542562355)

class TokenSeller(Trader):
    """Handles selling tokens on pump.fun."""

    def __init__(
        self,
        client: SolanaClient,
        wallet: Wallet,
        curve_manager: BondingCurveManager,
        priority_fee_manager: PriorityFeeManager,
        slippage: float = 0.25,
        max_retries: int = 5,
    ):
        """Initialize token seller.

        Args:
            client: Solana client for RPC calls
            wallet: Wallet for signing transactions
            curve_manager: Bonding curve manager
            slippage: Slippage tolerance (0.25 = 25%)
            max_retries: Maximum number of retry attempts
        """
        self.client = client
        self.wallet = wallet
        self.curve_manager = curve_manager
        self.priority_fee_manager = priority_fee_manager
        self.slippage = slippage
        self.max_retries = max_retries

    def _get_relevant_accounts(self, token_info: TokenInfo) -> list[Pubkey]:
        """Get accounts relevant for priority fee calculation."""
        return [token_info.mint, token_info.bonding_curve]

    async def execute(self, token_info: TokenInfo, *args, **kwargs) -> TradeResult:
        """Execute sell operation.

        Args:
            token_info: Token information

        Returns:
            TradeResult with sell outcome
        """
        try:
            # Get associated token account
            associated_token_account = self.wallet.get_associated_token_address(
                token_info.mint
            )
            logger.debug(f"Calculating ATA for mint: {token_info.mint}")
            logger.debug(f"ATA calculated: {associated_token_account}")

            # Wait for node synchronization
            logger.info("Waiting 10 seconds for RPC node to synchronize ATA...")
            await asyncio.sleep(10)

            # Check if ATA exists with retries
            account_info = None
            for attempt in range(3):
                try:
                    account_info = await self.client.get_account_info(associated_token_account)
                    if account_info is None:
                        logger.warning(f"ATA {associated_token_account} not found on attempt {attempt + 1}/3")
                        await asyncio.sleep(2)
                        continue
                    logger.debug(f"ATA {associated_token_account} found on attempt {attempt + 1}/3")
                    break
                except Exception as e:
                    logger.warning(f"Failed to fetch ATA {associated_token_account} on attempt {attempt + 1}/3: {str(e)}")
                    await asyncio.sleep(2)
            if account_info is None:
                logger.error(f"Associated token account {associated_token_account} does not exist after 3 attempts")
                return TradeResult(
                    success=False,
                    error_message=f"Account {associated_token_account} not found",
                    amount=0,
                    price=0,
                    tx_signature=None,
                )

            # Get token balance
            token_balance = await self.client.get_token_account_balance(
                associated_token_account
            )
            token_balance_decimal = token_balance / 10**TOKEN_DECIMALS
            logger.debug(f"ATA {associated_token_account} balance: {token_balance_decimal} tokens")

            logger.info(f"Token balance: {token_balance_decimal}")

            if token_balance == 0:
                logger.info("No tokens to sell.")
                return TradeResult(
                    success=False,
                    error_message="No tokens to sell",
                    amount=0,
                    price=0,
                    tx_signature=None,
                )

            # Fetch token price
            curve_state = await self.curve_manager.get_curve_state(
                token_info.bonding_curve
            )
            token_price_sol = curve_state.calculate_price()

            logger.info(f"Price per Token: {token_price_sol:.8f} SOL")

            # Calculate minimum SOL output with slippage
            amount = token_balance
            expected_sol_output = float(token_balance_decimal) * float(token_price_sol)
            slippage_factor = 1 - self.slippage
            min_sol_output = int(
                (expected_sol_output * slippage_factor) * LAMPORTS_PER_SOL
            )

            logger.info(f"Selling {token_balance_decimal} tokens")
            logger.info(f"Expected SOL output: {expected_sol_output:.8f} SOL")
            logger.info(
                f"Minimum SOL output (with {self.slippage * 100}% slippage): {min_sol_output / LAMPORTS_PER_SOL:.8f} SOL"
            )

            tx_signature = await self._send_sell_transaction(
                token_info,
                associated_token_account,
                amount,
                min_sol_output,
            )

            success = await self.client.confirm_transaction(tx_signature)

            if success:
                logger.info(f"Sell transaction confirmed: {tx_signature}")
                return TradeResult(
                    success=True,
                    tx_signature=tx_signature,
                    amount=token_balance_decimal,
                    price=token_price_sol,
                    error_message=None,
                )
            else:
                return TradeResult(
                    success=False,
                    error_message=f"Transaction failed to confirm: {tx_signature}",
                    amount=token_balance_decimal,
                    price=token_price_sol,
                    tx_signature=tx_signature,
                )

        except Exception as e:
            logger.error(f"Sell operation failed: {str(e)}")
            return TradeResult(
                success=False,
                error_message=str(e),
                amount=0,
                price=0,
                tx_signature=None,
            )

    async def _send_sell_transaction(
        self,
        token_info: TokenInfo,
        associated_token_account: Pubkey,
        token_amount: int,
        min_sol_output: int,
    ) -> str:
        """Send sell transaction with retries and error handling.

        Args:
            token_info: Token information
            associated_token_account: User's token account
            token_amount: Amount of tokens to sell in raw units
            min_sol_output: Minimum SOL to receive in lamports

        Returns:
            Transaction signature

        Raises:
            Exception: If all retry attempts fail
        """
        # Prepare sell instruction accounts
        accounts = [
            AccountMeta(
                pubkey=PumpAddresses.GLOBAL, is_signer=False, is_writable=False
            ),
            AccountMeta(pubkey=PumpAddresses.FEE, is_signer=False, is_writable=True),
            AccountMeta(pubkey=token_info.mint, is_signer=False, is_writable=False),
            AccountMeta(
                pubkey=token_info.bonding_curve, is_signer=False, is_writable=True
            ),
            AccountMeta(
                pubkey=token_info.associated_bonding_curve,
                is_signer=False,
                is_writable=True,
            ),
            AccountMeta(
                pubkey=associated_token_account, is_signer=False, is_writable=True
            ),
            AccountMeta(pubkey=self.wallet.pubkey, is_signer=True, is_writable=True),
            AccountMeta(
                pubkey=SystemAddresses.PROGRAM, is_signer=False, is_writable=False
            ),
            AccountMeta(
                pubkey=SystemAddresses.ASSOCIATED_TOKEN_PROGRAM,
                is_signer=False,
                is_writable=False,
            ),
            AccountMeta(
                pubkey=SystemAddresses.TOKEN_PROGRAM, is_signer=False, is_writable=False
            ),
            AccountMeta(
                pubkey=PumpAddresses.EVENT_AUTHORITY, is_signer=False, is_writable=False
            ),
            AccountMeta(
                pubkey=PumpAddresses.PROGRAM, is_signer=False, is_writable=False
            ),
        ]

        # Prepare sell instruction data
        data = (
            EXPECTED_DISCRIMINATOR
            + struct.pack("<Q", token_amount)
            + struct.pack("<Q", min_sol_output)
        )
        sell_ix = Instruction(PumpAddresses.PROGRAM, data, accounts)

        # Calculate base priority fee
        base_priority_fee = await self.priority_fee_manager.calculate_priority_fee(
            self._get_relevant_accounts(token_info)
        )

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                # Increase priority fee with each attempt (20% more per attempt)
                priority_fee = base_priority_fee * (1 + 0.2 * (attempt - 1))
                tx_signature = await self.client.build_and_send_transaction(
                    [sell_ix],
                    self.wallet.keypair,
                    skip_preflight=True,
                    max_retries=1,  # Handle retries manually
                    priority_fee=int(priority_fee),
                )
                log_transaction_attempt(
                    logger,
                    action="sell",
                    attempt=attempt,
                    max_attempts=self.max_retries,
                    success=True,
                    token_symbol=token_info.symbol,
                    tx_signature=tx_signature
                )
                return tx_signature

            except Exception as e:
                last_error = str(e)
                log_transaction_attempt(
                    logger,
                    action="sell",
                    attempt=attempt,
                    max_attempts=self.max_retries,
                    success=False,
                    error=last_error,
                    token_symbol=token_info.symbol
                )

                # Handle specific errors
                if "blockhash not found" in last_error.lower():
                    logger.info("Blockhash not found, refreshing blockhash for retry...")
                    # Refresh blockhash by forcing a new priority fee calculation
                    base_priority_fee = await self.priority_fee_manager.calculate_priority_fee(
                        self._get_relevant_accounts(token_info)
                    )

                if attempt < self.max_retries:
                    # Exponential backoff: 2^attempt seconds
                    await asyncio.sleep(2 ** (attempt - 1))
                else:
                    raise Exception(f"All {self.max_retries} sell attempts failed: {last_error}")