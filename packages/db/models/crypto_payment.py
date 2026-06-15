from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import Base, JsonType, new_uuid


class CryptoPayment(Base):
    __tablename__ = "crypto_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), unique=True, nullable=False
    )
    pay_currency: Mapped[str] = mapped_column(String(20), nullable=False)
    pay_amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    pay_address: Mapped[str | None] = mapped_column(String(255))
    tx_hash: Mapped[str | None] = mapped_column(String(255))
    confirmations: Mapped[int] = mapped_column(Integer, default=0)
    webhook_payload: Mapped[dict | None] = mapped_column(JsonType)

    payment: Mapped["Payment"] = relationship(back_populates="crypto_detail")
