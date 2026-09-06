from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    Float,
    Boolean,
    ForeignKey,
    String,
    DateTime
)

from database import Base


class temples(Base):
    __tablename__ = "temples"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    location = Column(String, nullable=False)

    description = Column(String)

    opening_time = Column(String)
    closing_time = Column(String)

    contact = Column(String)

    created_at = Column(
        DateTime,
        default=datetime.now
    )


class users(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(
        String,
        nullable=False
    )

    email = Column(
        String,
        unique=True,
        nullable=False
    )

    password_hash = Column(
        String,
        nullable=True
    )

    roles = Column(
        String,
        nullable=False,
        default="PILIGRIM"
    )

    temple_id = Column(
        Integer,
        ForeignKey("temples.id"),
        nullable=True
    )

    auth_user_id = Column(
        String,
        unique=True,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.now
    )


class zone(Base):
    __tablename__ = "zones"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # REQUIRED tenant ownership.
    temple_id = Column(
        Integer,
        ForeignKey("temples.id"),
        nullable=False,
        index=True
    )

    name = Column(String, nullable=False)

    capacity = Column(
        Integer,
        nullable=False
    )

    # Keep existing database column name for compatibility.
    # API exposes this as `type`.
    types = Column(
        String,
        nullable=False,
        default="OTHER"
    )

    crowd_count = Column(
        Integer,
        nullable=False,
        default=0
    )

    risk = Column(
        String,
        default="LOW"
    )


class crowddata(Base):
    __tablename__ = "crowd_data"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    zone_id = Column(
        Integer,
        ForeignKey("zones.id"),
        nullable=False,
        index=True
    )

    timestamp = Column(
        DateTime,
        default=datetime.now
    )

    people_count = Column(
        Integer,
        nullable=False
    )

    density = Column(Float)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    zone_id = Column(
        Integer,
        ForeignKey("zones.id"),
        nullable=False,
        index=True
    )

    alert_type = Column(String)
    message = Column(String)

    created_at = Column(
        DateTime,
        default=datetime.now
    )

    resolved = Column(
        Boolean,
        nullable=False,
        default=False
    )
