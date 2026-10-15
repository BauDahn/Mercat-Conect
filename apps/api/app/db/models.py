import uuid
from datetime import datetime, time
from typing import Any

from sqlalchemy import (
    ARRAY, BigInteger, Boolean, CheckConstraint, Float, ForeignKey, Integer, LargeBinary,
    Numeric, Text, Time, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

TS = TIMESTAMP(timezone=True)
GEN_UUID = text("gen_random_uuid()")
NOW = text("now()")  # clock-ok: espejo del DDL; la app siempre fija las marcas con el Clock


class Base(DeclarativeBase):
    pass


class Market(Base):
    __tablename__ = "markets"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    name: Mapped[str] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    opens_at: Mapped[time] = mapped_column(Time)
    closes_at: Mapped[time] = mapped_column(Time)
    offers_from: Mapped[time] = mapped_column(Time)
    tz: Mapped[str] = mapped_column(Text, server_default="Europe/Madrid")


class Stall(Base):
    __tablename__ = "stalls"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id"))
    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    verified_at: Mapped[datetime | None] = mapped_column(TS)
    payout_account_ref: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('NEIGHBOR','PRODUCER','MANAGER','ADMIN')"),
        CheckConstraint("status IN ('PENDING','ACTIVE','SUSPENDED','DELETED')"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    lang: Mapped[str] = mapped_column(Text, server_default="es")
    reputation: Mapped[float] = mapped_column(Numeric(3, 2), server_default=text("1.00"))
    status: Mapped[str] = mapped_column(Text, server_default="PENDING")
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)


class UserIdentity(Base):
    __tablename__ = "user_identities"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    person_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    age_verified_at: Mapped[datetime] = mapped_column(TS)
    age_method: Mapped[str] = mapped_column(Text)
    provider_ref: Mapped[str | None] = mapped_column(Text)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    created_at: Mapped[datetime] = mapped_column(TS)  # hora del Clock
    expires_at: Mapped[datetime] = mapped_column(TS)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("food_class IN ('REFRIGERATED','AMBIENT')"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    stall_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stalls.id"))
    name: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    unit_weight_g: Mapped[int | None] = mapped_column(Integer)
    vat_rate: Mapped[float] = mapped_column(Numeric(4, 2))
    allergens: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    food_class: Mapped[str] = mapped_column(Text)
    usual_price_cents: Mapped[int | None] = mapped_column(Integer)
    photo_path: Mapped[str | None] = mapped_column(Text)


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (
        CheckConstraint("qty_total > 0"),
        CheckConstraint("qty_available >= 0"),
        CheckConstraint("price_cents >= 0"),
        CheckConstraint("status IN ('DRAFT','ACTIVE','SOLD_OUT','EXPIRED','WITHDRAWN','DONATED','DISCARDED')"),
        CheckConstraint("consume_by IN ('TODAY','BEST_BEFORE')"),
        CheckConstraint("qty_available <= qty_total"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    stall_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stalls.id"))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    qty_total: Mapped[int] = mapped_column(Integer)
    qty_available: Mapped[int] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(Integer)
    reference_price_cents: Mapped[int | None] = mapped_column(Integer)
    pickup_from: Mapped[datetime] = mapped_column(TS)
    pickup_until: Mapped[datetime] = mapped_column(TS)
    status: Mapped[str] = mapped_column(Text, server_default="DRAFT")
    consume_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)


class OfferPolicy(Base):
    __tablename__ = "offer_policies"
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offers.id"), primary_key=True)
    profile: Mapped[str] = mapped_column(Text)
    policy: Mapped[dict[str, Any]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class PointsWeek(Base):
    __tablename__ = "points_week"
    __table_args__ = (CheckConstraint("spent >= 0 AND spent <= allowance"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    week_key: Mapped[str] = mapped_column(Text, primary_key=True)
    allowance: Mapped[int] = mapped_column(Integer)
    spent: Mapped[int] = mapped_column(Integer, server_default=text("0"))


class PointsLedger(Base):
    __tablename__ = "points_ledger"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    week_key: Mapped[str] = mapped_column(Text)
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    stall_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stalls.id"))
    status: Mapped[str] = mapped_column(Text)
    total_cents: Mapped[int] = mapped_column(Integer)
    points_cost: Mapped[int] = mapped_column(Integer)
    rules_applied: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'"))
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True)
    hold_expires_at: Mapped[datetime | None] = mapped_column(TS)
    pickup_until: Mapped[datetime] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("qty > 0"),)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), primary_key=True)
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offers.id"), primary_key=True)
    qty: Mapped[int] = mapped_column(Integer)
    unit_cents: Mapped[int] = mapped_column(Integer)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), unique=True)
    provider: Mapped[str] = mapped_column(Text)
    provider_ref: Mapped[str | None] = mapped_column(Text, unique=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)


class Locker(Base):
    __tablename__ = "lockers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id"))
    device_id: Mapped[str] = mapped_column(Text, unique=True)
    last_seen: Mapped[datetime | None] = mapped_column(TS)
    firmware: Mapped[str | None] = mapped_column(Text)


class Compartment(Base):
    __tablename__ = "compartments"
    __table_args__ = (
        CheckConstraint("size IN ('S','M','L')"),
        CheckConstraint("zone IN ('REFRIGERATED','AMBIENT')"),
        CheckConstraint("status IN ('FREE','RESERVED','OCCUPIED','OUT_OF_SERVICE')"),
        UniqueConstraint("locker_id", "slot"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    locker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lockers.id"))
    slot: Mapped[int] = mapped_column(Integer)
    size: Mapped[str] = mapped_column(Text)
    zone: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="FREE")


class Deposit(Base):
    __tablename__ = "deposits"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), unique=True)
    compartment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compartments.id"))
    code_hash: Mapped[bytes] = mapped_column(LargeBinary)
    valid_from: Mapped[datetime] = mapped_column(TS)
    valid_until: Mapped[datetime] = mapped_column(TS)
    deposited_at: Mapped[datetime | None] = mapped_column(TS)
    picked_up_at: Mapped[datetime | None] = mapped_column(TS)


class Subscription(Base):
    __tablename__ = "subscriptions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id"), primary_key=True)
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    quiet_from: Mapped[time | None] = mapped_column(Time)
    quiet_to: Mapped[time | None] = mapped_column(Time)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    read_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    keys: Mapped[dict[str, Any]] = mapped_column(JSONB)


class DomainEvent(Base):
    __tablename__ = "domain_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(TS)
    event_type: Mapped[str] = mapped_column(Text)
    aggregate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(TS)


class Payout(Base):
    __tablename__ = "payouts"
    __table_args__ = (CheckConstraint("status IN ('PENDING','PAID')"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    stall_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stalls.id"))
    period_from: Mapped[datetime] = mapped_column(TS)
    period_to: Mapped[datetime] = mapped_column(TS)
    gross_cents: Mapped[int] = mapped_column(Integer)
    commission_cents: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default="PENDING")
    paid_at: Mapped[datetime | None] = mapped_column(TS)


class Charity(Base):
    __tablename__ = "charities"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    name: Mapped[str] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Donation(Base):
    __tablename__ = "donations"
    __table_args__ = (CheckConstraint("qty > 0"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offers.id"))
    charity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("charities.id"))
    qty: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default="OFFERED")
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)
    completed_at: Mapped[datetime | None] = mapped_column(TS)


class Delivery(Base):
    __tablename__ = "deliveries"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=GEN_UUID)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), unique=True)
    provider: Mapped[str] = mapped_column(Text)
    provider_ref: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="REQUESTED")
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime | None] = mapped_column(TS)
