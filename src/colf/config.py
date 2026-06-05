import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]


@dataclass(frozen=True, slots=True)
class Settings:
    # existing
    llm_model_path: Path
    service_account_path: Path
    # cedente (fixed, read from .env)
    cedente_nome: str
    cedente_cognome: str
    cedente_piva: str
    cedente_cf: str
    cedente_indirizzo: str
    cedente_cap: str
    cedente_comune: str
    cedente_provincia: str
    cedente_iban: str
    # PEC credentials
    pec_host: str
    pec_port: int
    pec_user: str
    pec_password: str
    # storage
    sqlite_path: Path
    invoices_xml_dir: Path


def _resolve(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


@lru_cache
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        llm_model_path=PACKAGE_DIR / "models" / os.environ["LLM_NAME"],
        service_account_path=_resolve(os.environ["SERVICE_ACCOUNT_PATH"]),
        cedente_nome=os.environ["CEDENTE_NOME"],
        cedente_cognome=os.environ["CEDENTE_COGNOME"],
        cedente_piva=os.environ["CEDENTE_PIVA"],
        cedente_cf=os.environ["CEDENTE_CF"],
        cedente_indirizzo=os.environ["CEDENTE_INDIRIZZO"],
        cedente_cap=os.environ["CEDENTE_CAP"],
        cedente_comune=os.environ["CEDENTE_COMUNE"],
        cedente_provincia=os.environ["CEDENTE_PROVINCIA"],
        cedente_iban=os.environ["CEDENTE_IBAN"],
        pec_host=os.environ["PEC_HOST"],
        pec_port=int(os.environ["PEC_PORT"]),
        pec_user=os.environ["PEC_USER"],
        pec_password=os.environ["PEC_PASSWORD"],
        sqlite_path=_resolve(os.environ.get("SQLITE_PATH", "data/colf.db")),
        invoices_xml_dir=_resolve(os.environ.get("INVOICES_XML_DIR", "data/invoices/xml")),
    )
