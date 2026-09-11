from leangraph.corpus import _IMPORT, downstream, reverse_graph, roundtrip_command, split_signature, statement_of


def test_split_signature_with_universes_and_instances():
    sig = "Foo.bar.{u_1} {α : Type u_1} [inst : Group α] (a : α) :\n  a * 1 = a"
    assert split_signature("Foo.bar", sig) == ("{α : Type u_1} [inst : Group α] (a : α)", "a * 1 = a")


def test_split_signature_without_binders():
    assert split_signature("Foo", "Foo : 1 + 1 = 2") == ("", "1 + 1 = 2")


def test_split_signature_ignores_colons_inside_binders():
    sig = "Foo (f : ℕ → ℕ) (h : ∀ x : ℕ, f x = x) : f 0 = 0"
    assert split_signature("Foo", sig) == ("(f : ℕ → ℕ) (h : ∀ x : ℕ, f x = x)", "f 0 = 0")


def test_split_signature_rejects_foreign_name():
    assert split_signature("Foo", "Bar : True") is None


def test_statement_and_roundtrip_forms():
    assert statement_of("(a : ℕ)", "a = a") == "(a : ℕ) : a = a"
    assert statement_of("", "True") == ": True"
    assert roundtrip_command("(a : ℕ)", "a = a", "X.y") == "example : ∀ (a : ℕ), a = a := @X.y"
    assert roundtrip_command("", "True", "X.y") == "example : True := @X.y"


def test_import_regex_handles_module_system():
    head = "module\n\npublic import Mathlib.A\npublic meta import Mathlib.B\nimport Mathlib.C\nimport all Mathlib.D\n"
    assert _IMPORT.findall(head) == ["Mathlib.A", "Mathlib.B", "Mathlib.C", "Mathlib.D"]


def test_downstream_closure_and_cap():
    g = {"A": [], "B": ["A"], "C": ["B"], "D": ["C"], "E": ["A"]}
    rev = reverse_graph(g)
    assert downstream(rev, "A") == {"B", "C", "D", "E"}
    assert downstream(rev, "D") == set()
    assert len(downstream(rev, "A", cap=1)) == 2  # stops as soon as the cap is exceeded
