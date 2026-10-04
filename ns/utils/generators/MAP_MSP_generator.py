"""Stationary Markov chains and batch Markovian interarrival samples."""

import numpy as np
from numpy.random import rand

PRECISION_VALUE = 1e-5


def _square_matrix(matrix):
    """Use floating-point arithmetic and reject undefined transition tables."""
    matrix = np.asarray(matrix, dtype=float)
    if (
        matrix.ndim != 2
        or matrix.shape[0] == 0
        or matrix.shape[0] != matrix.shape[1]
        or not np.all(np.isfinite(matrix))
    ):
        raise ValueError("transition matrix must be finite, nonempty and square.")
    return matrix


def solve_CTMC(Q):
    """Return row vector pi satisfying pi Q = 0 and sum(pi) = 1.

    Q has nonnegative off-diagonal rates and zero row sums. A nonunique
    stationary distribution needs a caller-chosen initial phase instead.
    """
    Q = _square_matrix(Q)
    off_diagonal = Q - np.diag(np.diag(Q))
    if (
        np.any(off_diagonal < 0)
        or np.any(np.diag(Q) > 0)
        or np.any(abs(Q.sum(axis=1)) > PRECISION_VALUE)
    ):
        raise ValueError("invalid CTMC rates or nonzero row sum.")
    # Replace one redundant balance equation with the normalization equation.
    A = Q.copy()
    A[:, 0] = 1
    b = np.zeros((Q.shape[0], 1))
    b[0] = 1
    try:
        return np.linalg.solve(A.T, b).T
    except np.linalg.LinAlgError as error:
        raise ValueError("stationary distribution is not unique.") from error


def solve_DTMC(P):
    """Return the stationary row vector of a stochastic transition matrix."""
    P = _square_matrix(P)
    if np.any(P < 0) or np.any(abs(P.sum(axis=1) - 1) > PRECISION_VALUE):
        raise ValueError("invalid DTMC probabilities or row sum.")
    return solve_CTMC(P - np.eye(P.shape[0]))


def sum_matrix_list(mat_list):
    """Sum transition-rate matrices without mutating the caller's matrices."""
    return np.sum(mat_list, axis=0)


def check_BMAP_representation(D_list, prec=PRECISION_VALUE):
    """Check rate signs, row balance, and eventual arrival from every phase.

    D0 describes transitions without arrivals; Dk describes a batch of k.
    D0 must be transient, so a closed silent class cannot trap the sampler.
    These conditions follow BuTools' CheckMAPRepresentation/check.py.
    """
    if len(D_list) < 2:
        return False
    try:
        matrices = [_square_matrix(matrix) for matrix in D_list]
    except ValueError:
        return False
    D0 = matrices[0]
    if any(matrix.shape != D0.shape for matrix in matrices[1:]):
        return False
    if np.any(np.diag(D0) >= 0):
        return False
    if np.any(D0 - np.diag(np.diag(D0)) < 0):
        return False
    if any(np.any(matrix < 0) for matrix in matrices[1:]):
        return False
    if np.any(abs(sum_matrix_list(matrices).sum(axis=1)) > prec):
        return False
    # Every phase must reach an arrival along silent transitions. This finite
    # graph check detects closed silent classes without a near-zero eigenvalue
    # being mistaken for a strictly negative one due to floating-point rounding.
    silent = D0 - np.diag(np.diag(D0))
    can_arrive = np.any(np.hstack(matrices[1:]) > 0, axis=1)
    for _ in range(D0.shape[0]):
        can_arrive |= np.any((silent > 0) & can_arrive[None, :], axis=1)
    return bool(np.all(can_arrive))


def BMAP_generator(D_list, initial=None):
    """Yield MAP intervals in seconds, or BMAP [interval, batch_size] pairs.

    Rates in D0...DN are per second. With no initial phase, start in the
    stationary distribution of their sum, as the existing time-origin API did.
    This first interval is therefore a stationary-time residual; subsequent
    intervals start at arrivals. It is not an arrival-stationary initial sample.
    Each step waits an exponential phase holding time and selects a silent
    transition or a batch. See BuTools' SamplesFromMMAP in map/misc.py.
    """
    if not check_BMAP_representation(D_list):
        raise ValueError("input is not a valid BMAP representation.")
    matrices = [np.asarray(matrix, dtype=float) for matrix in D_list]
    M = matrices[0].shape[0]
    if initial is None:
        cumulative = np.cumsum(solve_CTMC(sum_matrix_list(matrices)))
        cumulative[-1] = 1
        state = int(np.searchsorted(cumulative, rand(), side="right"))
    else:
        if not isinstance(initial, (int, np.integer)) or not 0 <= initial < M:
            raise ValueError("initial state must index a BMAP phase.")
        state = initial

    sojourn = -1 / np.diag(matrices[0])
    silent = matrices[0] - np.diag(np.diag(matrices[0]))
    # Columns are [silent next phases, batch-1 phases, batch-2 phases, ...].
    probabilities = np.hstack([silent, *matrices[1:]]) * sojourn[:, None]
    # Normalize rounding allowed by the row-balance tolerance; end exactly at 1.
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    cumulative = np.cumsum(probabilities, axis=1)
    cumulative[:, -1] = 1
    while True:
        interval = 0
        while state < M:
            # rand() can return zero. Clip that endpoint before taking log so
            # an otherwise finite exponential holding time cannot become inf.
            draw = max(rand(), np.nextafter(0.0, 1.0))
            interval -= np.log(draw) * sojourn[state]
            state = int(np.searchsorted(cumulative[state], rand(), side="right"))
        batch = state // M
        state %= M
        yield [interval, batch] if len(matrices) > 2 else interval
