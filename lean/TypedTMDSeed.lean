import Init

/-!
# A typed transformation seed

This file proves a conditional algebraic statement. A presentation provides
states, admitted evolution steps, and an observable response. A transformation
carries explicit proofs that it respects evolution and preserves that response.
The composition of two such transformations has the same properties.

The `Step` type records admitted transitions; it does not assert that every pair
of contexts has a physical evolution map. No analytic, numerical, or QCD
factorization theorem is asserted here. This seed has no mathlib dependency.
-/

namespace TypedTMDSeed

structure Presentation
    (Context : Type) (Step : Context → Context → Type)
    (Output : Context → Type) where
  State : Context → Type
  evolve : {source target : Context} → Step source target → State source → State target
  observe : {context : Context} → State context → Output context

variable {Context : Type} {Step : Context → Context → Type}
    {Output : Context → Type}

structure Transformation
    (A B : Presentation Context Step Output) where
  map : {context : Context} → A.State context → B.State context
  evolution_compatible : ∀ {source target : Context}
    (step : Step source target) (x : A.State source),
    map (A.evolve step x) = B.evolve step (map x)
  observation_preserved : ∀ {context : Context} (x : A.State context),
    B.observe (map x) = A.observe x

namespace Transformation

variable {A B C D : Presentation Context Step Output}

def identity (A : Presentation Context Step Output) : Transformation A A where
  map x := x
  evolution_compatible _ _ := rfl
  observation_preserved _ := rfl

/-- Certified transformations compose without changing their endpoint types. -/
def comp (g : Transformation B C) (f : Transformation A B) : Transformation A C where
  map x := g.map (f.map x)
  evolution_compatible step x := by
    calc
      g.map (f.map (A.evolve step x))
          = g.map (B.evolve step (f.map x)) :=
            congrArg (fun y => g.map y) (f.evolution_compatible step x)
      _ = C.evolve step (g.map (f.map x)) :=
            g.evolution_compatible step (f.map x)
  observation_preserved x := by
    calc
      C.observe (g.map (f.map x)) = B.observe (f.map x) :=
        g.observation_preserved (f.map x)
      _ = A.observe x := f.observation_preserved x

/-- The maps underlying composition are associative. -/
theorem comp_map_assoc (h : Transformation C D) (g : Transformation B C)
    (f : Transformation A B) {context : Context} (x : A.State context) :
    (comp h (comp g f)).map x = (comp (comp h g) f).map x := rfl

/-- A generator certificate also transports a two-step calculation. -/
theorem preserves_two_steps (f : Transformation A B)
    {a b c : Context} (firstStep : Step a b) (secondStep : Step b c)
    (x : A.State a) :
    f.map (A.evolve secondStep (A.evolve firstStep x)) =
      B.evolve secondStep (B.evolve firstStep (f.map x)) := by
  calc
    f.map (A.evolve secondStep (A.evolve firstStep x))
        = B.evolve secondStep (f.map (A.evolve firstStep x)) :=
          f.evolution_compatible secondStep (A.evolve firstStep x)
    _ = B.evolve secondStep (B.evolve firstStep (f.map x)) :=
          congrArg (fun y => B.evolve secondStep y) (f.evolution_compatible firstStep x)

end Transformation
end TypedTMDSeed
