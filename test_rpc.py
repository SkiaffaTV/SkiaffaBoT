import asyncio
from solana.rpc.async_api import AsyncClient
from dotenv import load_dotenv
import os

load_dotenv()

async def test_connection():
    client = AsyncClient(os.getenv("SOLANA_NODE_RPC_ENDPOINT"))
    try:
        is_connected = await client.is_connected()
        print(f"RPC Connection Status: {'Connected' if is_connected else 'Not Connected'}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_connection())