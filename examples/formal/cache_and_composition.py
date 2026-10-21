#!/usr/bin/env python3
"""Runtime tutorial: safe caching, model restriction and transported references."""
import copy
import json
import math

from typed_tmd.contracts import ContractError
from typed_tmd.finite_plan import (Algebra, PreparedPlan, atom, binary, compose,
    digest, prepare_wire, propose, respects_variation, unary, var)
from typed_tmd.finite_plan_bridge import kernel_cache_fixture


def run():
    ops = (lambda x, y: x+y, lambda x, y: x*y)
    good, _ = kernel_cache_fixture()
    bad, _ = kernel_cache_fixture(freeze_dynamic=True)
    calls = []

    def bind(doc):
        return prepare_wire(doc, expected_context=doc['context'],
            unary_ops=(lambda x: calls.append(x) or math.exp(x),), binary_ops=ops,
            unary_symbols=('exp',), binary_symbols=('add', 'mul'))

    try:
        bind(bad)
    except ContractError as exc:
        refusal = str(exc)
    else:
        raise AssertionError('unsafe fitted-parameter cache was accepted')
    assert not calls
    safe = bind(good)
    context = digest(good['context'])
    f = lambda g: safe.evaluate((.25, g), context_identity=context)[0]
    step = 1e-6
    derivative = (f(.04+step)-f(.04-step))/(2*step)
    assert math.isclose(derivative, -1.3**2*math.log(4)*f(.04), abs_tol=1e-8)
    assert f(.05) != f(.04)
    fixed = copy.deepcopy(bad)
    fixed['parameters']['varying'] = [True, False]
    restricted = bind(fixed)
    restricted.evaluate((.35, .04), context_identity=context)
    try:
        restricted.evaluate((.35, .041), context_identity=context)
    except ContractError as exc:
        fixed_refusal = str(exc)
    else:
        raise AssertionError('fixed coordinate changed without rejection')

    # f(x,y)=(x+2,y²); g(u,v)=u*v. Only the first coordinate varies.
    algebra = Algebra((2.,), (lambda x: x*x,), ops)
    source_f = (binary(0, var(0), atom(0)), unary(0, var(1)))
    source_g = (binary(1, var(0), var(1)),)
    mask = (True, False)
    theta0, theta = (.2, .3), (.4, .3)
    assert respects_variation(source_f, mask, mask)
    first = PreparedPlan(source_f, tuple(propose(e, mask) for e in source_f),
                         mask, theta0, algebra, context_identity='first')
    eta0 = tuple(algebra.eval(e, theta0) for e in source_f)
    second = PreparedPlan(source_g, tuple(propose(e, mask) for e in source_g),
                          mask, eta0, algebra, context_identity='second')
    eta = first.evaluate(theta, context_identity='first')
    value = second.evaluate(eta, context_identity='second')
    assert value == tuple(algebra.eval(e, theta) for e in compose(source_f, source_g))
    wrong = PreparedPlan(source_g, tuple(propose(e, mask) for e in source_g),
                         mask, theta0, algebra, context_identity='wrong')
    try:
        wrong.evaluate(eta, context_identity='wrong')
    except ContractError as exc:
        wrong_refusal = str(exc)
    else:
        raise AssertionError('untransported reference was accepted')
    return {'status': 'runtime_tested', 'primitive_calls_before_refusal': 0,
        'unsafe_cache_refusal': refusal, 'reference_value': f(.04),
        'correct_off_reference_value': f(.05), 'frozen_off_reference_value': f(.04),
        'correct_derivative': derivative, 'frozen_derivative': 0.,
        'fixed_model_change_refusal': fixed_refusal, 'transported_reference': eta0,
        'composition_value': value, 'wrong_reference_refusal': wrong_refusal,
        'scope': 'Python runtime example; run check_formal.py for kernel evidence'}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, sort_keys=True))
