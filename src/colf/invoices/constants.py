from decimal import Decimal
from enum import StrEnum

FATTURA_NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
FATTURA_VERSIONE = "FPR12"

BOLLO_IMPORTO = Decimal("2.00")


class InvoiceStato(StrEnum):
    BOZZA = "BOZZA"
    INVIATA = "INVIATA"
    CONSEGNATA = "CONSEGNATA"
    SCARTATA = "SCARTATA"
    PAGATA = "PAGATA"


CAUSALI: tuple[str, ...] = (
    (
        "Operazione effettuata in regime forfettario ai sensi dell'art. 1, "
        "commi da 54 a 89, della Legge n. 190/2014 e successive modificazioni"
    ),
    (
        "Operazione in franchigia da IVA ai sensi della Legge 190 del 23 "
        "dicembre 2014 art.1 commi da 54 a 89"
    ),
    (
        "Operazione non soggetta a ritenuta alla fonte a titolo di acconto "
        "ai sensi dell'articolo 1, comma 67, Legge n. 190 del 2014 e "
        "successive modificazioni"
    ),
)

SDI_PEC = "sdi01@pec.fatturapa.it"
