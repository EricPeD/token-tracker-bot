# src/testMoralis.py
import asyncio
from watcher.moralis import get_myst_deposits


async def main():
    wallet = "0x4c0ECdd578D76915be88e693cC98e32f85Bd93Ce"
    print(f"Buscando depósitos MYST en {wallet}...\n")

    deposits = await get_myst_deposits(wallet)

    if not deposits:
        print("No se encontraron depósitos de MYST recientes")
        return

    print(f"Encontrados {len(deposits)} depósitos:\n")
    for d in deposits:
        print(f"{d['amount']} {d['token_symbol']}")
        print(f"   De: {d['from_address'][:10]}...{d['from_address'][-6:]}")
        print(f"   Tx: https://polygonscan.com/tx/{d['tx_hash']}")
        print(f"   Fecha: {d['block_timestamp']}\n")


if __name__ == "__main__":
    asyncio.run(main())
