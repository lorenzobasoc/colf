import logging
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import aiosqlite

from ..config import Settings
from .constants import BOLLO_IMPORTO, InvoiceStato
from .domain import Client, Invoice
from .pec_sender import send_via_pec
from .repository import (
    get_client_by_id,
    get_invoice_by_id,
    get_invoice_by_numero,
    get_next_numero,
    insert_client,
    insert_invoice,
    list_clients,
    list_expiring_invoices,
    list_invoices,
    search_clients,
    update_client,
    update_invoice_stato,
)
from .schemas import (
    ClientCreate,
    ClientUpdate,
    InvoiceDraft,
)
from .xml_builder import build_fattura_xml

logger = logging.getLogger(__name__)


# ── Clients ───────────────────────────────────────────────────────────────────

async def service_create_client(payload: ClientCreate, *, db: aiosqlite.Connection) -> Client:
    return await insert_client(db, payload.model_dump())


async def service_update_client(
    client_id: int, payload: ClientUpdate, *, db: aiosqlite.Connection
) -> Client | None:
    data = payload.model_dump(exclude_none=True)
    if not data:
        return await get_client_by_id(db, client_id)
    return await update_client(db, client_id, data)


async def service_list_clients(*, db: aiosqlite.Connection, active_only: bool = True) -> list[Client]:
    return await list_clients(db, active_only=active_only)


async def service_get_client(client_id: int, *, db: aiosqlite.Connection) -> Client | None:
    return await get_client_by_id(db, client_id)


# ── Invoice parse (bot flow) ──────────────────────────────────────────────────

async def parse_invoice(query: str, *, db: aiosqlite.Connection) -> InvoiceDraft:
    results = await search_clients(db, query)
    if not results:
        raise ValueError(f"Nessun cliente trovato per '{query}'")
    client = results[0]
    today = date.today()
    return InvoiceDraft(
        cliente_id=client.id,
        ragione_sociale=client.ragione_sociale,
        descrizione=client.descrizione_default or "",
        importo="0.00",
        data_emissione=today.isoformat(),
        giorni_pagamento=client.giorni_pagamento_default,
    )


# ── Invoice commit (bot flow + UI form) ───────────────────────────────────────

async def commit_invoice(
    draft: InvoiceDraft, *, db: aiosqlite.Connection, settings: Settings
) -> Invoice:
    client = await get_client_by_id(db, draft.cliente_id)
    if client is None:
        raise ValueError(f"Cliente {draft.cliente_id} non trovato")

    data_emissione = date.fromisoformat(draft.data_emissione)
    data_scadenza = data_emissione + timedelta(days=draft.giorni_pagamento)
    anno = data_emissione.year
    numero = await get_next_numero(db, anno)
    importo = Decimal(draft.importo.replace(",", "."))
    totale = importo + BOLLO_IMPORTO
    progressivo_invio = f"{anno}{numero:04d}"

    invoice = await insert_invoice(db, {
        "numero": numero,
        "anno": anno,
        "cliente_id": client.id,
        "data_emissione": data_emissione.isoformat(),
        "data_scadenza": data_scadenza.isoformat(),
        "descrizione": draft.descrizione,
        "importo": str(importo),
        "totale": str(totale),
        "stato": InvoiceStato.BOZZA,
        "progressivo_invio": progressivo_invio,
    })

    xml_bytes = build_fattura_xml(invoice, client, settings)
    filename = f"IT{settings.cedente_piva}_{progressivo_invio}.xml"

    xml_dir = settings.invoices_xml_dir
    xml_dir.mkdir(parents=True, exist_ok=True)
    xml_path = xml_dir / filename
    xml_path.write_bytes(xml_bytes)

    try:
        await send_via_pec(xml_bytes, filename, settings)
        await update_invoice_stato(db, invoice.id, InvoiceStato.INVIATA, str(xml_path))
        logger.info("Fattura %s inviata via PEC", filename)
    except Exception:
        logger.exception("Invio PEC fallito per fattura %s — rimane in stato BOZZA", filename)
        await update_invoice_stato(db, invoice.id, InvoiceStato.BOZZA, str(xml_path))

    return await get_invoice_by_id(db, invoice.id)


# ── Queries ───────────────────────────────────────────────────────────────────

async def service_list_invoices(
    *, db: aiosqlite.Connection,
    anno: int | None = None,
    stato: str | None = None,
    cliente_id: int | None = None,
) -> list[Invoice]:
    return await list_invoices(db, anno=anno, stato=stato, cliente_id=cliente_id)


async def service_get_expiring(*, db: aiosqlite.Connection) -> list[Invoice]:
    return await list_expiring_invoices(db)


async def service_get_invoice_by_numero(
    numero: int, anno: int, *, db: aiosqlite.Connection
) -> Invoice | None:
    return await get_invoice_by_numero(db, numero, anno)
