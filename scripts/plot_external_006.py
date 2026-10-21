#!/usr/bin/env python3
"""Make static scientific figures from retained arrays; never rerun a fit."""
import argparse
import csv
import json
import os
from pathlib import Path
import numpy as np
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1]/".cache/matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read(p):
    return json.loads(p.read_text())


def save(fig, path):
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--campaign", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--timing", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    d, fits = read(args.campaign/"data.json"), read(args.campaign/"fits.json")
    obs = read(args.plan/"observation_contract.json")["contract"]["bins"]
    plan = read(args.plan/"experiment_plan.json")
    centers = np.array([sum(r["qT"])/2 for r in obs])
    truth, sigma = np.array(d["truth"]), np.array(d["sigma"])
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "savefig.facecolor": "white"})
    blue, red = "#286a9f", "#b54131"
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 3.9), layout="constrained")
    ax = axes[0]
    ax.errorbar(centers, truth, yerr=sigma, color=blue, fmt="o-", lw=1.4, capsize=3,
                label="Native bin means ± synthetic σ")
    ax.plot(centers, d["midpoint_at_truth"], "s--", color=red, ms=4, label="Midpoint at generating c₀")
    ax.set(xlabel="qₜ bin center [GeV]", ylabel="Average dσ/dqₜ [pb/GeV]", title="(a) Same native physics kernel")
    ax.legend(fontsize=8, frameon=False)
    labels = ["correct_noiseless", "unchecked_noiseless", "correct_fixed_noise", "unchecked_fixed_noise"]
    names = ["Noiseless · integrated", "Noiseless · midpoint", "Fixed noise · integrated", "Fixed noise · midpoint"]
    ax = axes[1]
    for i, label in enumerate(labels):
        selected = fits[label]["selected"]
        ax.errorbar(selected["c0"], i, xerr=selected["local_c0_sigma"], fmt="o", capsize=3,
                    color=blue if label.startswith("correct") else red)
    ax.axvline(plan["fit"]["truth"], color="0.3", ls="--", lw=1, label="Generating c₀")
    ax.set_yticks(range(4), names, fontsize=8)
    ax.set(xlabel="c₀ [GeV²] · bars: local sensitivity σ", title="(b) Frozen five-start fits", xlim=(0., .102))
    ax.invert_yaxis(); ax.legend(fontsize=8, frameon=False, loc="upper right")
    ax = axes[2]
    ax.axvspan(10, 16, color="0.94", label="Held out")
    ax.axhline(0, color="0.4", lw=.8)
    for label, name, color, mark in (("correct_noiseless", "Integrated fit", blue, "o"),
                                      ("unchecked_noiseless", "Midpoint fit", red, "s")):
        residual = (np.array(fits[label]["full_prediction"])-truth)/sigma
        ax.plot(centers, residual, marker=mark, color=color, lw=1.3, label=name)
    ax.set(xlabel="qₜ bin center [GeV]", ylabel="(fit prediction − generating mean) / σ",
           title="(c) Noiseless mean residuals", xlim=(0, 16))
    ax.legend(fontsize=8, frameon=False)
    save(fig, args.output/"external_observation_effect")
    with (args.output/"fit_table.csv").open("w", newline="") as stream:
        fields = ["case", "c0_GeV2", "local_sigma_GeV2", "chi2", "heldout_mean_whitened_norm", "bound_hit"]
        writer = csv.DictWriter(stream, fieldnames=fields);writer.writeheader()
        for label in labels:
            f, s = fits[label], fits[label]["selected"]
            writer.writerow(dict(zip(fields, [label,s["c0"],s["local_c0_sigma"],s["chi2"],f["heldout_mean_whitened_norm"],s["at_bound"]])))
    if args.timing:
        timing = read(args.timing/"timings.json")
        keys = ["construction_validation", "warm_scalar", "warm_batch", "parameter_changing_objective"]
        names = ["Construction", "One bin (GL)", "Seven bins (GL)", "3 parameter proposals"]
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), layout="constrained")
        y = np.arange(len(keys))
        for route, offset, color in (("native", -.12, "0.35"), ("typed", .12, blue)):
            times = [timing["workloads"][k]["median_"+route+"_seconds"] for k in keys]
            axes[0].plot(times, y+offset, "o", color=color, label="Plain" if route == "native" else "Typed")
        axes[0].set(xscale="log", xlabel="Median seconds per workload", title="(a) Absolute cost")
        axes[0].set_yticks(y, names);axes[0].invert_yaxis();axes[0].legend(frameon=False, fontsize=9)
        for i,k in enumerate(keys):
            ratios = [b["typed_ns"]/b["native_ns"] for b in timing["workloads"][k]["samples"]]
            axes[1].scatter(ratios, np.full(len(ratios), i)+np.linspace(-.08, .08, len(ratios)), s=9, color=blue, alpha=.6)
            axes[1].plot(np.median(ratios), i, "|", color="black", ms=17, mew=2)
        axes[1].axvline(1, color="0.5", ls="--", lw=1)
        axes[1].set(xlabel="Typed / plain paired time ratio", title="(b) 30 alternating paired blocks")
        axes[1].set_yticks(y, names);axes[1].invert_yaxis()
        save(fig, args.output/"external_checking_overhead")
    (args.output/"figure_receipt.json").write_text(json.dumps({"matplotlib": matplotlib.__version__,
        "scope": "static plots of saved scientific and timing arrays; no fits or noise generated", "synthetic_data": True},indent=2)+"\n")


if __name__ == "__main__":
    main()
