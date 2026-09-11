import numpy as np
import pytest
from digitalcreativity.movement import distance_threshold_events, interpolate_distance_crossings


def test_crossing_is_assigned_to_interval_end_not_start():
    events, _ = distance_threshold_events([[20, 35, 20, 30]], [0, 6, 12, 18, 24], ['001'])
    assert events.time_seconds.tolist() == [12, 24]
    assert events.time_lower_seconds.tolist() == [6, 18]
    assert events.timestamp_row_1based.tolist() == [3, 5]
    assert events.category.tolist() == ['001', '001']
    assert events.distance_since_event_or_reset.tolist() == [55, 50]


def test_missing_and_battery_gap_do_not_complete_an_event():
    d = np.array([[40., np.nan, 20., 999., 35., 20.]])
    original = d.copy()
    events, meta = distance_threshold_events(d, [0, 6, 12, 18, 1000, 1006, 1012], ['a'])
    assert events.time_seconds.tolist() == [1012]
    assert events.distance_since_event_or_reset.tolist() == [55]
    assert meta['valid_steps_per_identity'] == [4]
    np.testing.assert_array_equal(d, original)


def test_no_extra_notes_for_overshoot_and_no_notes_for_stationary_animal():
    events, _ = distance_threshold_events([[120, 10], [0, 0]], [0, 6, 12], ['moving', 'still'])
    assert events.time_seconds.tolist() == [6]
    assert events.category.tolist() == ['moving']


@pytest.mark.parametrize('t', [[0, 0], [6, 0], [0, np.nan]])
def test_invalid_clock_fails(t):
    with pytest.raises(ValueError):
        distance_threshold_events([[1]], t, ['a'])


def test_identity_collision_and_misaligned_columns_fail():
    with pytest.raises(ValueError):
        distance_threshold_events([[1], [1]], [0, 6], ['a', 'a'])
    with pytest.raises(ValueError):
        distance_threshold_events([[1, 2]], [0, 6], ['a'])


def test_interpolation_distributes_coincident_detections_without_adding_events():
    d = [[40., 20.], [45., 20.]]
    t = [0., 6., 12.]
    observed, _ = distance_threshold_events(d, t, ['a', 'b'])
    inferred = interpolate_distance_crossings(observed, d, t, ['a', 'b'])
    assert observed.time_seconds.tolist() == [12., 12.]
    assert inferred.category.tolist() == ['b', 'a']
    assert inferred.time_seconds.tolist() == [7.5, 9.]
    assert inferred.observed_endpoint_seconds.tolist() == [12., 12.]
    assert sorted(inferred.event_id) == sorted(observed.event_id)


def test_interpolation_rejects_a_recording_gap():
    import pandas as pd
    event = pd.DataFrame(dict(category=['a'], timestamp_row_1based=[2],
        time_seconds=[60.], distance_since_event_or_reset=[55.]))
    with pytest.raises(ValueError):
        interpolate_distance_crossings(event, [[55.]], [0., 60.], ['a'])
