import pytest
from watcher.moralis import get_myst_deposits

@pytest.mark.asyncio
async def test_get_deposits(mocker):
    # Mock aiohttp response
    mock_session = mocker.AsyncMock()
    mock_resp = mocker.AsyncMock(status=200, json=mocker.AsyncMock(return_value={"result": []}))
    mock_session.get.return_value.__aenter__.return_value = mock_resp

    deposits = await get_myst_deposits("0x4c0ECdd578D76915be88e693cC98e32f85Bd93Ce")
    assert deposits == [] # Test básico