import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Il loader ritorna coppie (descrizione, categoria) in ordine cronologico:
# le occorrenze piu' recenti vincono (sovrascrivono).
Loader = Callable[[], list[tuple[str, str]]]


class CategoryCache:
    """Mappa in memoria descrizione(lower) -> categoria display, per evitare
    di richiamare l'LLM su descrizioni gia' categorizzate (es. "Driutti" -> Bar).

    Seed una sola volta dalle spese precedenti (Google Sheet), poi aggiornata
    a ogni commit con la categoria confermata dall'utente."""

    def __init__(self, loader: Loader) -> None:
        self._loader = loader
        self._entries: dict[str, str] = {}
        self._seeded = False

    @staticmethod
    def _key(description: str) -> str:
        return description.strip().casefold()

    def _ensure_seeded(self) -> None:
        if self._seeded:
            return
        # Segna come seeded PRIMA del load: un errore non deve ritentare a ogni lookup.
        self._seeded = True
        try:
            for description, category in self._loader():
                self.remember(description, category)
            logger.info("Category cache seeded with %d entries", len(self._entries))
        except Exception:
            logger.exception("Failed to seed category cache from previous expenses")

    def lookup(self, description: str) -> str | None:
        key = self._key(description)
        if not key:
            return None
        self._ensure_seeded()
        return self._entries.get(key)

    def remember(self, description: str, category: str) -> None:
        key = self._key(description)
        if not key or not category:
            return
        self._entries[key] = category
