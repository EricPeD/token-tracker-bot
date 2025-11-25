from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import (
    relationship,
    declarative_base,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.config.settings import settings  # Importar settings


Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True)
    wallet_address = Column(String, nullable=False)
    # Relación con last_tx (multi-user)
    last_tx = relationship("LastTx", back_populates="user", uselist=False)
    # Relación con UserToken para los tokens que el usuario quiere trackear
    tracked_tokens = relationship(
        "UserToken", back_populates="user", cascade="all, delete-orphan"
    )
    # Relación con Transaction para guardar el historial de depósitos
    transactions = relationship(
        "Transaction", back_populates="user", cascade="all, delete-orphan"
    )


class UserToken(Base):
    __tablename__ = "user_tokens"
    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    token_address = Column(String, primary_key=True, nullable=False)
    token_symbol = Column(
        String, nullable=True
    )  # Para identificar el token, aunque el contrato es la clave

    user = relationship("User", back_populates="tracked_tokens")

    __table_args__ = (
        UniqueConstraint("user_id", "token_address", name="_user_token_uc"),
    )


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    token_address = Column(String, nullable=False)
    token_symbol = Column(String, nullable=True)
    amount = Column(
        String, nullable=False
    )  # Almacenar como string para precisión con grandes números
    tx_hash = Column(String, nullable=False)
    block_timestamp = Column(String, nullable=False)
    from_address = Column(String, nullable=False)

    user = relationship("User", back_populates="transactions")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "tx_hash", "token_address", name="_user_tx_token_uc"
        ),
    )  # Prevenir duplicados


class LastTx(Base):
    __tablename__ = "last_tx"
    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    last_timestamp = Column(String)
    user = relationship("User", back_populates="last_tx")


# Engine async
engine = create_async_engine(
    "sqlite+aiosqlite:///tx_storage.db", echo=settings.sqlalchemy_echo
)  # echo for debug
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)
