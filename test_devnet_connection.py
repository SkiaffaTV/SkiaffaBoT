import asyncio
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TokenAccountOpts
from utils.logger import get_logger

logger = get_logger(__name__)

async def test_devnet_connection(rpc_endpoint: str, wallet_address: str):
    """
    Test connection to Solana Devnet node and wallet balance.
    
    Args:
        rpc_endpoint: Solana Devnet RPC endpoint
        wallet_address: Public address of the Devnet wallet
    """
    async with AsyncClient(rpc_endpoint) as client:
        # Test node health
        try:
            health = await client.get_health()
            logger.info(f"Node health: {health}")
        except Exception as e:
            logger.error(f"Failed to connect to node: {str(e)}")
            return

        # Test wallet balance
        try:
            balance = await client.get_balance(Pubkey.from_string(wallet_address))
            balance_sol = balance.value / 1_000_000_000  # Convert lamports to SOL
            logger.info(f"Wallet balance: {balance_sol:.6f} SOL")
        except Exception as e:
            logger.error(f"Failed to get wallet balance: {str(e)}")
            return

        # Test pump.fun program
        pump_fun_address = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
        try:
            account_info = await client.get_account_info(Pubkey.from_string(pump_fun_address))
            if account_info.value:
                logger.info(f"Pump.fun program found at {pump_fun_address}")
            else:
                logger.warning(f"Pump.fun program not found at {pump_fun_address}")
        except Exception as e:
            logger.error(f"Failed to check pump.fun program: {str(e)}")

if __name__ == "__main__":
    rpc_endpoint = "https://solana-devnet.core.chainstack.com/e8d2850b2c1957982139b5408d4e16d9"
    wallet_address = "AToXR1m6qUrVEbcpFfauyEVr7CuL381cW67Cqat3xLQV"  # Replace with your Devnet wallet address
    asyncio.run(test_devnet_connection(rpc_endpoint, wallet_address))