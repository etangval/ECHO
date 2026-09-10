import numpy as np
from digitalcreativity.processes import interval_metrics,count_models,time_rescaling


def test_local_variation_does_not_bridge_unobserved_gap():
    result=interval_metrics([0,1,2,10,30],[[0,3],[10,50]])
    assert result['complete_intervals']==3
    assert result['CV2']==0
    assert result['LV']==0
    assert result['observation_seconds']==43


def test_held_out_covariate_model_detects_known_daily_rate_variation():
    rng=np.random.default_rng(71)
    edges=np.linspace(0,14*86400,2049)
    mid=(edges[:-1]+edges[1:])/2
    expected=10*np.exp(1.3*np.sin(2*np.pi*mid/86400))
    y=rng.poisson(expected)
    result,_=count_models(edges,y,np.diff(edges),seed=17)
    assert result['models']['covariate_poisson']['test_log_likelihood'] > result['models']['homogeneous_poisson']['test_log_likelihood']+100
    assert result['hpp_dispersion_parametric_bootstrap_p']<=.01


def test_continuous_time_diagnostic_does_not_treat_ties_as_poisson_spacings():
    t=np.repeat(np.arange(100.),2)
    result=time_rescaling(t,np.arange(101.),np.full(100,2.),precision=1.)
    assert result['status']=='continuous_rescaling_not_used_for_tied_or_coarse_clock'
