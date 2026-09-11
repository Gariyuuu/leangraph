

# ---- Guard: no test may modify the real exported site (found 2026-09-11: a test deleted site/public/figures). ----
import pathlib as _pl
import pytest as _pt

_REAL_SITE = _pl.Path(__file__).resolve().parents[1] / "site"


def _snapshot():
    out = {}
    for sub in ("public", "data"):
        d = _REAL_SITE / sub
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file():
                    st = f.stat()
                    out[str(f)] = (st.st_size, st.st_mtime_ns)
    return out


@_pt.fixture(autouse=True)
def _real_site_untouched():
    before = _snapshot()
    yield
    after = _snapshot()
    assert before == after, "a test modified the real site/ export: " + ", ".join(
        sorted(set(before) ^ set(after))[:5] or [k for k in before if before[k] != after.get(k)][:5])
