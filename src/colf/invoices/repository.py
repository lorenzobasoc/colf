import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import aiosqlite

from .domain import Client, Invoice

logger = logging.getLogger(__name__)

_CREATE_CLIENTS = """
CREATE TABLE IF NOT EXISTS clients (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    ragione_sociale          TEXT    NOT NULL,
    piva                     TEXT    NOT NULL,
    codice_fiscale           TEXT    NOT NULL,
    pec                      TEXT    NOT NULL,
    codice_destinatario      TEXT    NOT NULL,
    indirizzo                TEXT    NOT NULL,
    cap                      TEXT    NOT NULL,
    comune                   TEXT    NOT NULL,
    provincia                TEXT    NOT NULL,
    nazione                  TEXT    NOT NULL DEFAULT 'IT',
    active                   INTEGER NOT NULL DEFAULT 1,
    tariffa_oraria           TEXT    NOT NULL DEFAULT '0.00',
    note                     TEXT,
    created_at               TEXT    NOT NULL,
    descrizione_default      TEXT,
    giorni_pagamento_default INTEGER NOT NULL DEFAULT 30
)
"""

_CREATE_INVOICES = """
CREATE TABLE IF NOT EXISTS invoices (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    numero            INTEGER NOT NULL,
    anno              INTEGER NOT NULL,
    cliente_id        INTEGER NOT NULL REFERENCES clients(id),
    data_emissione    TEXT    NOT NULL,
    data_scadenza     TEXT    NOT NULL,
    descrizione       TEXT    NOT NULL,
    importo           TEXT    NOT NULL,
    totale            TEXT    NOT NULL,
    stato             TEXT    NOT NULL DEFAULT 'BOZZA',
    progressivo_invio TEXT    NOT NULL UNIQUE,
    xml_path          TEXT,
    created_at        TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL,
    note              TEXT
)
"""


async def create_tables(db: aiosqlite.Connection) -> None:
    await db.execute(_CREATE_CLIENTS)
    await db.execute(_CREATE_INVOICES)
    await db.commit()
    logger.info("SQLite tables ensured")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_client(row: aiosqlite.Row) -> Client:
    return Client(
        id=row["id"],
        ragione_sociale=row["ragione_sociale"],
        piva=row["piva"],
        codice_fiscale=row["codice_fiscale"],
        pec=row["pec"],
        codice_destinatario=row["codice_destinatario"],
        indirizzo=row["indirizzo"],
        cap=row["cap"],
        comune=row["comune"],
        provincia=row["provincia"],
        nazione=row["nazione"],
        active=bool(row["active"]),
        tariffa_oraria=Decimal(row["tariffa_oraria"]),
        note=row["note"],
        created_at=datetime.fromisoformat(row["created_at"]),
        descrizione_default=row["descrizione_default"],
        giorni_pagamento_default=row["giorni_pagamento_default"],
    )


def _row_to_invoice(row: aiosqlite.Row) -> Invoice:
    return Invoice(
        id=row["id"],
        numero=row["numero"],
        anno=row["anno"],
        cliente_id=row["cliente_id"],
        data_emissione=date.fromisoformat(row["data_emissione"]),
        data_scadenza=date.fromisoformat(row["data_scadenza"]),
        descrizione=row["descrizione"],
        importo=Decimal(row["importo"]),
        totale=Decimal(row["totale"]),
        stato=row["stato"],
        progressivo_invio=row["progressivo_invio"],
        xml_path=row["xml_path"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        note=row["note"],
    )


# ── Clients ──────────────────────────────────────────────────────────────────

async def insert_client(db: aiosqlite.Connection, data: dict) -> Client:
    now = _now()
    cursor = await db.execute(
        """
        INSERT INTO clients
          (ragione_sociale, piva, codice_fiscale, pec, codice_destinatario,
           indirizzo, cap, comune, provincia, nazione, tariffa_oraria, note,
           created_at, descrizione_default, giorni_pagamento_default)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            data["ragione_sociale"], data["piva"], data["codice_fiscale"],
            data["pec"], data["codice_destinatario"], data["indirizzo"],
            data["cap"], data["comune"], data["provincia"],
            data.get("nazione", "IT"), data.get("tariffa_oraria", "0.00"),
            data.get("note"), now,
            data.get("descrizione_default"), data.get("giorni_pagamento_default", 30),
        ),
    )
    await db.commit()
    return await get_client_by_id(db, cursor.lastrowid)


async def get_client_by_id(db: aiosqlite.Connection, client_id: int) -> Client | None:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM clients WHERE id = ?", (client_id,)
    ) as cursor:
        row = await cursor.fetchone()
    return _row_to_client(row) if row else None


async def list_clients(db: aiosqlite.Connection, active_only: bool = True) -> list[Client]:
    db.row_factory = aiosqlite.Row
    query = "SELECT * FROM clients"
    params: tuple = ()
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY ragione_sociale"
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
    return [_row_to_client(r) for r in rows]


async def search_clients(db: aiosqlite.Connection, query: str) -> list[Client]:
    db.row_factory = aiosqlite.Row
    pattern = f"%{query}%"
    async with db.execute(
        "SELECT * FROM clients WHERE active = 1 AND ragione_sociale LIKE ? ORDER BY ragione_sociale",
        (pattern,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [_row_to_client(r) for r in rows]


async def update_client(db: aiosqlite.Connection, client_id: int, data: dict) -> Client | None:
    fields = [f"{k} = ?" for k in data]
    values = list(data.values()) + [client_id]
    await db.execute(
        f"UPDATE clients SET {', '.join(fields)} WHERE id = ?", values
    )
    await db.commit()
    return await get_client_by_id(db, client_id)


# ── Invoices ─────────────────────────────────────────────────────────────────

async def get_next_numero(db: aiosqlite.Connection, anno: int) -> int:
    async with db.execute(
        "SELECT COALESCE(MAX(numero), 0) + 1 FROM invoices WHERE anno = ?", (anno,)
    ) as cursor:
        row = await cursor.fetchone()
    return row[0]


async def insert_invoice(db: aiosqlite.Connection, data: dict) -> Invoice:
    now = _now()
    cursor = await db.execute(
        """
        INSERT INTO invoices
          (numero, anno, cliente_id, data_emissione, data_scadenza,
           descrizione, importo, totale, stato, progressivo_invio,
           xml_path, created_at, updated_at, note)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            data["numero"], data["anno"], data["cliente_id"],
            data["data_emissione"], data["data_scadenza"],
            data["descrizione"], data["importo"], data["totale"],
            data.get("stato", "BOZZA"), data["progressivo_invio"],
            data.get("xml_path"), now, now, data.get("note"),
        ),
    )
    await db.commit()
    return await get_invoice_by_id(db, cursor.lastrowid)


async def update_invoice_stato(
    db: aiosqlite.Connection, invoice_id: int, stato: str, xml_path: str | None = None
) -> None:
    now = _now()
    if xml_path is not None:
        await db.execute(
            "UPDATE invoices SET stato = ?, xml_path = ?, updated_at = ? WHERE id = ?",
            (stato, xml_path, now, invoice_id),
        )
    else:
        await db.execute(
            "UPDATE invoices SET stato = ?, updated_at = ? WHERE id = ?",
            (stato, now, invoice_id),
        )
    await db.commit()


async def get_invoice_by_id(db: aiosqlite.Connection, invoice_id: int) -> Invoice | None:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM invoices WHERE id = ?", (invoice_id,)
    ) as cursor:
        row = await cursor.fetchone()
    return _row_to_invoice(row) if row else None


async def get_invoice_by_numero(db: aiosqlite.Connection, numero: int, anno: int) -> Invoice | None:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM invoices WHERE numero = ? AND anno = ?", (numero, anno)
    ) as cursor:
        row = await cursor.fetchone()
    return _row_to_invoice(row) if row else None


async def list_invoices(
    db: aiosqlite.Connection,
    anno: int | None = None,
    stato: str | None = None,
    cliente_id: int | None = None,
) -> list[Invoice]:
    db.row_factory = aiosqlite.Row
    query = "SELECT * FROM invoices WHERE 1=1"
    params: list = []
    if anno is not None:
        query += " AND anno = ?"
        params.append(anno)
    if stato is not None:
        query += " AND stato = ?"
        params.append(stato)
    if cliente_id is not None:
        query += " AND cliente_id = ?"
        params.append(cliente_id)
    query += " ORDER BY anno DESC, numero DESC"
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
    return [_row_to_invoice(r) for r in rows]


async def list_expiring_invoices(db: aiosqlite.Connection, within_days: int = 7) -> list[Invoice]:
    db.row_factory = aiosqlite.Row
    today = date.today().isoformat()
    deadline = (date.today() + timedelta(days=within_days)).isoformat()
    async with db.execute(
        """
        SELECT * FROM invoices
        WHERE stato NOT IN ('PAGATA', 'SCARTATA')
          AND data_scadenza >= ?
          AND data_scadenza <= ?
        ORDER BY data_scadenza
        """,
        (today, deadline),
    ) as cursor:
        rows = await cursor.fetchall()
    return [_row_to_invoice(r) for r in rows]
