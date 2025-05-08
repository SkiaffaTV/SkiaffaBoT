import asyncio
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from spl.token.instructions import create_mint, create_associated_token_account, mint_to
from solders.transaction import Transaction
from solana.rpc.commitment import Confirmed
from utils.logger import get_logger
import base58

logger = get_logger(__name__)

async def create_test_token(rpc_endpoint: str, wallet_private_key: str, program_id: str):
    """
    Create a test SPL token on Solana Devnet and mint some tokens.
    
    Args:
        rpc_endpoint: Solana Devnet RPC endpoint
        wallet_private_key: Base58-encoded private key of the wallet
        program_id: Pump.fun program address
    """
    async with AsyncClient(rpc_endpoint) as client:
        # Load wallet keypair
        try:
            wallet_keypair = Keypair.from_base58_string(base58.b58decode(wallet_private_key))
        except Exception as e:
            logger.error(f"Invalid private key: {str(e)}")
            return None

        # Create a new token mint
        mint_authority = wallet_keypair.pubkey()
        try:
            mint_pubkey = Pubkey.new_unique()
            mint_tx = Transaction()
            mint_tx.add(create_mint(
                program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"),
                mint=mint_pubkey,
                authority=mint_authority,
                decimals=9,
                freeze_authority=None
            ))
            mint_tx.fee_payer = mint_authority
            mint_tx.sign(wallet_keypair)
            mint_signature = await client.send_transaction(mint_tx, commitment=Confirmed)
            logger.info(f"Created test token mint: {mint_signature}")

            # Create associated token account
            ata_tx = Transaction()
            ata = create_associated_token_account(
                payer=mint_authority,
                owner=mint_authority,
                mint=mint_pubkey
            )
            ata_tx.add(ata)
            ata_tx.fee_payer = mint_authority
            ata_tx.sign(wallet_keypair)
            ata_signature = await client.send_transaction(ata_tx, commitment=Confirmed)
            logger.info(f"Created associated token account: {ata_signature}")

            # Mint tokens to ATA
            mint_to_tx = Transaction()
            mint_to_tx.add(mint_to(
                program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"),
                mint=mint_pubkey,
                dest=ata.instructions[0].keys[0].pubkey,
                authority=mint_authority,
                amount=1000 * 10**9  # Mint 1000 tokens
            ))
            mint_to_tx.fee_payer = mint_authority
            mint_to_tx.sign(wallet_keypair)
            mint_to_signature = await client.send_transaction(mint_to_tx, commitment=Confirmed)
            logger.info(f"Minted 1000 tokens to ATA: {mint_to_signature}")

            return mint_pubkey
        except Exception as e:
            logger.error(f"Failed to create test token: {str(e)}")
            return None

if __name__ == "__main__":
    rpc_endpoint = "https://solana-devnet.core.chainstack.com/e8d2850b2c1957982139b5408d4e16d9"
    wallet_private_key = "5vaaShXa6GFQ4hBZx29W8WpYRoj1pVTQuVBfQDtdczgHSvEFEXcfuxcnHW3rhEca8PDo5RTQmrNHy1P2etGLjCbw"
    program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

    asyncio.run(create_test_token(rpc_endpoint, wallet_private_key, program_id))