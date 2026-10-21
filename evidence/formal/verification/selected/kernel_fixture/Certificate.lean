import TypedTMDPlan.Core
open TypedTMDPlan
namespace WireCertificate
-- wire_sha256: da79972f25a8d4cbd5751a7d14d0b454c41f97ce615e162d8ab802cafae04402
set_option maxRecDepth 100000
set_option maxHeartbeats 0
def varies : Fin 2 → Bool := fun i =>
  if i.val = 0 then true else (if i.val = 1 then true else (false))
def e0 : Expr 2 := .atom 0
def e1 : Expr 2 := .var ⟨1, by decide⟩
def e2 : Expr 2 := .atom 1
def e3 : Expr 2 := .binary 1 e1 e2
def e4 : Expr 2 := .binary 0 e0 e3
def e5 : Expr 2 := .unary 0 e4
def e6 : Expr 2 := .var ⟨0, by decide⟩
def e7 : Expr 2 := .atom 2
def e8 : Expr 2 := .binary 1 e6 e7
def e9 : Expr 2 := .unary 0 e8
def e10 : Expr 2 := .binary 1 e5 e9
def p0 : Plan 2 := .cache e0
def p1 : Plan 2 := .live e1
def p2 : Plan 2 := .cache e2
def p3 : Plan 2 := .binary 1 p1 p2
def p4 : Plan 2 := .binary 0 p0 p3
def p5 : Plan 2 := .unary 0 p4
def p6 : Plan 2 := .live e6
def p7 : Plan 2 := .cache e7
def p8 : Plan 2 := .binary 1 p6 p7
def p9 : Plan 2 := .unary 0 p8
def p10 : Plan 2 := .binary 1 p5 p9
theorem accepted_0 : check varies e10 p10 = true := by decide
theorem preservation_0 {α : Type} (M : Model α)
    (θ0 θ : Fin 2 → α) (fixed : FixedAgreement varies θ0 θ) :
    Plan.eval M θ0 θ p10 = Expr.eval M θ e10 :=
  check_sound M varies θ0 θ e10 p10 fixed accepted_0
#print axioms preservation_0
end WireCertificate
