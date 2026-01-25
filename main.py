import asyncio
from system_orchestrator import SystemCoordinator
from utils.logger import get_logger
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)

async def main():
    coord = SystemCoordinator()
    await coord.initialize()
    # Initialize bots with components
    fee_manager = coord.fee_manager
    staking_manager = coord.staking_manager
    q_bot = QBot(coord.config, coord.exchanges, fee_manager)
    a_bot = ABot(coord.config, coord.exchanges, staking_manager, fee_manager)
    g_bot = GBot(coord.config, coord.exchanges, fee_manager)
    # Run logic...

if __name__ == "__main__":
    asyncio.run(main())