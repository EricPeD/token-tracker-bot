# src/utils/format.py
from typing import Dict, Any


def escape_md2(text: str) -> str:
    """Escapea caracteres reservados en MarkdownV2 de Telegram"""
    escape_chars = r"_[]()~`>#+-=|{}.!"
    return "".join("\\" + c if c in escape_chars else c for c in str(text))


def format_deposit_msg(deposit: Dict[Any, Any]) -> str:
    amount = escape_md2(deposit["amount"])
    symbol = escape_md2(deposit["token_symbol"])
    from_addr = escape_md2(deposit["from_address"])
    tx_hash = deposit["tx_hash"]
    timestamp = escape_md2(deposit["block_timestamp"])

    return (
        f"*{symbol} Deposit\\!*\n"  # ← ¡¡el \! es obligatorio!!
        f"Cantidad: {amount} {symbol}\n"
        f"De: `{from_addr[:10]}...{from_addr[-6:]}`\n"
        f"Tx: [Ver en Polygonscan](https://polygonscan.com/tx/{tx_hash})\n"
        f"Fecha: {timestamp}"
    )
