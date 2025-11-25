import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.models import Base, User  # Import your models and Base
from src.watcher.storage import TxStorage


# Setup a test database engine and session
@pytest.fixture(name="test_engine")
async def test_engine_fixture():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(name="TestSessionLocal")
async def test_session_local_fixture(test_engine, mocker):
    """Fixture that returns a SQLAlchemy AsyncSessionLocal for tests and patches global engine/session."""
    TestSessionLocal = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    mocker.patch("src.models.engine", test_engine)
    mocker.patch("src.models.AsyncSessionLocal", TestSessionLocal)
    return TestSessionLocal


@pytest.fixture
async def db_session(TestSessionLocal):
    """Fixture that provides a 'session' for testing."""
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def populated_db(db_session):
    # Setup for tests that need initial data
    user = User(user_id=123, wallet_address="0xtestwallet123")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)  # Refresh user to get any relationships loaded
    yield db_session


@pytest.mark.asyncio
async def test_tx_storage_save_and_load_last(TestSessionLocal):
    storage = TxStorage(user_id=1, session_factory=TestSessionLocal)
    await storage.save_last("2023-01-01T00:00:00Z")
    last_timestamp = await storage.load_last()
    assert last_timestamp == "2023-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_tx_storage_filter_new(TestSessionLocal):
    storage = TxStorage(user_id=2, session_factory=TestSessionLocal)
    # No last timestamp, all deposits should be new
    deposits_1 = [
        {"block_timestamp": "2023-01-01T01:00:00Z"},
        {"block_timestamp": "2023-01-01T02:00:00Z"},
    ]
    new_deposits_1 = await storage.filter_new(deposits_1)
    assert len(new_deposits_1) == 2

    # Save a timestamp, some deposits should be filtered
    await storage.save_last("2023-01-01T01:30:00Z")
    deposits_2 = [
        {"block_timestamp": "2023-01-01T01:00:00Z"},  # Old
        {"block_timestamp": "2023-01-01T02:00:00Z"},  # New
        {"block_timestamp": "2023-01-01T03:00:00Z"},  # New
    ]
    new_deposits_2 = await storage.filter_new(deposits_2)
    assert len(new_deposits_2) == 2
    assert new_deposits_2[0]["block_timestamp"] == "2023-01-01T02:00:00Z"


@pytest.mark.asyncio
async def test_tx_storage_reset(TestSessionLocal):
    storage = TxStorage(user_id=3, session_factory=TestSessionLocal)
    await storage.save_last("2023-01-01T00:00:00Z")
    await storage.reset()
    last_timestamp = await storage.load_last()
    assert last_timestamp is None
