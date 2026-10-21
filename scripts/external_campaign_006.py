"""Bounded synthetic campaign and isolated, explicitly unchecked fault harness.

Imported by run_external_006.py; not a production bypass of observation checks.
All reported fit data are synthetic. Neither fit path changes the native model.
"""
from dataclasses import asdict, replace
import math
import time
import numpy as np
from scipy.optimize import least_squares

from typed_tmd.observations import (ObservationContract, ObservationMismatch,
    ObservedFitProblem, convert_averages)


def fit_case(plan, contract, data, sigma, specification, *, unchecked=False):
    """The unchecked branch exists only to quantify the injected misuse."""
    lo, hi = specification["domain"]
    width = hi-lo
    problem = None if unchecked else ObservedFitProblem(contract, plan, tuple(data), tuple(sigma))
    results = []
    for start in specification["start_fractions"]:
        history = []

        def residual(u):
            theta = (float(lo+width*u[0]),)
            if unchecked:
                # Deliberately skips ObservedFitProblem; plan still correctly
                # declares point_density and cannot bind to the bin contract.
                value = (np.asarray(plan.evaluate(theta))-data)/sigma
            else:
                value = np.asarray(problem.residuals(theta))
            history.append({"c0": theta[0], "chi2": float(value@value)})
            return value

        def jacobian(u):
            # Frozen absolute step in the dimensionless chart, shortened only
            # to remain inside the admitted native domain.
            step = specification["jacobian_chart_step"]
            left, right = max(0., u[0]-step), min(1., u[0]+step)
            return ((residual([right])-residual([left]))/(right-left))[:, None]

        start_time = time.perf_counter()
        result = least_squares(residual, [start], jac=jacobian, bounds=([0.], [1.]),
            **specification["solver_options"])
        theta = float(lo+width*result.x[0])
        at_bound = bool(min(result.x[0], 1-result.x[0]) < specification["bound_fraction_tolerance"])
        information = float(result.jac[:, 0]@result.jac[:, 0])/(width*width)
        results.append({"start_fraction": start, "c0": theta, "chi2": float(result.fun@result.fun),
            "success": bool(result.success), "status": int(result.status), "message": str(result.message),
            "at_bound": at_bound, "active_mask": result.active_mask.tolist(),
            "nfev": int(result.nfev), "njev": int(result.njev), "actual_calls": len(history),
            "optimality": float(result.optimality), "elapsed_seconds": time.perf_counter()-start_time,
            "local_c0_sigma": None if at_bound or information <= 0 else 1/math.sqrt(information),
            "uncertainty_scope": "local linear sensitivity for fixed synthetic covariance; no boundary Wald interval",
            "history": history})
    eligible = [r for r in results if r["success"]]
    best = min(eligible or results, key=lambda r: r["chi2"])
    return {"starts": results, "selected": {k: v for k, v in best.items() if k != "history"},
            "all_starts_successful": all(r["success"] for r in results),
            "successful_start_chi2_range": [min(r["chi2"] for r in eligible), max(r["chi2"] for r in eligible)] if eligible else None,
            "global_optimum_proved": False, "unchecked_fault_harness": unchecked}


def campaign(native, session, contract, lock, specification, out, write, compare):
    session.orders = tuple(specification["quadrature"]["nominal_orders"])
    theta = (lock["fixed_parameter_vector"][1],)
    correct = session.plan(contract, operation="independent_bin_average")
    generating = session.plan(contract)
    wrong = session.plan(contract, operation="qT_point_density")
    before = dict(session.calls)
    optimizer_calls = 0
    try:
        ObservedFitProblem(contract, wrong, (0.,)*len(contract.bins), (1.,)*len(contract.bins))
        optimizer_calls += 1
        raise AssertionError("Invalid point observation accepted")
    except ObservationMismatch as error:
        rejection = {**error.diagnostic, "backend_call_delta": {k: v-before[k] for k, v in session.calls.items()},
                     "optimizer_calls": optimizer_calls, "passed": session.calls == before and optimizer_calls == 0}
    write(out/"rejection.json", rejection)
    write(out/"response_plans.json", {"correct": correct.record(), "fault": wrong.record()})

    truth = np.asarray(generating.evaluate(theta))
    train = specification["fit"]["training_indices"]
    heldout = specification["fit"]["heldout_indices"]
    sigma = np.maximum(.02*abs(truth), 1e-4*np.max(abs(truth[train])))
    noise = np.random.Generator(np.random.PCG64(specification["noise_seed"])).standard_normal(len(truth))
    noisy = truth+sigma*noise
    arrays = {"truth": truth.tolist(), "sigma": sigma.tolist(), "covariance": np.diag(sigma*sigma).tolist(),
              "noise": noise.tolist(), "noise_hex": [float(v).hex() for v in noise], "noisy_data": noisy.tolist(),
              "numpy": np.__version__, "generator": "PCG64", "seed": specification["noise_seed"],
              "training_indices": train, "heldout_indices": heldout, "synthetic": True}
    write(out/"data.json", arrays)
    midpoint = np.asarray(wrong.evaluate(theta))
    arrays["midpoint_at_truth"] = midpoint.tolist()
    arrays["fixed_prediction_shift"] = (midpoint-truth).tolist()
    arrays["fixed_whitened_norm"] = float(np.linalg.norm((midpoint-truth)/sigma))
    arrays["fixed_training_chi2"] = float(np.sum(((midpoint-truth)/sigma)[train]**2))
    write(out/"data.json", arrays)

    training = replace(contract, bins=tuple(contract.bins[i] for i in train))
    accepted = session.plan(training, operation="independent_bin_average")
    fault = session.plan(training, operation="qT_point_density")
    fits = {}
    for data_name, data in (("noiseless", truth), ("fixed_noise", noisy)):
        for route, plan in (("correct", accepted), ("unchecked", fault)):
            label = route+"_"+data_name
            print("Starting fit", label, flush=True)
            fits[label] = fit_case(plan, training, data[train], sigma[train], specification["fit"], unchecked=route=="unchecked")
            selected = fits[label]["selected"]
            value = (selected["c0"],)
            full = np.asarray((correct if route == "correct" else wrong).evaluate(value))
            fits[label].update({"full_prediction": full.tolist(),
                "parameter_error_from_truth": value[0]-theta[0],
                "heldout_mean_residual": (full[heldout]-truth[heldout]).tolist(),
                "heldout_mean_whitened_norm": float(np.linalg.norm((full[heldout]-truth[heldout])/sigma[heldout]))})
            write(out/"fits.json", fits)
            print(label, "c0", value[0], "chi2", selected["chi2"], flush=True)

    # Empirical derivative refinement supports the one-parameter rank check
    # and local sensitivity coordinate, without asserting global identifiability.
    derivatives = []
    for h in specification["sensitivity_steps"]:
        plus = np.asarray(correct.evaluate((theta[0]+h,)))
        minus = np.asarray(correct.evaluate((theta[0]-h,)))
        derivatives.append((plus-minus)/(2*h))
    whitened = derivatives[-1][train]/sigma[train]
    sensitivity = float(np.linalg.norm(whitened))
    rank = {"columns": 1, "singular_values": [sensitivity], "rank": int(sensitivity > 1e-8),
        "steps": specification["sensitivity_steps"], "derivatives": [v.tolist() for v in derivatives],
        "relative_step_change": float(np.linalg.norm((derivatives[0]-derivatives[1])[train]/sigma[train])/sensitivity),
        "truth_local_sigma_c0": 1/sensitivity, "scope": "local training sensitivity at generating parameter"}
    write(out/"rank_check.json", rank)
    consequences = {}
    for data_name in ("noiseless", "fixed_noise"):
        a, b = fits["unchecked_"+data_name], fits["correct_"+data_name]
        shift = a["selected"]["c0"]-b["selected"]["c0"]
        consequences[data_name] = {"c0_uncorrected_minus_corrected": shift,
            "shift_in_truth_local_sigma": shift*sensitivity,
            "chi2_uncorrected_minus_corrected": a["selected"]["chi2"]-b["selected"]["chi2"],
            "response_uncorrected_minus_corrected": (np.asarray(a["full_prediction"])-b["full_prediction"]).tolist(),
            "heldout_difference": (np.asarray(a["full_prediction"])[heldout]-np.asarray(b["full_prediction"])[heldout]).tolist()}
    write(out/"consequences.json", consequences)
    return truth, sigma, fits


def validate_selected(session, contract, lock, specification, truth, sigma, fits, out, write, compare, *, point_label=None):
    """Same numerical budgets at truth and every selected fitted parameter."""
    points = {"truth": lock["fixed_parameter_vector"][1]}
    points.update({k: v["selected"]["c0"] for k, v in fits.items()})
    if point_label is not None:
        if point_label == "geometry":
            points = {}
        elif point_label in points:
            points = {point_label: points[point_label]}
        else:
            raise ValueError("Unknown validation point")
    checks, arrays = {}, {}
    native_plan = session.plan(contract)
    nominal = tuple(specification["quadrature"]["nominal_orders"])
    refined_orders = [tuple(v) for v in specification["quadrature"]["refinement_orders"]]
    for label, c0 in points.items():
        print("Independent integration validation", label, flush=True)
        vectors = {"native": native_plan.evaluate((c0,))}
        for order in (nominal, *refined_orders):
            session.orders = order
            vectors["GL_"+"_".join(map(str, order))] = session.plan(contract, operation="independent_bin_average").evaluate((c0,))
        basekey = "GL_"+"_".join(map(str, nominal))
        comparisons = {"native_independent": compare(vectors[basekey], vectors["native"], sigma)}
        for order in refined_orders:
            key = "GL_"+"_".join(map(str, order))
            check = compare(vectors[key], vectors[basekey], sigma)
            check["refinement_passed"] = check["whitened_norm"] <= .05/3
            comparisons[key] = check
        # Wrong route needs Q/y integration validation too: distinguish the
        # qT midpoint error from a poorly resolved remaining observation map.
        midpoint_vectors = []
        for order in (nominal, *refined_orders[1:]):
            session.orders = order
            midpoint_vectors.append(session.plan(contract, operation="qT_point_density").evaluate((c0,)))
        for i, value in enumerate(midpoint_vectors[1:]):
            check = compare(value, midpoint_vectors[0], sigma)
            check["refinement_passed"] = check["whitened_norm"] <= .05/3
            comparisons["midpoint_Qy_refinement_"+str(i)] = check
        arrays[label] = {"c0": c0, "vectors": vectors, "midpoint_refinements": midpoint_vectors}
        checks[label] = comparisons
        write(out/"selected_validation_arrays.json", arrays)
        write(out/"selected_validation_checks.json", checks)
    if point_label is not None and point_label != "geometry":
        return checks
    session.orders = nominal
    theta = (lock["fixed_parameter_vector"][1],)
    full = session.plan(contract, operation="independent_bin_average")
    average = np.asarray(full.evaluate(theta))
    split_rows = []
    for row in contract.bins:
        middle = sum(row.qT)/2
        split_rows.extend((replace(row, name=row.name+"_left", qT=(row.qT[0], middle)),
                           replace(row, name=row.name+"_right", qT=(middle, row.qT[1]))))
    split = replace(contract, bins=tuple(split_rows))
    halves = np.asarray(session.plan(split, operation="independent_bin_average").evaluate(theta))
    joined = (halves[::2]+halves[1::2])/2
    squared = replace(contract, measure="dqT2")
    converted = np.asarray(convert_averages(tuple(average), contract, squared))
    recomputed = np.asarray(session.plan(squared, operation="independent_bin_average").evaluate(theta))
    factors = np.asarray(convert_averages((1.,)*len(contract.bins), contract, squared))
    # Nonzero synthetic residual and a correlated positive-definite covariance
    # demonstrate that the complete inference problem must be transported.
    residual = sigma*np.linspace(-1., 1., len(sigma))
    covariance = np.diag(sigma*sigma)+.1*np.outer(sigma, sigma)
    objective = float(residual@np.linalg.solve(covariance, residual))
    transformed = covariance*factors[:, None]*factors[None, :]
    mapped = factors*residual
    transformed_objective = float(mapped@np.linalg.solve(transformed, mapped))
    widths, point_limits = [2., 1., .5, .25, .125], []
    row = contract.bins[0]
    for width in widths:
        narrow = replace(contract, bins=(replace(row, name="point_limit", qT=(1-width/2, 1+width/2)),))
        point_limits.append(session.plan(narrow, operation="independent_bin_average").evaluate(theta)[0])
    point = session.plan(narrow, operation="qT_point_density").evaluate(theta)[0]
    errors = abs(np.asarray(point_limits)-point)
    reset_values = [full.evaluate((value,)) for value in (theta[0], .02, theta[0])]
    geometry_checks = {
        "additivity": compare(joined, average, sigma),
        "same_yield_average_conversion": {"passed": bool(np.allclose(converted, recomputed, rtol=1e-12, atol=1e-12*max(abs(converted))))},
        "full_covariance_transport": {"passed": math.isclose(objective, transformed_objective, rel_tol=1e-12, abs_tol=1e-12)},
        "point_limit": {"passed": bool(np.all(np.diff(errors) < 0)), "scope": "empirical approach at qT=1; not an exact finite-bin equivalence"},
        "parameter_change_reset": {"passed": reset_values[0] == reset_values[2] and reset_values[0] != reset_values[1]}}
    write(out/"geometry_arrays.json", {"average": average.tolist(), "split_averages": halves.tolist(),
        "joined": joined.tolist(), "converted": converted.tolist(), "recomputed": recomputed.tolist(),
        "residual": residual.tolist(), "covariance": covariance.tolist(), "map_diagonal": factors.tolist(),
        "objective": objective, "transformed_objective": transformed_objective, "point_limit_widths": widths,
        "point_limit_values": point_limits, "point_value": point, "point_limit_errors": errors.tolist(), "parameter_reset": reset_values})
    checks["geometry"] = geometry_checks
    write(out/"selected_validation_checks.json", checks)
    return checks


def measure_overhead(native, session, contract, lock, spec, out, write):
    """30 paired blocks of the same point-kernel calls and observation integral.

    Plain route explicitly constructs the numerical integral without contracts.
    It is not the upstream adaptive bin API, which has a different cost.
    """
    from typed_tmd.observation_quadrature import integrate_point_density
    from time import perf_counter_ns
    from statistics import median
    truth = lock["fixed_parameter_vector"][1]
    scalar = replace(contract, bins=contract.bins[:1])
    rows = [asdict(b) for b in contract.bins]
    raw_factors = [b.rapidity_multiplicity/(b.qT[1]-b.qT[0]) for b in contract.bins]
    session.orders = tuple(spec["quadrature"]["nominal_orders"])
    plain_calls = {"parameter_sets": 0, "native_bin": 0, "native_point_batches": 0, "native_points": 0}

    def plain_points(row, qt, mass, rapidity):
        n = len(qt)
        plain_calls["native_point_batches"] += 1
        plain_calls["native_points"] += n
        return native.DY.xSecListBINLESS(np.tile(row.process, (n, 1)), np.full(n, row.s), qt, mass, rapidity,
            np.full(n, row.include_cuts), np.tile(row.cuts, (n, 1)))

    def direct(c0, count):
        native.setNPparameters([lock["fixed_parameter_vector"][0], c0, *lock["fixed_parameter_vector"][2:]])
        plain_calls["parameter_sets"] += 1
        return tuple(integrate_point_density(plain_points, row, session.orders, session.mass_breaks)*factor
                     for row, factor in zip(contract.bins[:count], raw_factors[:count]))

    scalar_plan, batch_plan = [session.plan(c, operation="independent_bin_average") for c in (scalar, contract)]
    data = np.asarray(batch_plan.evaluate((truth,)))
    sigma = .02*abs(data)
    fit = ObservedFitProblem(contract, batch_plan, tuple(data), tuple(sigma))
    parameters = [truth, .02, .04]

    def direct_objective():
        result = []
        for c0 in parameters:
            r = (np.asarray(direct(c0, len(rows)))-data)/sigma
            result.append(float(r@r))
        return tuple(result)

    def typed_objective():
        result = []
        for c0 in parameters:
            r = np.asarray(fit.residuals((c0,)))
            result.append(float(r@r))
        return tuple(result)

    # Construction comparison is descriptive: raw request records versus
    # constructing/validating an immutable contract and bound response plan.
    workloads = {
        "construction_validation": (lambda: tuple(asdict(b) for b in contract.bins),
            lambda: session.plan(ObservationContract(tuple(contract.bins), session.identity), operation="independent_bin_average"), 0, 0),
        "warm_scalar": (lambda: direct(truth, 1), lambda: scalar_plan.evaluate((truth,)), 1, 1),
        "warm_batch": (lambda: direct(truth, len(rows)), lambda: batch_plan.evaluate((truth,)), len(rows), 1),
        "parameter_changing_objective": (direct_objective, typed_objective, 3*len(rows), 3),
    }
    result = {"clock": "perf_counter_ns", "clock_info": vars(time.get_clock_info("perf_counter")),
        "blocks": spec["timing_blocks"], "order": "alternating native-first and typed-first",
        "startup": "separate environment receipt; includes import/configuration/initial grid binding once",
        "cache": "same native interpolation grid; no response cache; full NP rebind on every evaluation",
        "threads": 1, "batch_scope": "same batched native point requests and independent observation quadrature; excludes upstream adaptive bin API",
        "memory_scope": "not measured; process high-water marks are not per-call allocations",
        "workloads": {}}
    for name, (plain, typed, bins, bindings) in workloads.items():
        print("Timing", name, flush=True)
        # Warm and compare outside timing; construction has different outputs.
        a, b = plain(), typed()
        if bins and not np.array_equal(a, b):
            raise AssertionError("Timing workload outputs differ")
        durations = []
        for call in (plain, typed):
            start = perf_counter_ns()
            call()
            durations.append(perf_counter_ns()-start)
        repetitions = max(1, min(10000, math.ceil(20_000_000/min(durations))))
        before_plain, before_typed = dict(plain_calls), dict(session.calls)
        samples = []
        for block in range(spec["timing_blocks"]):
            sample = {"block": block, "order": ["native", "typed"] if block % 2 == 0 else ["typed", "native"]}
            for route in sample["order"]:
                call = plain if route == "native" else typed
                start = perf_counter_ns()
                for _ in range(repetitions):
                    call()
                sample[route+"_ns"] = perf_counter_ns()-start
            samples.append(sample)
        native_times = np.array([r["native_ns"] for r in samples])/repetitions
        typed_times = np.array([r["typed_ns"] for r in samples])/repetitions
        ratio = typed_times/native_times
        plain_delta = {k: v-before_plain[k] for k,v in plain_calls.items()}
        typed_delta = {k: v-before_typed[k] for k,v in session.calls.items()}
        if plain_delta != typed_delta:
            raise AssertionError("Paired timing routes made different native calls")
        result["workloads"][name] = {"pilot_ns": durations, "repetitions_per_block": repetitions,
            "measured_timed_call_counts": {"native": plain_delta, "typed": typed_delta},
            "native_point_batches_per_repetition_each_route": bins, "NP_bindings_per_repetition_each_route": bindings,
            "native_points_per_repetition_each_route": bins*session.orders[0]*session.orders[1]*session.orders[2]*(len(session.mass_breaks)+1),
            "warmups_each_route": 2, "samples": samples, "outputs_binary_equal": True if bins else None,
            "median_native_seconds": float(np.median(native_times)*1e-9),
            "median_typed_seconds": float(np.median(typed_times)*1e-9),
            "median_extra_seconds": float(np.median(typed_times-native_times)*1e-9),
            "median_paired_ratio": float(np.median(ratio)), "paired_ratio_IQR": np.quantile(ratio, [.25, .75]).tolist()}
        write(out/"timings.json", result)
    return result
