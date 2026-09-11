import Mathlib

/-!
Dump every Mathlib theorem as one JSON line: name, module, pretty-printed
signature, docstring, source line. This is the retrieval corpus; nothing in it
is written by hand, so no premise can be invented.
-/

open Lean Meta Elab Command

set_option maxHeartbeats 0

def lgModuleOf (env : Environment) (n : Name) : Option Name :=
  (env.getModuleIdxFor? n).map fun i => env.header.moduleNames[i.toNat]!

#eval show CommandElabM Unit from do
  let env ← getEnv
  let path := (← IO.getEnv "LG_PREMISES_OUT").getD "premises.jsonl"
  let h ← IO.FS.Handle.mk path .write
  let mut count := 0
  let mut failed := 0
  for (n, ci) in env.constants.map₁.toList do
    let .thmInfo _ := ci | continue
    if n.isInternalDetail then continue
    let some mod := lgModuleOf env n | continue
    unless (`Mathlib).isPrefixOf mod do continue
    let sig ← liftTermElabM do
      try
        let f ← PrettyPrinter.ppSignature n
        pure (some f.fmt.pretty)
      catch _ => pure none
    let some sig := sig | failed := failed + 1; continue
    let doc ← findDocString? env n
    let rng ← findDeclarationRanges? n
    let line := (rng.map (·.range.pos.line)).getD 0
    let j := Json.mkObj [("name", toJson n.toString), ("module", toJson mod.toString),
      ("signature", toJson sig), ("doc", toJson doc), ("line", toJson line)]
    h.putStrLn j.compress
    count := count + 1
  IO.println s!"LG_EXTRACTED {count} LG_FAILED {failed}"
