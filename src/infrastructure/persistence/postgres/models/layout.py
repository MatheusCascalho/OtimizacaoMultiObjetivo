from __future__ import annotations

from sqlalchemy import Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.postgres.base import Base


class CityLayout(Base):
    __tablename__ = "city_layouts"
    __table_args__ = (
        UniqueConstraint("instance_id", "city_index", name="uq_city_layouts_instance_city"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(40), nullable=False)
    city_index: Mapped[int] = mapped_column(Integer, nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
