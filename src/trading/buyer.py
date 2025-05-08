from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solders.instruction import Instruction
from solders.system_program import TransferParams, transfer
from solders.token import create_associated_token_account_instruction
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed
from solana.rpc.api import Client as SolanaClient
from .curve import BondingCurveManager
from .priority_fee import PriorityFeeManager
from .wallet import Wallet
from .types import TokenInfo, TradeResult
from .constants import LAMPORTS_PER_SOL, TOKEN_DECIMALS
from .logger import logger
import asyncio
import struct
from typing import List
from solders.account import AccountMeta

class TokenBuyer:
    """Handles buying tokens on pump.fun."""

    def __init__(
        self,
        client: SolanaClient,
        wallet: Wallet,
        curve_manager: BondingCurveManager,
        priority_fee_manager: PriorityFeeManager,
        amount: float,
        slippage: float = 0.01,
        max_retries: int = 5,
        extreme_fast_mode: bool = False,
    ):
        """Initialize token buyer.

        Args:
            client: Solana client for RPC calls
            wallet: Wallet for signing transactions
            curve_manager: Bonding curve manager
            priority_fee_manager: Priority fee manager
            amount: Amount of SOL to spend
            slippage: Slippage tolerance (0.01 = 1%)
            max_retries: Maximum number of retry attempts
            extreme_fast_mode: If enabled, use minimal checks for faster execution
        """
        self.client = client
        self.wallet = wallet
        self.curve_manager = curve_manager
        self.priority_fee_manager = priority_fee_manager
        self.amount = amount
        self.slippage = slippage
        self.max_retries = max_retries
        self.extreme_fast_mode = extreme_fast_mode

    async def execute(self, token_info: TokenInfo, *args, **kwargs) -> TradeResult:
        """Execute buy operation.

        Args:
            token_info: Token information

        Returns:
            TradeResult with buy outcome
        """
        try:
            # Get associated token account
            associated_token_account = self.wallet.get_associated_token_address(
                token_info.mint
            )
            logger.debug(f"Calculating ATA for mint: {token_info.mint}")
            logger.debug(f"ATA calculated: {associated_token_account}")

            if not self.extreme_fast_mode:
                # Wait for node synchronization only if not in extreme fast mode
                logger.info("Waiting 10 seconds for RPC node to synchronize ATA...")
                await asyncio.sleep(10)

            # Check if ATA exists, create if not
            try:
                account_info = await self.client.get_account_info(associated_token_account)
            except ValueError:
                account_info = None
            if account_info is None:
                logger.info(f"Creating ATA {associated_token_account}...")
                create_ata_ix = create_associated_token_account_instruction(
                    payer=self.wallet.pubkey,
                    wallet=self.wallet.pubkey,
                    mint=token_info.mint,
                )
                tx_signature = await self.client.build_and_send_transaction(
                    [create_ata_ix],
                    self.wallet.keypair,
                    skip_preflight=True,
                    max_retries=self.max_retries,
                    priority_fee=await self.priority_fee_manager.calculate_priority_fee(
                        self._get_relevant_accounts(token_info)
                    ),
                )
                success = await self.client.confirm_transaction(tx_signature)
                if not success:
                    logger.error(f"Failed to create ATA {associated_token_account}")
                    return TradeResult(
                        success=False,
                        error_message=f"Failed to create ATA {associated_token_account}",
                        amount=0,
                        price=0,
                        tx_signature=tx_signature,
                    )
                logger.info(f"ATA {associated_token_account} created: {tx_signature}")

            # Convert amount to lamports
            sol_amount_lamports = int(self.amount * LAMPORTS_PER_SOL)

            if self.extreme_fast_mode:
                # In extreme fast mode, set a low min_token_output to ensure transaction success
                min_token_output = 1  # Accept any amount greater than 0
                token_price_sol = None  # Price not calculated
            else:
                # Fetch token price from curve state
                curve_state = await self.curve_manager.get_curve_state(
                    token_info.bonding_curve
                )
                token_price_sol = curve_state.calculate_price()
                expected_token_output = (self.amount / token_price_sol) * (10**TOKEN_DECIMALS)
                slippage_factor = 1 - self.slippage
                min_token_output = int(expected_token_output * slippage_factor)

            logger.info(f"Buying tokens with {self.amount:.6f} SOL")
            if not self.extreme_fast_mode:
                logger.info(f"Expected token output: {expected_token_output / (10**TOKEN_DECIMALS):.6f} tokens")
                logger.info(
                    f"Minimum token output (with {self.slippage * 100}% slippage): {min_token_output / (10**TOKEN_DECIMALS):.6f} tokens"
                )
            else:
                logger.info("Extreme fast mode: Minimum token output set to 1")

            tx_signature = await self._send_buy_transaction(
                token_info,
                associated_token_account,
                sol_amount_lamports,
                min_token_output,
            )

            success = await self.client.confirm_transaction(tx_signature)
            if success:
                logger.info(f"Buy transaction confirmed: {tx_signature}")
                return TradeResult(
                    success=True,
                    tx_signature=tx_signature,
                    amount=expected_token_output / (10**TOKEN_DECIMALS) if not self.extreme_fast_mode else None,
                    price=token_price_sol if not self.extreme_fast_mode else None,
                    error_message=None,
                )
            else:
                logger.error(f"Buy transaction failed to confirm on chain: {tx_signature}")
                return TradeResult(
                    success=False,
                    error_message=f"Transaction failed to confirm on chain: {tx_signature}",
                    amount=0,
                    price=token_price_sol if not self.extreme_fast_mode else None,
                    tx_signature=tx_signature,
                )

        except Exception as e:
            logger.error(f"Buy operation failed: {str(e)}")
            return TradeResult(
                success=False,
                error_message=str(e),
                amount=0,
                price=0,
                tx_signature=None,
            )

    async def _send_buy_transaction(
        self,
        token_info: TokenInfo,
        associated_token_account: Pubkey,
        sol_amount: int,
        min_token_output: int,
    ) -> str:
        """Send buy transaction with retries and error handling.

        Args:
            token_info: Token information
            associated_token_account: User's token account
            sol_amount: Amount of SOL to spend in lamports
            min_token_output: Minimum tokens to receive in raw units

        Returns:
            Transaction signature

        Raises:
            Exception: If all retry attempts fail
        """
        # Prepare buy instruction accounts
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

        # Prepare buy instruction data
        data = (
            EXPECTED_DISCRIMINATOR
            + struct.pack("<Q", sol_amount)
            + struct.pack("<Q", min_token_output)
        )
        buy_ix = Instruction(PumpAddresses.PROGRAM, data, accounts)

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
                    [buy_ix],
                    self.wallet.keypair,
                    skip_preflight=True,
                    max_retries=1,  # Handle retries manually
                    priority_fee=int(priority_fee),
                )
                log_transaction_attempt(
                    logger,
                    action="buy",
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
                    action="buy",
                    attempt=attempt,
                    max_attempts=self.max_retries,
                    success=False,
                    error=last_error,
                    token_symbol=token_info.symbol
                )

                # Handle specific errors
                if "blockhash not found" in last_error.lower():
                    logger.info("Blockhash not found, refreshing blockhash for retry...")
                    base_priority_fee = await self.priority_fee_manager.calculate_priority_fee(
                        self._get_relevant_accounts(token_info)
                    )

                if attempt < self.max_retries:
                    # Exponential backoff: 2^attempt seconds
                    await asyncio.sleep(2 ** (attempt - 1))
                else:
                    raise Exception(f"All {self.max_retries} buy attempts failed: {last_error}")

    def _get_relevant_accounts(self, token_info: TokenInfo) -> List[Pubkey]:
        """Get relevant accounts for priority fee calculation.

        Args:
            token_info: Token information

        Returns:
            List of relevant Pubkeys
        """
        return [
            token_info.bonding_curve,
            token_info.associated_bonding_curve,
            self.wallet.get_associated_token_address(token_info.mint),
        ]