"""Independent observation quadrature of a supplied point-response kernel.

For the pinned arTeMiDe interface h = d sigma/(dqT^2 dQ^2 dy), in pb/GeV^4.
This integrates the observation, sharing the native physics kernel. It is not
an independent QCD calculation. No native bin-integration call is used here.
"""
from __future__ import annotations

from functools import lru_cache
import numpy as np


@lru_cache(maxsize=128)
def nodes(lo: float, hi: float, order: int) -> tuple[np.ndarray, np.ndarray]:
    """Cache parameter-independent geometry only; never cache kernel values."""
    if not (np.isfinite(lo) and np.isfinite(hi) and hi > lo and type(order) is int and order >= 2):
        raise ValueError("Invalid quadrature interval/order")
    x, w = np.polynomial.legendre.leggauss(order)
    x, w = (lo+hi)/2 + (hi-lo)/2*x, (hi-lo)/2*w
    x.setflags(write=False)
    w.setflags(write=False)
    return x, w


def mass_nodes(bounds, order, breaks):
    edges = [bounds[0], *[v for v in breaks if bounds[0] < v < bounds[1]], bounds[1]]
    pieces = [nodes(a, b, order) for a, b in zip(edges[:-1], edges[1:])]
    return np.concatenate([v[0] for v in pieces]), np.concatenate([v[1] for v in pieces])


def integrate_point_density(point, row, orders, mass_breaks):
    """Integrate all qT,Q,y coordinates using their explicit Jacobians."""
    qt, wq = nodes(*row.qT, orders[0])
    mass, wm = mass_nodes(row.Q, orders[1], mass_breaks)
    rap, wy = nodes(*row.y, orders[2])
    q, m, y = np.meshgrid(qt, mass, rap, indexing="ij")
    values = np.asarray(point(row, q.ravel(), m.ravel(), y.ravel())).reshape(q.shape)
    if not np.all(np.isfinite(values)):
        raise ValueError("Nonfinite native point response")
    weights = (2*qt*wq)[:, None, None] * (2*mass*wm)[None, :, None] * wy[None, None, :]
    return float(np.sum(values*weights))


def integrate_mass_rapidity(point, row, qt, orders, mass_breaks):
    """Return d sigma/dqT^2 at a fixed qT, integrated over Q^2 and y."""
    mass, wm = mass_nodes(row.Q, orders[0], mass_breaks)
    rap, wy = nodes(*row.y, orders[1])
    m, y = np.meshgrid(mass, rap, indexing="ij")
    values = np.asarray(point(row, np.full(m.size, qt), m.ravel(), y.ravel())).reshape(m.shape)
    if not np.all(np.isfinite(values)):
        raise ValueError("Nonfinite native point response")
    return float(np.sum(values * (2*mass*wm)[:, None] * wy[None, :]))
