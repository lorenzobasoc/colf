from decimal import Decimal

from lxml import etree

from ..config import Settings
from .constants import BOLLO_IMPORTO, CAUSALI, FATTURA_NS, FATTURA_VERSIONE
from .domain import Client, Invoice


def _el(parent: etree._Element, tag: str, text: str | None = None) -> etree._Element:
    el = etree.SubElement(parent, tag)  # figli non qualificati (elementFormDefault=unqualified)
    if text is not None:
        el.text = text
    return el


def _fmt(value: Decimal) -> str:
    return f"{value:.2f}"


def build_fattura_xml(invoice: Invoice, client: Client, settings: Settings) -> bytes:
    nsmap = {"p": FATTURA_NS}
    root = etree.Element(f"{{{FATTURA_NS}}}FatturaElettronica", nsmap=nsmap)
    root.set("versione", FATTURA_VERSIONE)

    # ── Header ────────────────────────────────────────────────────────────────
    header = _el(root, "FatturaElettronicaHeader")

    dati_tx = _el(header, "DatiTrasmissione")
    id_tx = _el(dati_tx, "IdTrasmittente")
    _el(id_tx, "IdPaese", "IT")
    _el(id_tx, "IdCodice", settings.cedente_cf)
    _el(dati_tx, "ProgressivoInvio", invoice.progressivo_invio)
    _el(dati_tx, "FormatoTrasmissione", FATTURA_VERSIONE)
    _el(dati_tx, "CodiceDestinatario", client.codice_destinatario)

    cedente = _el(header, "CedentePrestatore")
    dati_an_ced = _el(cedente, "DatiAnagrafici")
    id_iva_ced = _el(dati_an_ced, "IdFiscaleIVA")
    _el(id_iva_ced, "IdPaese", "IT")
    _el(id_iva_ced, "IdCodice", settings.cedente_piva)
    _el(dati_an_ced, "CodiceFiscale", settings.cedente_cf)
    anagrafica_ced = _el(dati_an_ced, "Anagrafica")
    _el(anagrafica_ced, "Nome", settings.cedente_nome)
    _el(anagrafica_ced, "Cognome", settings.cedente_cognome)
    _el(dati_an_ced, "RegimeFiscale", "RF19")
    sede_ced = _el(cedente, "Sede")
    _el(sede_ced, "Indirizzo", settings.cedente_indirizzo)
    _el(sede_ced, "CAP", settings.cedente_cap)
    _el(sede_ced, "Comune", settings.cedente_comune)
    _el(sede_ced, "Provincia", settings.cedente_provincia)
    _el(sede_ced, "Nazione", "IT")

    cessionario = _el(header, "CessionarioCommittente")
    dati_an_ces = _el(cessionario, "DatiAnagrafici")
    id_iva_ces = _el(dati_an_ces, "IdFiscaleIVA")
    _el(id_iva_ces, "IdPaese", "IT")
    _el(id_iva_ces, "IdCodice", client.piva)
    _el(dati_an_ces, "CodiceFiscale", client.codice_fiscale)
    anagrafica_ces = _el(dati_an_ces, "Anagrafica")
    _el(anagrafica_ces, "Denominazione", client.ragione_sociale)
    sede_ces = _el(cessionario, "Sede")
    _el(sede_ces, "Indirizzo", client.indirizzo)
    _el(sede_ces, "CAP", client.cap)
    _el(sede_ces, "Comune", client.comune)
    _el(sede_ces, "Provincia", client.provincia)
    _el(sede_ces, "Nazione", client.nazione)

    # ── Body ──────────────────────────────────────────────────────────────────
    body = _el(root, "FatturaElettronicaBody")

    dati_gen = _el(body, "DatiGenerali")
    dati_gen_doc = _el(dati_gen, "DatiGeneraliDocumento")
    _el(dati_gen_doc, "TipoDocumento", "TD01")
    _el(dati_gen_doc, "Divisa", "EUR")
    _el(dati_gen_doc, "Data", invoice.data_emissione.isoformat())
    _el(dati_gen_doc, "Numero", str(invoice.numero))
    dati_bollo = _el(dati_gen_doc, "DatiBollo")
    _el(dati_bollo, "BolloVirtuale", "SI")
    _el(dati_bollo, "ImportoBollo", _fmt(BOLLO_IMPORTO))
    _el(dati_gen_doc, "ImportoTotaleDocumento", _fmt(invoice.totale))
    for causale in CAUSALI:
        _el(dati_gen_doc, "Causale", causale)

    dati_beni = _el(body, "DatiBeniServizi")
    linea = _el(dati_beni, "DettaglioLinee")
    _el(linea, "NumeroLinea", "1")
    _el(linea, "Descrizione", invoice.descrizione)
    _el(linea, "PrezzoUnitario", _fmt(invoice.importo))
    _el(linea, "PrezzoTotale", _fmt(invoice.importo))
    _el(linea, "AliquotaIVA", "0.00")
    _el(linea, "Natura", "N2.2")
    riepilogo = _el(dati_beni, "DatiRiepilogo")
    _el(riepilogo, "AliquotaIVA", "0.00")
    _el(riepilogo, "Natura", "N2.2")
    _el(riepilogo, "ImponibileImporto", _fmt(invoice.importo))
    _el(riepilogo, "Imposta", "0.00")

    dati_pag = _el(body, "DatiPagamento")
    _el(dati_pag, "CondizioniPagamento", "TP02")
    det_pag = _el(dati_pag, "DettaglioPagamento")
    _el(det_pag, "ModalitaPagamento", "MP05")
    _el(det_pag, "DataRiferimentoTerminiPagamento", invoice.data_emissione.isoformat())
    giorni = (invoice.data_scadenza - invoice.data_emissione).days
    _el(det_pag, "GiorniTerminiPagamento", str(giorni))
    _el(det_pag, "DataScadenzaPagamento", invoice.data_scadenza.isoformat())
    _el(det_pag, "ImportoPagamento", _fmt(invoice.totale))
    _el(det_pag, "IBAN", settings.cedente_iban)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
