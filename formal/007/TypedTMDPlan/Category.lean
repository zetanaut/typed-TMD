import TypedTMDPlan.Core

/-!
A concrete mask-indexed term category, without a mathlib dependency. We provide
objects, arrows, identity, composition, and the category/functor laws directly.
The fixed interpretation Model is the immutable scientific/numerical context.
Changing it is NOT a morphism granted by this construction.
-/
namespace TypedTMDPlan
namespace Category

universe u

structure Interface where
  size : Nat
  varies : Fin size → Bool

/-- Target coordinates declared fixed may depend only on source-fixed data. -/
structure Arrow (X Y : Interface) where
  terms : Fin Y.size → Expr X.size
  admissible : ∀ j, Y.varies j = false → Expr.cacheable X.varies (terms j) = true

namespace Arrow

variable {X Y Z W : Interface}

theorem ext (f g : Arrow X Y) (h : ∀ j, f.terms j = g.terms j) : f = g := by
  cases f with
  | mk ft hf =>
    cases g with
    | mk gt hg =>
      have hfg : ft = gt := funext h
      cases hfg
      rfl

def id (X : Interface) : Arrow X X where
  terms := Expr.var
  admissible j hj := by simp [Expr.cacheable, hj]

/-- g after f: concrete substitution, not an assumed semantic equality. -/
def comp (g : Arrow Y Z) (f : Arrow X Y) : Arrow X Z where
  terms j := Expr.subst f.terms (g.terms j)
  admissible j hj :=
    cacheable_subst f.terms X.varies Y.varies f.admissible (g.terms j) (g.admissible j hj)

theorem id_comp (f : Arrow X Y) : comp (id Y) f = f := by
  apply ext
  intro j
  rfl

theorem comp_id (f : Arrow X Y) : comp f (id X) = f := by
  apply ext
  intro j
  exact Expr.subst_vars (f.terms j)

theorem comp_assoc (h : Arrow Z W) (g : Arrow Y Z) (f : Arrow X Y) :
    comp h (comp g f) = comp (comp h g) f := by
  apply ext
  intro j
  exact (Expr.subst_comp g.terms f.terms (h.terms j)).symm

/-- Interpretation functor into functions between finite environment spaces. -/
def interpret {α : Type u} (M : Model α) (f : Arrow X Y)
    (θ : Fin X.size → α) : Fin Y.size → α :=
  fun j => Expr.eval M θ (f.terms j)

theorem interpret_id {α : Type u} (M : Model α) (X : Interface) :
    interpret M (id X) = (fun θ => θ) := by
  rfl

theorem interpret_comp {α : Type u} (M : Model α) (g : Arrow Y Z) (f : Arrow X Y) :
    interpret M (comp g f) = (fun θ => interpret M g (interpret M f θ)) := by
  funext θ j
  exact Expr.eval_subst M f.terms (g.terms j) θ

/-- Arrows send an allowed variation slice to the correctly transported slice. -/
theorem fixed_slice_preserved {α : Type u} (M : Model α) (f : Arrow X Y)
    (θ0 θ : Fin X.size → α) (fixed : FixedAgreement X.varies θ0 θ) :
    FixedAgreement Y.varies (interpret M f θ0) (interpret M f θ) := by
  intro j hj
  exact cacheable_sound M X.varies θ0 θ fixed (f.terms j) (f.admissible j hj)

/-- Locally checked plans compose with TRANSPORTED cache reference values.
Reusing an unrelated second-stage reference is not asserted sound. -/
theorem checked_composition {α : Type u} (M : Model α)
    (f : Arrow X Y) (g : Arrow Y Z)
    (pf : Fin Y.size → Plan X.size) (pg : Fin Z.size → Plan Y.size)
    (hf : ∀ j, check X.varies (f.terms j) (pf j) = true)
    (hg : ∀ j, check Y.varies (g.terms j) (pg j) = true)
    (θ0 θ : Fin X.size → α) (fixed : FixedAgreement X.varies θ0 θ) :
    (fun j => Plan.eval M (interpret M f θ0)
      (fun i => Plan.eval M θ0 θ (pf i)) (pg j)) =
      interpret M (comp g f) θ := by
  have first : (fun i => Plan.eval M θ0 θ (pf i)) = interpret M f θ := by
    funext i
    exact check_sound M X.varies θ0 θ (f.terms i) (pf i) fixed (hf i)
  rw [first]
  funext j
  calc
    Plan.eval M (interpret M f θ0) (interpret M f θ) (pg j)
        = Expr.eval M (interpret M f θ) (g.terms j) :=
      check_sound M Y.varies (interpret M f θ0) (interpret M f θ)
        (g.terms j) (pg j) (fixed_slice_preserved M f θ0 θ fixed) (hg j)
    _ = Expr.eval M θ (Expr.subst f.terms (g.terms j)) :=
      (Expr.eval_subst M f.terms (g.terms j) θ).symm

end Arrow

#print axioms Arrow.comp_assoc
#print axioms Arrow.interpret_comp
#print axioms Arrow.fixed_slice_preserved
#print axioms Arrow.checked_composition

end Category
end TypedTMDPlan
