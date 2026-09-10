import numpy as np
import pandas as pd
from digitalcreativity.preprocessing import epoch_seconds,displacement_events,merge_intervals


def test_datetime_storage_precision_does_not_rescale_seconds():
    expected=np.array([0.,180.])
    for unit in ['s','ms','us','ns']:
        x=np.array(['1970-01-01T00:00:00','1970-01-01T00:03:00'],dtype=f'datetime64[{unit}]')
        np.testing.assert_array_equal(epoch_seconds(x),expected)


def test_gps_gap_does_not_create_invented_movement():
    gps=pd.DataFrame(dict(entity_id=['cat']*4,event_time=[0.,180.,3600.,3780.],latitude=[0.,0.,1.,1.],longitude=[0.,.0001,1.,1.0001],source_row=[1,2,3,4]))
    events,coverage,_=displacement_events(gps,50.,900.)
    assert events.empty
    assert len(coverage)==2


def test_crossing_retains_observed_time_and_censoring_bounds():
    gps=pd.DataFrame(dict(entity_id=['cat']*3,event_time=[0.,180.,360.],latitude=[0.,0.,0.],longitude=[0.,.0001,.001],source_row=[1,2,3]))
    events,_,_=displacement_events(gps,50.,900.)
    assert len(events)==1
    assert events.iloc[0].event_time==360
    assert events.iloc[0].time_lower==180
    assert events.iloc[0].time_upper==360
    assert merge_intervals([[0,1],[.5,2],[3,4]])==[[0.,2.],[3.,4.]]
