from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rtt: Mapped[float] = mapped_column(Float, nullable=False)
    srtt: Mapped[float] = mapped_column(Float, nullable=False)
    rttvar: Mapped[float] = mapped_column(Float, nullable=False)
    rto: Mapped[float] = mapped_column(Float, nullable=False)
    was_retransmission: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timeout_occurred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
