from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class PromptCache(Base):
    __tablename__ = "prompt_cache"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    prompt = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=False)
    response = Column(JSONB, nullable=False)
    model = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)
