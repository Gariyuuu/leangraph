import Mathlib

/-! Every non-internal constant name in the pinned environment, one per line.
Used only to tell a wrong-namespace name from a hallucinated one. -/

open Lean Elab Command

#eval show CommandElabM Unit from do
  let env ← getEnv
  let path := (← IO.getEnv "LG_NAMES_OUT").getD "all_names.txt"
  let h ← IO.FS.Handle.mk path .write
  let mut n := 0
  for (c, _) in env.constants.map₁.toList do
    if c.isInternalDetail then continue
    h.putStrLn c.toString
    n := n + 1
  IO.println s!"LG_NAMES {n}"
