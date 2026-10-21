import TypedTMDPlan.Core
import TypedTMDPlan.Category

namespace TypedTMDPlan.Examples
open TypedTMDPlan

def varying : Fin 2 → Bool := fun _ => true

def a : Expr 2 := .var ⟨0, by decide⟩
def g : Expr 2 := .var ⟨1, by decide⟩
/-- Atom 0 = R, atom 1 = -b² log(Q/QA), atom 2 = -b² in the Python fixture.
Unary symbol 0 = exp; binary symbols 0/1 = add/mul. These assignments are fixed
in the bridge context and not needed for structural dependency correctness. -/
def transport : Expr 2 := .unary 0 (.binary 0 (.atom 0) (.binary 1 g (.atom 1)))
def boundary : Expr 2 := .unary 0 (.binary 1 a (.atom 2))
def source : Expr 2 := .binary 1 transport boundary

def good : Plan 2 := .binary 1
  (.unary 0 (.binary 0 (.cache (.atom 0)) (.binary 1 (.live g) (.cache (.atom 1)))))
  (.unary 0 (.binary 1 (.live a) (.cache (.atom 2))))

def bad : Plan 2 := .binary 1 (.cache transport) (.live boundary)

theorem good_accepts : check varying source good = true := by decide
theorem bad_rejects : check varying source bad = false := by decide

theorem good_preserves {α : Type} (M : Model α) (θ0 θ : Fin 2 → α) :
    Plan.eval M θ0 θ good = Expr.eval M θ source := by
  apply check_sound M varying θ0 θ source good
  · intro i hi
    simp [varying] at hi
  · exact good_accepts

/-- A valid specialization is a DIFFERENT varying interface. -/
def onlyA : Fin 2 → Bool := fun i => decide (i.val = 0)
theorem fixed_g_cache_is_admissible : check onlyA source bad = true := by decide

/-- Noninvertible observation: a weighted sum of two native samples. No inverse
constructor is provided or claimed. -/
def quadrature : Expr 2 :=
  .binary 0 (.binary 1 (.atom 0) a) (.binary 1 (.atom 1) g)

def quadraturePlan : Plan 2 :=
  .binary 0 (.binary 1 (.cache (.atom 0)) (.live a))
    (.binary 1 (.cache (.atom 1)) (.live g))

theorem quadrature_accepts : check varying quadrature quadraturePlan = true := by decide

#print axioms good_preserves
#print axioms bad_rejects
#print axioms fixed_g_cache_is_admissible

end TypedTMDPlan.Examples
