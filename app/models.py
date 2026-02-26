from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, Float, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


# Asociacijska tabela za many-to-many: Clan ↔ Skupina
clan_skupina_table = Table(
    "clan_skupina",
    Base.metadata,
    Column("clan_id", Integer, ForeignKey("clani.id"), primary_key=True),
    Column("skupina_id", Integer, ForeignKey("skupine.id"), primary_key=True),
)


TIPI_CLANSTVA_PRIVZETO = [
    "Osebni",
    "Družinski",
    "Simpatizerji",
    "Mladi",
    "Invalid",
]

OPERATERSKI_RAZREDI_PRIVZETO = ["A", "N"]

VLOGE = ["admin", "urednik", "bralec"]


class Clan(Base):
    __tablename__ = "clani"

    id = Column(Integer, primary_key=True, index=True)
    priimek = Column(String, nullable=False)
    ime = Column(String, nullable=False)
    klicni_znak = Column(String, nullable=True, index=True)
    naslov_ulica = Column(String, nullable=True)
    naslov_posta = Column(String, nullable=True)
    tip_clanstva = Column(String, nullable=False, default="Redno")
    klicni_znak_nosilci = Column(String, nullable=True)
    operaterski_razred = Column(String, nullable=True)
    mobilni_telefon = Column(String, nullable=True)
    telefon_doma = Column(String, nullable=True)
    elektronska_posta = Column(String, nullable=True)
    soglasje_op = Column(String, nullable=True)
    izjava = Column(String, nullable=True)
    veljavnost_rd = Column(Date, nullable=True)
    es_stevilka = Column(Integer, nullable=True)
    aktiven = Column(Boolean, default=True, nullable=False)
    opombe = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    clanarine = relationship("Clanarina", back_populates="clan", cascade="all, delete-orphan",
                             order_by="Clanarina.leto.desc()")
    aktivnosti = relationship("Aktivnost", back_populates="clan", cascade="all, delete-orphan",
                              order_by="(Aktivnost.leto.desc(), Aktivnost.datum.desc())")
    skupine = relationship("Skupina", secondary=clan_skupina_table, back_populates="clani")


class Clanarina(Base):
    __tablename__ = "clanarine"

    id = Column(Integer, primary_key=True, index=True)
    clan_id = Column(Integer, ForeignKey("clani.id"), nullable=False)
    leto = Column(Integer, nullable=False)
    datum_placila = Column(Date, nullable=True)
    znesek = Column(String, nullable=True)
    opombe = Column(String, nullable=True)

    clan = relationship("Clan", back_populates="clanarine")


class Aktivnost(Base):
    __tablename__ = "aktivnosti"

    id = Column(Integer, primary_key=True, index=True)
    clan_id = Column(Integer, ForeignKey("clani.id"), nullable=False)
    leto = Column(Integer, nullable=False)
    datum = Column(Date, nullable=True)
    opis = Column(String(1000), nullable=False)
    delovne_ure = Column(Float, nullable=True)

    clan = relationship("Clan", back_populates="aktivnosti")


class Skupina(Base):
    __tablename__ = "skupine"

    id = Column(Integer, primary_key=True, index=True)
    ime = Column(String, nullable=False)
    opis = Column(String, nullable=True)

    clani = relationship("Clan", secondary=clan_skupina_table, back_populates="skupine")


class Uporabnik(Base):
    __tablename__ = "uporabniki"

    id = Column(Integer, primary_key=True, index=True)
    uporabnisko_ime = Column(String, unique=True, nullable=False, index=True)
    geslo_hash = Column(String, nullable=False)
    vloga = Column(String, nullable=False, default="bralec")
    ime_priimek = Column(String, nullable=True)
    aktiven = Column(Boolean, default=True, nullable=False)
    totp_skrivnost = Column(String, nullable=True)
    totp_aktiven = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Nastavitev(Base):
    __tablename__ = "nastavitve"

    kljuc = Column(String, primary_key=True)
    vrednost = Column(String, nullable=True)
    opis = Column(String, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    cas = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    uporabnik = Column(String, nullable=True)
    ip = Column(String, nullable=True)
    akcija = Column(String, nullable=False, index=True)
    opis = Column(String, nullable=True)


class ZaupljivaNaprava(Base):
    __tablename__ = "zaupljive_naprave"

    id = Column(Integer, primary_key=True, index=True)
    uporabnik_id = Column(Integer, ForeignKey("uporabniki.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    user_agent = Column(String, nullable=True)
