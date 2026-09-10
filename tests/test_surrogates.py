import numpy as np
from digitalcreativity.surrogates import local_shuffle, pair_coactivation, interval_shuffle


def test_local_shuffle_preserves_block_marginals_and_breaks_synchrony():
    matrix = np.zeros((128,4), dtype=int)
    matrix[::8] = 3
    shuffled = local_shuffle(matrix, np.random.default_rng(23))
    for a in [0,64]:
        np.testing.assert_array_equal(np.sort(matrix[a:a+64],axis=0),np.sort(shuffled[a:a+64],axis=0))
    assert pair_coactivation(shuffled) < pair_coactivation(matrix)


def test_interval_surrogate_detects_order_without_cross_gap_pairs():
    times = np.r_[0,np.cumsum(np.arange(1.,61.))]
    result = interval_shuffle(times,[[0,times[-1]+1]],np.random.default_rng(31),99)
    assert result['serial_spearman'] > .99
    assert result['shuffled_95_interval'][1] < .5
