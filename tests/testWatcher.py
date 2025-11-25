import pytest
from src.watcher.moralis import get_myst_deposits


@pytest.mark.asyncio
async def test_get_deposits(mocker):
    # Prepare the mock response object
    mock_response = mocker.AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {"result": []}

    # Patch aiohttp.ClientSession.get directly
    # The return_value of the patched method needs to be an async context manager
    mocker.patch(
        "aiohttp.ClientSession.get",
        return_value=mocker.AsyncMock(
            __aenter__=mocker.AsyncMock(return_value=mock_response),
            __aexit__=mocker.AsyncMock(return_value=None),
        ),
    )

    deposits = await get_myst_deposits("0x4c0ECdd578D76915be88e693cC98e32f85Bd93Ce")
    assert deposits == []  # Test básico
