"""A small exact polynomial algebra for the synthetic evolution fixture.

The supported grammar is finite rational polynomials in u, v and b. This is a
symbolic checker for that grammar, not a general computer algebra/proof system.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from .contracts import ContractError, EvolutionConsistencyError, finite

VARIABLES = ("u", "v", "b")


@dataclass(frozen=True)
class Monomial:
    coefficient: Fraction
    powers: tuple[int, int, int]

    def __post_init__(self) -> None:
        coefficient = self.coefficient
        if not isinstance(coefficient, Fraction):
            coefficient = Fraction(str(coefficient))
        powers = tuple(self.powers)
        if len(powers) != 3 or any(type(power) is not int or power < 0 for power in powers):
            raise ContractError("Monomials need three nonnegative integer powers (u,v,b)")
        object.__setattr__(self, "coefficient", coefficient)
        object.__setattr__(self, "powers", powers)


@dataclass(frozen=True)
class Polynomial:
    terms: tuple[Monomial, ...] = ()

    def __post_init__(self) -> None:
        collected: dict[tuple[int, int, int], Fraction] = {}
        for term in self.terms:
            if not isinstance(term, Monomial):
                raise ContractError("Polynomial terms must be Monomial objects")
            collected[term.powers] = collected.get(term.powers, Fraction(0)) + term.coefficient
        canonical = tuple(Monomial(value, powers) for powers, value in sorted(collected.items()) if value)
        object.__setattr__(self, "terms", canonical)

    @classmethod
    def from_terms(cls, terms: Iterable[tuple[float | str | Fraction, tuple[int, int, int]]]) -> Polynomial:
        return cls(tuple(Monomial(Fraction(str(value)), powers) for value, powers in terms))

    def derivative(self, variable: str) -> Polynomial:
        if variable not in VARIABLES:
            raise ContractError(f"Unknown polynomial variable {variable!r}")
        index = VARIABLES.index(variable)
        result = []
        for term in self.terms:
            power = term.powers[index]
            if power:
                powers = list(term.powers)
                powers[index] -= 1
                result.append(Monomial(term.coefficient * power, tuple(powers)))
        return Polynomial(tuple(result))

    def __add__(self, other: Polynomial) -> Polynomial:
        if not isinstance(other, Polynomial):
            return NotImplemented
        return Polynomial(self.terms + other.terms)

    def __sub__(self, other: Polynomial) -> Polynomial:
        if not isinstance(other, Polynomial):
            return NotImplemented
        return self + Polynomial(tuple(Monomial(-term.coefficient, term.powers) for term in other.terms))

    @property
    def is_zero(self) -> bool:
        return not self.terms

    def evaluate(self, *, u: float, v: float, b: float) -> float:
        values = tuple(finite(value, name) for name, value in zip(VARIABLES, (u, v, b)))
        return sum(float(term.coefficient) * values[0] ** term.powers[0]
                   * values[1] ** term.powers[1] * values[2] ** term.powers[2]
                   for term in self.terms)

    def to_dict(self) -> dict:
        return {"variables": list(VARIABLES), "terms": [
            {"coefficient": str(term.coefficient), "powers": list(term.powers)}
            for term in self.terms
        ]}


@dataclass(frozen=True)
class EvolutionGenerators:
    gamma: Polynomial
    kernel: Polynomial

    @classmethod
    def from_potential(cls, potential: Polynomial) -> EvolutionGenerators:
        return cls(potential.derivative("u"), potential.derivative("v"))

    @property
    def curvature(self) -> Polynomial:
        return self.kernel.derivative("u") - self.gamma.derivative("v")

    def require_exact_flatness(self) -> None:
        if not self.curvature.is_zero:
            raise EvolutionConsistencyError("Exact synthetic generators have a nonzero polynomial curvature")

