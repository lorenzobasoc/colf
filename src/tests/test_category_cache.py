from colf.expenses.category_cache import CategoryCache


class TestCategoryCacheLookup:
    def test_lookup_su_cache_vuota_none(self):
        cache = CategoryCache(loader=lambda: [])
        assert cache.lookup("Driutti") is None

    def test_lookup_case_insensitive(self):
        cache = CategoryCache(loader=lambda: [("Driutti", "🍺 Bar")])
        assert cache.lookup("driutti") == "🍺 Bar"

    def test_lookup_ignora_spazi(self):
        cache = CategoryCache(loader=lambda: [("Driutti", "🍺 Bar")])
        assert cache.lookup("  Driutti  ") == "🍺 Bar"

    def test_lookup_vuoto_non_seeda(self):
        calls = []

        def loader():
            calls.append(1)
            return []

        cache = CategoryCache(loader=loader)
        assert cache.lookup("") is None
        assert cache.lookup("   ") is None
        assert calls == []


class TestCategoryCacheRemember:
    def test_remember_poi_lookup(self):
        cache = CategoryCache(loader=lambda: [])
        cache.remember("Driutti", "🍺 Bar")
        assert cache.lookup("Driutti") == "🍺 Bar"
        assert cache.lookup("driutti") == "🍺 Bar"

    def test_remember_sovrascrive(self):
        cache = CategoryCache(loader=lambda: [])
        cache.remember("Driutti", "🍺 Bar")
        cache.remember("driutti", "🍿 Intrattenimento")
        assert cache.lookup("Driutti") == "🍿 Intrattenimento"

    def test_remember_ignora_descrizione_vuota(self):
        cache = CategoryCache(loader=lambda: [])
        cache.remember("", "🍺 Bar")
        cache.remember("   ", "🍺 Bar")
        assert cache.lookup("") is None

    def test_remember_ignora_categoria_vuota(self):
        cache = CategoryCache(loader=lambda: [])
        cache.remember("Driutti", "")
        assert cache.lookup("Driutti") is None


class TestCategoryCacheSeed:
    def test_seed_una_sola_volta(self):
        calls = []

        def loader():
            calls.append(1)
            return [("Driutti", "🍺 Bar")]

        cache = CategoryCache(loader=loader)
        cache.lookup("Driutti")
        cache.lookup("driutti")
        cache.lookup("altro")
        assert calls == [1]

    def test_seed_case_insensitive(self):
        cache = CategoryCache(loader=lambda: [("Driutti", "🍺 Bar")])
        assert cache.lookup("Driutti") == "🍺 Bar"
        assert cache.lookup("driutti") == "🍺 Bar"

    def test_seed_ultimo_vince(self):
        cache = CategoryCache(
            loader=lambda: [
                ("Bar Sport", "🍺 Bar"),
                ("bar sport", "🍿 Intrattenimento"),
            ]
        )
        assert cache.lookup("Bar Sport") == "🍿 Intrattenimento"

    def test_seed_fallisce_silenziosamente(self):
        calls = []

        def loader():
            calls.append(1)
            raise RuntimeError("boom")

        cache = CategoryCache(loader=loader)
        assert cache.lookup("Driutti") is None
        assert cache.lookup("Driutti") is None
        assert calls == [1]
