import logging
from datetime import date
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import Settings
from .constants import InvoiceStato
from .dependencies import get_db, get_settings_dep
from .domain import Client, Invoice
from .schemas import (
    ClientCreate,
    ClientResponse,
    ClientUpdate,
    CommitInvoiceResponse,
    InvoiceDraft,
    InvoiceListItem,
    InvoiceResponse,
    ParseInvoiceRequest,
    ParseInvoiceResponse,
)
from .service import (
    commit_invoice,
    parse_invoice,
    service_create_client,
    service_get_client,
    service_get_expiring,
    service_get_invoice_by_numero,
    service_list_clients,
    service_list_invoices,
    service_update_client,
)

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

api_router = APIRouter(prefix="/api", tags=["invoices"])
ui_router = APIRouter(prefix="/ui", tags=["ui"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_to_response(c: Client) -> ClientResponse:
    return ClientResponse(
        id=c.id,
        ragione_sociale=c.ragione_sociale,
        piva=c.piva,
        codice_fiscale=c.codice_fiscale,
        pec=c.pec,
        codice_destinatario=c.codice_destinatario,
        indirizzo=c.indirizzo,
        cap=c.cap,
        comune=c.comune,
        provincia=c.provincia,
        nazione=c.nazione,
        active=c.active,
        tariffa_oraria=str(c.tariffa_oraria),
        note=c.note,
        created_at=c.created_at.isoformat(),
        descrizione_default=c.descrizione_default,
        giorni_pagamento_default=c.giorni_pagamento_default,
    )


def _invoice_to_list_item(inv: Invoice, ragione_sociale: str) -> InvoiceListItem:
    return InvoiceListItem(
        id=inv.id,
        numero=inv.numero,
        anno=inv.anno,
        ragione_sociale=ragione_sociale,
        data_emissione=inv.data_emissione.isoformat(),
        data_scadenza=inv.data_scadenza.isoformat(),
        importo=str(inv.importo),
        totale=str(inv.totale),
        stato=inv.stato,
    )


def _invoice_to_response(inv: Invoice, ragione_sociale: str) -> InvoiceResponse:
    return InvoiceResponse(
        id=inv.id,
        numero=inv.numero,
        anno=inv.anno,
        cliente_id=inv.cliente_id,
        ragione_sociale=ragione_sociale,
        data_emissione=inv.data_emissione.isoformat(),
        data_scadenza=inv.data_scadenza.isoformat(),
        descrizione=inv.descrizione,
        importo=str(inv.importo),
        totale=str(inv.totale),
        stato=inv.stato,
        progressivo_invio=inv.progressivo_invio,
        xml_path=inv.xml_path,
        created_at=inv.created_at.isoformat(),
        note=inv.note,
    )


# ── JSON API — Clients ────────────────────────────────────────────────────────

@api_router.get("/clients", response_model=list[ClientResponse])
async def api_list_clients(
    active_only: bool = True,
    db: aiosqlite.Connection = Depends(get_db),
) -> list[ClientResponse]:
    clients = await service_list_clients(db=db, active_only=active_only)
    return [_client_to_response(c) for c in clients]


@api_router.post("/clients", response_model=ClientResponse)
async def api_create_client(
    payload: ClientCreate,
    db: aiosqlite.Connection = Depends(get_db),
) -> ClientResponse:
    client = await service_create_client(payload, db=db)
    return _client_to_response(client)


@api_router.get("/clients/{client_id}", response_model=ClientResponse)
async def api_get_client(
    client_id: int,
    db: aiosqlite.Connection = Depends(get_db),
) -> ClientResponse:
    client = await service_get_client(client_id, db=db)
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    return _client_to_response(client)


@api_router.put("/clients/{client_id}", response_model=ClientResponse)
async def api_update_client(
    client_id: int,
    payload: ClientUpdate,
    db: aiosqlite.Connection = Depends(get_db),
) -> ClientResponse:
    client = await service_update_client(client_id, payload, db=db)
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    return _client_to_response(client)


# ── JSON API — Invoices (bot flow) ────────────────────────────────────────────

@api_router.post("/invoices/parse", response_model=ParseInvoiceResponse)
async def api_parse_invoice(
    payload: ParseInvoiceRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> ParseInvoiceResponse:
    try:
        draft = await parse_invoice(payload.query, db=db)
        return ParseInvoiceResponse(draft=draft, success=True)
    except Exception as error:
        logger.exception("Failed to parse invoice")
        return ParseInvoiceResponse(success=False, error=str(error))


@api_router.post("/invoices/commit", response_model=CommitInvoiceResponse)
async def api_commit_invoice(
    draft: InvoiceDraft,
    db: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> CommitInvoiceResponse:
    try:
        invoice = await commit_invoice(draft, db=db, settings=settings)
        client = await service_get_client(invoice.cliente_id, db=db)
        rs = client.ragione_sociale if client else "?"
        summary = (
            f"Fattura n. {invoice.numero}/{invoice.anno} emessa per {rs} — "
            f"€ {invoice.totale} — scadenza {invoice.data_scadenza.isoformat()} — "
            f"stato: {invoice.stato}"
        )
        return CommitInvoiceResponse(
            response=summary, success=True,
            invoice_id=invoice.id, numero=invoice.numero,
        )
    except Exception as error:
        logger.exception("Failed to commit invoice")
        return CommitInvoiceResponse(response="", success=False, error=str(error))


@api_router.get("/invoices", response_model=list[InvoiceListItem])
async def api_list_invoices(
    anno: int | None = None,
    stato: str | None = None,
    cliente_id: int | None = None,
    db: aiosqlite.Connection = Depends(get_db),
) -> list[InvoiceListItem]:
    invoices = await service_list_invoices(db=db, anno=anno, stato=stato, cliente_id=cliente_id)
    result = []
    for inv in invoices:
        client = await service_get_client(inv.cliente_id, db=db)
        rs = client.ragione_sociale if client else "?"
        result.append(_invoice_to_list_item(inv, rs))
    return result


@api_router.get("/invoices/expiring", response_model=list[InvoiceListItem])
async def api_expiring_invoices(
    db: aiosqlite.Connection = Depends(get_db),
) -> list[InvoiceListItem]:
    invoices = await service_get_expiring(db=db)
    result = []
    for inv in invoices:
        client = await service_get_client(inv.cliente_id, db=db)
        rs = client.ragione_sociale if client else "?"
        result.append(_invoice_to_list_item(inv, rs))
    return result


@api_router.get("/invoices/{numero}", response_model=InvoiceResponse)
async def api_get_invoice(
    numero: int,
    anno: int | None = None,
    db: aiosqlite.Connection = Depends(get_db),
) -> InvoiceResponse:
    year = anno or date.today().year
    invoice = await service_get_invoice_by_numero(numero, year, db=db)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Fattura non trovata")
    client = await service_get_client(invoice.cliente_id, db=db)
    rs = client.ragione_sociale if client else "?"
    return _invoice_to_response(invoice, rs)


# ── UI — Clients ──────────────────────────────────────────────────────────────

@ui_router.get("/clients", response_class=HTMLResponse)
async def ui_list_clients(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
) -> HTMLResponse:
    clients = await service_list_clients(db=db, active_only=False)
    return templates.TemplateResponse(
        "clients_list.html", {"request": request, "clients": clients}
    )


@ui_router.get("/clients/new", response_class=HTMLResponse)
async def ui_new_client_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "client_form.html", {"request": request, "client": None, "action": "/ui/clients"}
    )


@ui_router.post("/clients", response_class=HTMLResponse)
async def ui_create_client(
    request: Request,
    ragione_sociale: str = Form(...),
    piva: str = Form(...),
    codice_fiscale: str = Form(...),
    pec: str = Form(...),
    codice_destinatario: str = Form(...),
    indirizzo: str = Form(...),
    cap: str = Form(...),
    comune: str = Form(...),
    provincia: str = Form(...),
    nazione: str = Form("IT"),
    tariffa_oraria: str = Form("0.00"),
    note: str = Form(None),
    descrizione_default: str = Form(None),
    giorni_pagamento_default: int = Form(30),
    db: aiosqlite.Connection = Depends(get_db),
) -> RedirectResponse:
    payload = ClientCreate(
        ragione_sociale=ragione_sociale, piva=piva,
        codice_fiscale=codice_fiscale, pec=pec,
        codice_destinatario=codice_destinatario,
        indirizzo=indirizzo, cap=cap, comune=comune,
        provincia=provincia, nazione=nazione,
        tariffa_oraria=tariffa_oraria, note=note or None,
        descrizione_default=descrizione_default or None,
        giorni_pagamento_default=giorni_pagamento_default,
    )
    await service_create_client(payload, db=db)
    return RedirectResponse("/ui/clients", status_code=303)


@ui_router.get("/clients/{client_id}/edit", response_class=HTMLResponse)
async def ui_edit_client_form(
    request: Request,
    client_id: int,
    db: aiosqlite.Connection = Depends(get_db),
) -> HTMLResponse:
    client = await service_get_client(client_id, db=db)
    if client is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "client_form.html",
        {"request": request, "client": client, "action": f"/ui/clients/{client_id}"},
    )


@ui_router.post("/clients/{client_id}", response_class=HTMLResponse)
async def ui_update_client(
    request: Request,
    client_id: int,
    ragione_sociale: str = Form(...),
    piva: str = Form(...),
    codice_fiscale: str = Form(...),
    pec: str = Form(...),
    codice_destinatario: str = Form(...),
    indirizzo: str = Form(...),
    cap: str = Form(...),
    comune: str = Form(...),
    provincia: str = Form(...),
    nazione: str = Form("IT"),
    active: str | None = Form(default=None),  # checkbox: present="on", absent=None
    tariffa_oraria: str = Form("0.00"),
    note: str = Form(None),
    descrizione_default: str = Form(None),
    giorni_pagamento_default: int = Form(30),
    db: aiosqlite.Connection = Depends(get_db),
) -> RedirectResponse:
    payload = ClientUpdate(
        ragione_sociale=ragione_sociale, piva=piva,
        codice_fiscale=codice_fiscale, pec=pec,
        codice_destinatario=codice_destinatario,
        indirizzo=indirizzo, cap=cap, comune=comune,
        provincia=provincia, nazione=nazione,
        active=(active is not None),  # unchecked = not in POST body = None = False
        tariffa_oraria=tariffa_oraria, note=note or None,
        descrizione_default=descrizione_default or None,
        giorni_pagamento_default=giorni_pagamento_default,
    )
    await service_update_client(client_id, payload, db=db)
    return RedirectResponse("/ui/clients", status_code=303)


# ── UI — Invoices ─────────────────────────────────────────────────────────────

@ui_router.get("/invoices", response_class=HTMLResponse)
async def ui_list_invoices(
    request: Request,
    anno: int | None = None,
    stato: str | None = None,
    db: aiosqlite.Connection = Depends(get_db),
) -> HTMLResponse:
    year = anno or date.today().year
    invoices = await service_list_invoices(db=db, anno=year, stato=stato)
    items = []
    for inv in invoices:
        client = await service_get_client(inv.cliente_id, db=db)
        rs = client.ragione_sociale if client else "?"
        items.append(_invoice_to_list_item(inv, rs))
    return templates.TemplateResponse(
        "invoices_list.html",
        {
            "request": request, "invoices": items,
            "selected_anno": year, "selected_stato": stato,
            "stati": list(InvoiceStato),
        },
    )


@ui_router.get("/invoices/new", response_class=HTMLResponse)
async def ui_new_invoice_form(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
) -> HTMLResponse:
    clients = await service_list_clients(db=db, active_only=True)
    today = date.today().isoformat()
    return templates.TemplateResponse(
        "invoice_new.html",
        {"request": request, "clients": clients, "today": today},
    )


@ui_router.post("/invoices", response_class=HTMLResponse)
async def ui_create_invoice(
    request: Request,
    cliente_id: int = Form(...),
    descrizione: str = Form(...),
    importo: str = Form(...),
    data_emissione: str = Form(...),
    giorni_pagamento: int = Form(30),
    db: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> RedirectResponse:
    client = await service_get_client(cliente_id, db=db)
    draft = InvoiceDraft(
        cliente_id=cliente_id,
        ragione_sociale=client.ragione_sociale if client else "",
        descrizione=descrizione,
        importo=importo,
        data_emissione=data_emissione,
        giorni_pagamento=giorni_pagamento,
    )
    await commit_invoice(draft, db=db, settings=settings)
    return RedirectResponse("/ui/invoices", status_code=303)
