import Mathlib

/-!
For each candidate benchmark theorem (names read from `LG_CANDIDATES_IN`),
emit one JSON line with the constants its statement and its proof use (with
their modules), its source range, and the depth of its statement expression.
The proof constants are the retrieval ground truth; the rest feed the
difficulty proxies and the held-out filter.
-/

open Lean Meta Elab Command

set_option maxHeartbeats 0

def lgMod (env : Environment) (c : Name) : String :=
  match env.getModuleIdxFor? c with
  | some i => toString (env.header.moduleNames[i.toNat]!)
  | none => "_"

def lgProofConsts (env : Environment) (root : Name) : Array Name := Id.run do
  let mut todo := #[root]
  let mut seen : NameSet := {}
  let mut out : Array Name := #[]
  let mut outSeen : NameSet := {}
  while !todo.isEmpty do
    let n := todo.back!
    todo := todo.pop
    if seen.contains n then continue
    seen := seen.insert n
    let some ci := env.find? n | continue
    let some v := ci.value? (allowOpaque := true) | continue
    for c in v.getUsedConstants do
      if c == root then continue
      if root.isPrefixOf c || c.isInternalDetail then
        todo := todo.push c
      else if !outSeen.contains c then
        outSeen := outSeen.insert c
        out := out.push c
  return out

#eval show CommandElabM Unit from do
  let env ← getEnv
  let inPath := (← IO.getEnv "LG_CANDIDATES_IN").getD "candidates.txt"
  let outPath := (← IO.getEnv "LG_CANDIDATES_OUT").getD "candidates_meta.jsonl"
  let names ← IO.FS.lines inPath
  let h ← IO.FS.Handle.mk outPath .write
  for s in names do
    let n := s.toName
    match env.find? n with
    | none => h.putStrLn ((Json.mkObj [("name", toJson s), ("missing", toJson true)]).compress)
    | some ci =>
      let tyConsts := ci.type.getUsedConstants.map fun c => #[c.toString, lgMod env c]
      let pfConsts := (lgProofConsts env n).map fun c => #[c.toString, lgMod env c]
      let rng ← findDeclarationRanges? n
      let (sl, el) := match rng with
        | some r => (r.range.pos.line, r.range.endPos.line)
        | none => (0, 0)
      let hasValue := (ci.value? (allowOpaque := true)).isSome
      let j := Json.mkObj [("name", toJson s), ("type_consts", toJson tyConsts),
        ("proof_consts", toJson pfConsts), ("start_line", toJson sl), ("end_line", toJson el),
        ("type_depth", toJson ci.type.approxDepth.toNat), ("has_value", toJson hasValue)]
      h.putStrLn j.compress
  IO.println s!"LG_META {names.size}"
