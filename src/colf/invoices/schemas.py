from pydantic import BaseModel


class ClientCreate(BaseModel):
    ragione_sociale: str
    piva: str
    codice_fiscale: str
    pec: str
    codice_destinatario: str
    indirizzo: str
    cap: str
    comune: str
    provincia: str
    nazione: str = "IT"
    tariffa_oraria: str  # stored as string to avoid float drift
    note: str | None = None
    descrizione_default: str | None = None
    giorni_pagamento_default: int = 30


class ClientUpdate(BaseModel):
    ragione_sociale: str | None = None
    piva: str | None = None
    codice_fiscale: str | None = None
    pec: str | None = None
    codice_destinatario: str | None = None
    indirizzo: str | None = None
    cap: str | None = None
    comune: str | None = None
    provincia: str | None = None
    nazione: str | None = None
    active: bool | None = None
    tariffa_oraria: str | None = None
    note: str | None = None
    descrizione_default: str | None = None
    giorni_pagamento_default: int | None = None


class ClientResponse(BaseModel):
    id: int
    ragione_sociale: str
    piva: str
    codice_fiscale: str
    pec: str
    codice_destinatario: str
    indirizzo: str
    cap: str
    comune: str
    provincia: str
    nazione: str
    active: bool
    tariffa_oraria: str
    note: str | None
    created_at: str
    descrizione_default: str | None
    giorni_pagamento_default: int


class InvoiceDraft(BaseModel):
    """Bot-facing draft: what the Telegram bot shows and edits before commit."""
    cliente_id: int
    ragione_sociale: str  # display only
    descrizione: str
    importo: str  # e.g. "1000.00"
    data_emissione: str  # "YYYY-MM-DD"
    giorni_pagamento: int


class ParseInvoiceRequest(BaseModel):
    query: str


class ParseInvoiceResponse(BaseModel):
    draft: InvoiceDraft | None = None
    success: bool
    error: str | None = None


class CommitInvoiceResponse(BaseModel):
    response: str
    success: bool
    error: str | None = None
    invoice_id: int | None = None
    numero: int | None = None


class InvoiceListItem(BaseModel):
    id: int
    numero: int
    anno: int
    ragione_sociale: str
    data_emissione: str
    data_scadenza: str
    importo: str
    totale: str
    stato: str


class InvoiceResponse(BaseModel):
    id: int
    numero: int
    anno: int
    cliente_id: int
    ragione_sociale: str
    data_emissione: str
    data_scadenza: str
    descrizione: str
    importo: str
    totale: str
    stato: str
    progressivo_invio: str
    xml_path: str | None
    created_at: str
    note: str | None
