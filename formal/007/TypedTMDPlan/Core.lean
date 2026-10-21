import Std

/-!
H007 finite source/plan core.  These definitions are concrete; preservation is
NOT a field supplied by the caller.  No numerical equality oracle is used.
The Model operations are pure, fixed mathematical functions. No arithmetic
identity or real exponential law is required by the supported cache rewrite.

Build status is recorded outside this file. Source existence is not a build.
-/
namespace TypedTMDPlan

universe u

/-- Explicit two-argument congruence, keeping this library Std-only. -/
theorem congrTwo {α β γ : Sort u} (f : α → β → γ)
    {a a' : α} {b b' : β} (ha : a = a') (hb : b = b') :
    f a b = f a' b' := by
  cases ha
  cases hb
  rfl

/-- n is the complete declared parameter-interface size. -/
inductive Expr (n : Nat) where
  | var : Fin n → Expr n
  | atom : Nat → Expr n
  | unary : Nat → Expr n → Expr n
  | binary : Nat → Expr n → Expr n → Expr n
  deriving DecidableEq, Repr

/-- Frozen interpretation of all immutable atoms and primitive symbols. -/
structure Model (α : Type u) where
  atom : Nat → α
  unary : Nat → α → α
  binary : Nat → α → α → α

namespace Expr

variable {n m k : Nat} {α : Type u}

def eval (M : Model α) (θ : Fin n → α) : Expr n → α
  | .var i => θ i
  | .atom k => M.atom k
  | .unary k e => M.unary k (eval M θ e)
  | .binary k e f => M.binary k (eval M θ e) (eval M θ f)

def uses : Expr n → Fin n → Bool
  | .var i, j => decide (i = j)
  | .atom _, _ => false
  | .unary _ e, j => uses e j
  | .binary _ e f, j => uses e j || uses f j

/-- Conservative: algebraic cancellation never removes a dependency. -/
def cacheable (vary : Fin n → Bool) : Expr n → Bool
  | .var i => !(vary i)
  | .atom _ => true
  | .unary _ e => cacheable vary e
  | .binary _ e f => cacheable vary e && cacheable vary f

/-- The dependency computation, not a user-declared support, justifies equality. -/
theorem dependency_sound (M : Model α) (e : Expr n) (θ η : Fin n → α) :
    (∀ i, uses e i = true → θ i = η i) → eval M θ e = eval M η e := by
  induction e with
  | var i =>
      intro h
      exact h i (by simp [uses])
  | atom k =>
      intro _
      rfl
  | unary k e ih =>
      intro h
      exact congrArg (M.unary k) (ih (by intro i hi; exact h i hi))
  | binary k e f ihe ihf =>
      intro h
      have he : eval M θ e = eval M η e := ihe (by
        intro i hi
        apply h i
        simp [uses, hi])
      have hf : eval M θ f = eval M η f := ihf (by
        intro i hi
        apply h i
        simp [uses, hi])
      exact congrTwo (M.binary k) he hf

/-- Universal-property component: the recursive interpretation is the only
homomorphic extension of the variable assignment for this concrete signature. -/
theorem interpretation_unique (M : Model α) (θ : Fin n → α) (F : Expr n → α)
    (hvar : ∀ i, F (.var i) = θ i)
    (hatom : ∀ k, F (.atom k) = M.atom k)
    (hunary : ∀ k e, F (.unary k e) = M.unary k (F e))
    (hbinary : ∀ k e f, F (.binary k e f) = M.binary k (F e) (F f)) :
    ∀ e, F e = eval M θ e := by
  intro e
  induction e with
  | var i => exact hvar i
  | atom k => exact hatom k
  | unary k e ih =>
      exact (hunary k e).trans (congrArg (M.unary k) ih)
  | binary k e f ihe ihf =>
      exact (hbinary k e f).trans (congrTwo (M.binary k) ihe ihf)

/-- Substitution is the concrete composition operation of the source language. -/
def subst (σ : Fin n → Expr m) : Expr n → Expr m
  | .var i => σ i
  | .atom k => .atom k
  | .unary k e => .unary k (subst σ e)
  | .binary k e f => .binary k (subst σ e) (subst σ f)

theorem subst_vars (e : Expr n) : subst Expr.var e = e := by
  induction e <;> simp_all [subst]

theorem subst_comp (σ : Fin n → Expr m) (τ : Fin m → Expr k) (e : Expr n) :
    subst τ (subst σ e) = subst (fun i => subst τ (σ i)) e := by
  induction e <;> simp_all [subst]

theorem eval_subst (M : Model α) (σ : Fin n → Expr m) (e : Expr n)
    (θ : Fin m → α) :
    eval M θ (subst σ e) = eval M (fun i => eval M θ (σ i)) e := by
  induction e <;> simp_all [subst, eval]

end Expr

/-- Only coordinates declared varying may change during one cache lifetime. -/
def FixedAgreement {n : Nat} {α : Type u} (vary : Fin n → Bool)
    (θ0 θ : Fin n → α) : Prop :=
  ∀ i, vary i = false → θ i = θ0 i

variable {n m : Nat} {α : Type u}

theorem cacheable_sound (M : Model α) (vary : Fin n → Bool)
    (θ0 θ : Fin n → α) (fixed : FixedAgreement vary θ0 θ) (e : Expr n) :
    Expr.cacheable vary e = true → Expr.eval M θ e = Expr.eval M θ0 e := by
  induction e with
  | var i =>
      intro h
      have hi : vary i = false := by
        cases hv : vary i <;> simp_all [Expr.cacheable]
      exact fixed i hi
  | atom k =>
      intro _
      rfl
  | unary k e ih =>
      intro h
      exact congrArg (M.unary k) (ih h)
  | binary k e f ihe ihf =>
      intro h
      have hs : Expr.cacheable vary e = true ∧ Expr.cacheable vary f = true := by
        simpa only [Expr.cacheable, Bool.and_eq_true] using h
      exact congrTwo (M.binary k) (ihe hs.1) (ihf hs.2)

/-- The mask side condition needed when changing parameter interfaces. -/
theorem cacheable_subst (σ : Fin n → Expr m) (source : Fin m → Bool)
    (target : Fin n → Bool)
    (pres : ∀ i, target i = false → Expr.cacheable source (σ i) = true)
    (e : Expr n) :
    Expr.cacheable target e = true → Expr.cacheable source (Expr.subst σ e) = true := by
  induction e with
  | var i =>
      intro h
      have hi : target i = false := by
        cases hv : target i <;> simp_all [Expr.cacheable]
      exact pres i hi
  | atom k =>
      intro _
      rfl
  | unary k e ih =>
      intro h
      exact ih h
  | binary k e f ihe ihf =>
      intro h
      have hs : Expr.cacheable target e = true ∧ Expr.cacheable target f = true := by
        simpa only [Expr.cacheable, Bool.and_eq_true] using h
      have he := ihe hs.1
      have hf := ihf hs.2
      simp only [Expr.subst, Expr.cacheable, he, hf, Bool.true_and]

/-- Cache leaves retain the exact source subtree. Arbitrary numeric cache tables
are not accepted as evidence. Runtime initialization evaluates the subtree at θ0. -/
inductive Plan (n : Nat) where
  | live : Expr n → Plan n
  | cache : Expr n → Plan n
  | unary : Nat → Plan n → Plan n
  | binary : Nat → Plan n → Plan n → Plan n
  deriving DecidableEq, Repr

namespace Plan

def erase : Plan n → Expr n
  | .live e => e
  | .cache e => e
  | .unary k p => .unary k (erase p)
  | .binary k p q => .binary k (erase p) (erase q)

def safe (vary : Fin n → Bool) : Plan n → Bool
  | .live _ => true
  | .cache e => Expr.cacheable vary e
  | .unary _ p => safe vary p
  | .binary _ p q => safe vary p && safe vary q

def eval (M : Model α) (θ0 θ : Fin n → α) : Plan n → α
  | .live e => Expr.eval M θ e
  | .cache e => Expr.eval M θ0 e
  | .unary k p => M.unary k (eval M θ0 θ p)
  | .binary k p q => M.binary k (eval M θ0 θ p) (eval M θ0 θ q)

theorem safe_sound (M : Model α) (vary : Fin n → Bool)
    (θ0 θ : Fin n → α) (fixed : FixedAgreement vary θ0 θ) (p : Plan n) :
    safe vary p = true → eval M θ0 θ p = Expr.eval M θ (erase p) := by
  induction p with
  | live e =>
      intro _
      rfl
  | cache e =>
      intro h
      exact (cacheable_sound M vary θ0 θ fixed e h).symm
  | unary k p ih =>
      intro h
      exact congrArg (M.unary k) (ih h)
  | binary k p q ihp ihq =>
      intro h
      have hs : safe vary p = true ∧ safe vary q = true := by
        simpa only [safe, Bool.and_eq_true] using h
      exact congrTwo (M.binary k) (ihp hs.1) (ihq hs.2)

end Plan

/-- The actual, deliberately incomplete translation validator. -/
def check (vary : Fin n → Bool) (source : Expr n) (candidate : Plan n) : Bool :=
  decide (candidate.erase = source) && candidate.safe vary

/-- Main guarantee: every accepted plan preserves the entire admitted parameter
family. It is independent of the proposer and is not inferred from samples. -/
theorem check_sound (M : Model α) (vary : Fin n → Bool)
    (θ0 θ : Fin n → α) (source : Expr n) (candidate : Plan n)
    (fixed : FixedAgreement vary θ0 θ)
    (accepted : check vary source candidate = true) :
    Plan.eval M θ0 θ candidate = Expr.eval M θ source := by
  have parts : decide (candidate.erase = source) = true ∧ candidate.safe vary = true :=
    by simpa only [check, Bool.and_eq_true] using accepted
  have he : candidate.erase = source := of_decide_eq_true parts.1
  calc
    Plan.eval M θ0 θ candidate = Expr.eval M θ candidate.erase :=
      Plan.safe_sound M vary θ0 θ fixed candidate parts.2
    _ = Expr.eval M θ source := congrArg (fun e => Expr.eval M θ e) he

theorem live_accepted (vary : Fin n → Bool) (e : Expr n) :
    check vary e (.live e) = true := by
  simp [check, Plan.erase, Plan.safe]

#print axioms Expr.dependency_sound
#print axioms Expr.interpretation_unique
#print axioms Expr.eval_subst
#print axioms cacheable_sound
#print axioms cacheable_subst
#print axioms check_sound

end TypedTMDPlan
