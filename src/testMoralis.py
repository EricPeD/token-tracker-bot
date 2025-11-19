import asyncio
from watcher.moralis import get_myst_deposits
from config.settings import settings

async def main():
    # Usa tu wallet real
    deposits = await get_myst_deposits("0xTuWallet")
    if not deposits:
        print("No depósitos recientes o error.")
    for tx in deposits:
        if tx['to_address'].lower() == "0xtuwallet".lower():  # Filtra solo incoming
            print(f"{tx['value_formatted']} MYST de {tx['from_address'][:10]}... a las {tx['block_timestamp']}")
            print(f"Tx: https://polygonscan.com/tx/{tx['transaction_hash']}")

if __name__ == "__main__":
    asyncio.run(main())