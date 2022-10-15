import numpy as np
from numpy.random import rand

PRECISION_VALUE = 1e-5

def solve_CTMC(Q):
    """
    Solve stationary distribution vector x for a CTMC with generator matrix Q
    balance equation: x * Q = 0

    Parameters
    ----------
    Q: generator matrix of a CTMC, row sum == 0

    Return
    -------
    x.T: 1-D row vector, stationary distribution vector
    """

    if np.any(abs(np.sum(Q, 1) - 0.0) > PRECISION_VALUE):
        raise ValueError('Invalid CTMC Q matrix: Row sum not equal to 0')
    A = Q.copy()
    A[:, 0] = np.ones(A.shape[0])
    b = np.zeros((A.shape[0], 1))
    b[0] = 1.0
    x = np.linalg.solve(A.T, b)

    return x.T


def solve_DTMC(P):
    P = np.asarray(P)
    if np.any(np.sum(P, 1) - 1.0 > PRECISION_VALUE):
        raise ValueError('Invalid DTMC P matrix: Row sum not equal to 1')
    return solve_CTMC(P - np.eye(P.shape[0]))


def sum_matrix_list(mat_list):
    sum_mat = np.zeros(mat_list[0].shape)
    for mat in mat_list:
        sum_mat += mat
    return sum_mat


def check_BMAP_representation(D_list, prec=PRECISION_VALUE):
    if len(D_list) == 2:
        print('Input: MAP representation')
    elif len(D_list) > 2:
        print('Input: BMAP representation')
    else:
        print('neither MAP or BMAP representation')
        return False

    D0 = D_list[0]
    for Dk in D_list[1:]:
        if D0.shape != Dk.shape:
            print('D0 and Dk have different shapes')
            return False
    for Dk in D_list[1:]:
        if np.min(Dk) < -prec:
            print('Dk has negative entry')
            return False

    if np.any(np.abs(np.sum(sum_matrix_list(D_list), 1)) > prec):
        print('row sum is not zero')
        return False

    return True


def BMAP_generator(D_list, initial=None):
    """
    Generates random samples from a batch Markovian
    arrival process.

    Parameters
    ----------
    D_list: list of matrices of shape(M,M), length(N)
        The D0...DN matrices of the BMAP
    num_samples: integer
        The number of samples to generate.

    Yield:
    -------
    x : one sample.
        if BMAP: list consisting of two values: the inter-arrival time and the type of the
        arrival.   
        if MAP: float, inter-arrival time     
    """

    if not check_BMAP_representation(D_list):
        raise ValueError(
            "Samples From BMAP: Input is not a valid BMAP representation!")

    M = D_list[0].shape[0]

    if initial is None:
        # draw initial state according to the stationary distribution
        stat_distr_vec = solve_CTMC(sum_matrix_list(D_list))
        cumm_initial = np.cumsum(stat_distr_vec)
        r = rand()
        state = 0
        while cumm_initial[state] <= r:
            state += 1
    else:
        state = initial

    # auxilary variables
    sojourn = -1.0 / np.diag(D_list[0])
    nextpr = np.diag(sojourn) @ D_list[0]
    nextpr = nextpr - np.diag(np.diag(nextpr))
    for Dk in D_list[1:]:
        nextpr = np.hstack((nextpr, np.diag(sojourn) @ Dk))
    nextpr = np.cumsum(nextpr, 1)

    while True:
        iat = 0

        # play state transitions
        while state < M:
            iat -= np.log(rand()) * sojourn[state]
            r = rand()
            nstate = 0
            while nextpr[state, nstate] <= r:
                nstate += 1
            state = nstate
        state = nstate % M
        if len(D_list) > 2:
            yield [iat, nstate // M]
        else:
            yield iat
