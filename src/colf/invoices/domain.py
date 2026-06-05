from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Client:
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
    tariffa_oraria: Decimal
    note: str | None
    created_at: datetime
    descrizione_default: str | None
    giorni_pagamento_default: int


@dataclass(frozen=True, slots=True)
class Invoice:
    id: int
    numero: int
    anno: int
    cliente_id: int
    data_emissione: date
    data_scadenza: date
    descrizione: str
    importo: Decimal
    totale: Decimal
    stato: str
    progressivo_invio: str
    xml_path: str | None
    created_at: datetime
    updated_at: datetime
    note: str | None
