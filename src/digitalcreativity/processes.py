"""Shared exploratory point-process diagnostics with explicit observation support.

Count-history fits below are *binned self-exciting Poisson models*, a discrete-time
Hawkes approximation. They are not continuous-time causal interaction estimates.
"""
import math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import optimize,signal,special,stats
from .pipeline import save_json
from .preprocessing import merge_intervals


def finite(value):
    if isinstance(value,dict):return {str(k):finite(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [finite(v) for v in value]
    if isinstance(value,np.generic):value=value.item()
    if isinstance(value,float) and not np.isfinite(value):return None
    return value


def interval_sample(times,coverage):
    times=np.sort(np.asarray(times,float));gaps=[];right_censored=[];within=0
    for lo,hi in merge_intervals(coverage):
        a,b=np.searchsorted(times,[lo,hi]);t=times[a:b];within+=len(t)
        if len(t):
            gaps.extend(np.diff(t));right_censored.append(hi-t[-1])
    return np.asarray(gaps),np.asarray(right_censored),within


def interval_metrics(times,coverage):
    gaps,censored,within=interval_sample(times,coverage)
    exposure=sum(b-a for a,b in merge_intervals(coverage))
    r=dict(events=len(times),events_within_observation=within,observation_seconds=exposure,event_rate_hz=within/exposure if exposure else None,complete_intervals=len(gaps),zero_intervals=int((gaps==0).sum()),right_censored_intervals=len(censored))
    if len(gaps)<2:return {**r,'CV':None,'CV2':None,'LV':None,'burstiness':None}
    mean=float(gaps.mean());sd=float(gaps.std(ddof=1));den=gaps[1:]+gaps[:-1]
    # Local statistics must not connect consecutive intervals across gaps.
    cv2,lv=[],[]
    t=np.sort(np.asarray(times,float))
    for lo,hi in merge_intervals(coverage):
        a,b=np.searchsorted(t,[lo,hi]);d=np.diff(t[a:b]);den=d[:-1]+d[1:]
        valid=den>0
        cv2.extend(2*abs(np.diff(d))[valid]/den[valid])
        lv.extend(3*np.diff(d)[valid]**2/den[valid]**2)
    r.update(mean_interval_seconds=mean,median_interval_seconds=float(np.median(gaps)),CV=sd/mean if mean else None,CV2=float(np.mean(cv2)) if cv2 else None,LV=float(np.mean(lv)) if lv else None,burstiness=(sd-mean)/(sd+mean) if sd+mean else None,IEI_q10=float(np.quantile(gaps,.1)),IEI_q90=float(np.quantile(gaps,.9)))
    return finite(r)


def renewal_comparison(times,coverage,precision=0.):
    d,c,n=interval_sample(times,coverage)
    if len(d)<30:return dict(status='insufficient_complete_intervals',complete_intervals=len(d))
    if np.any(d<=0) or np.median(d)<=10*precision:return dict(status='continuous_renewal_fit_not_used_for_coarse_or_tied_timestamps')
    # Conditional likelihood after the first event of each continuous interval;
    # right-censored final waiting times contribute survival probabilities.
    mean=max(float(d.mean()),1e-15)
    x=d/mean;right=c/mean
    output={}
    for name,distribution in [('gamma',stats.gamma),('weibull',stats.weibull_min)]:
        def nll(theta):
            shape,scale=np.exp(theta)
            value=distribution.logpdf(x,shape,scale=scale).sum()+distribution.logsf(right,shape,scale=scale).sum()
            return -float(value) if np.isfinite(value) else 1e100
        initial_shape=max(.15,min(10.,1/(np.std(x)**2+1e-9))) if name=='gamma' else 1.
        start=np.log([initial_shape,1/initial_shape if name=='gamma' else 1.])
        fit=optimize.minimize(nll,start,method='L-BFGS-B',bounds=[(-4,5),(-8,8)])
        shape,scale=np.exp(fit.x);ll=-fit.fun-len(d)*np.log(mean)
        output[name]=dict(shape=float(shape),scale_seconds=float(scale*mean),conditional_log_likelihood=float(ll),AIC=float(4-2*ll),converged=bool(fit.success))
    exponential_rate=len(d)/(d.sum()+c.sum())
    ll=len(d)*np.log(exponential_rate)-exponential_rate*(d.sum()+c.sum())
    output['exponential']=dict(rate_hz=float(exponential_rate),conditional_log_likelihood=float(ll),AIC=float(2-2*ll))
    return dict(status='descriptive_conditional_renewal_fit',complete_intervals=len(d),right_censored_intervals=len(c),models=output,note='Whole-record renewal fits do not remove rate nonstationarity. AIC is descriptive, not proof of a renewal mechanism.')


def multiscale_fano(times,coverage,precision=0.):
    intervals=merge_intervals(coverage);maximum=max(b-a for a,b in intervals)
    low=max(precision,maximum/8192,1e-9);high=maximum/8
    if high<=low:return []
    rows=[];t=np.sort(np.asarray(times,float))
    for width in np.geomspace(low,high,13):
        counts=[]
        for lo,hi in intervals:
            n=int((hi-lo)//width)
            if n<2:continue
            edge=lo+np.arange(n+1)*width
            counts.extend(np.histogram(t[(t>=lo)&(t<edge[-1])],edge)[0])
        y=np.asarray(counts,float)
        if len(y)>1 and y.mean()>0:
            rows.append(dict(bin_seconds=float(width),complete_bins=len(y),mean_count=float(y.mean()),fano=float(y.var(ddof=1)/y.mean())))
    return rows


def count_series(times,coverage,bins=4096):
    intervals=merge_intervals(coverage);lo,hi=intervals[0][0],intervals[-1][1]
    edges=np.linspace(lo,hi,bins+1);width=(hi-lo)/bins
    counts=np.histogram(times,edges)[0].astype(float)
    exposure=np.zeros(bins)
    for a,b in intervals:exposure+=np.maximum(0,np.minimum(edges[1:],b)-np.maximum(edges[:-1],a))
    return edges,counts,np.minimum(exposure,width)


def acf_with_mask(values,mask,max_lag=128):
    y=np.asarray(values,float);m=np.asarray(mask,bool)
    if m.sum()<3 or np.var(y[m])==0:return []
    z=np.where(m,y-y[m].mean(),0.)
    numerator=signal.correlate(z,z,mode='full',method='fft')[len(y)-1:len(y)+max_lag]
    pairs=signal.correlate(m.astype(float),m.astype(float),mode='full',method='fft')[len(y)-1:len(y)+max_lag]
    denominator=np.var(y[m])*pairs
    return np.divide(numerator,denominator,out=np.full_like(numerator,np.nan),where=pairs>1).tolist()


def longest_run(mask):
    bounds=np.flatnonzero(np.diff(np.r_[False,mask,False]))
    if len(bounds)<2:return slice(0,0)
    spans=list(zip(bounds[::2],bounds[1::2]));a,b=max(spans,key=lambda p:p[1]-p[0]);return slice(a,b)


def dfa(values):
    y=np.asarray(values,float)
    if len(y)<256:return dict(status='insufficient_contiguous_bins')
    integrated=np.cumsum(y-y.mean());scales=np.unique(np.geomspace(8,len(y)//4,12).astype(int));rows=[]
    for s in scales:
        segments=integrated[:len(y)//s*s].reshape(-1,s)
        detrended=signal.detrend(segments,axis=1,type='linear')
        f=float(np.sqrt(np.mean(detrended**2)))
        if f>0:rows.append([int(s),f])
    if len(rows)<4:return dict(status='no_valid_scaling_range')
    r=np.array(rows);fit=stats.linregress(np.log(r[:,0]),np.log(r[:,1]))
    return dict(status='exploratory_scaling_only',slope=float(fit.slope),loglog_r_squared=float(fit.rvalue**2),scales_and_fluctuations=rows,note='Finite scaling range and nonstationarity preclude a claim of long-range dependence from this slope alone.')


def _poisson_fit(y,exposure,X,train):
    centers=X[train].mean(axis=0);scales=X[train].std(axis=0);scales[scales<1e-9]=1
    Z=(X-centers)/scales;Z=np.c_[np.ones(len(y)),Z]
    start=np.zeros(Z.shape[1]);start[0]=np.log(max(y[train].sum()/exposure[train].sum(),1e-12))
    def loss(beta):
        eta=np.clip(Z@beta,-30,30);mu=exposure*np.exp(eta)
        residual=mu[train]-y[train]
        penalty=1e-6*np.sum(beta[1:]**2)
        return float(np.sum(mu[train]-y[train]*eta[train])+penalty),Z[train].T@residual+np.r_[0,2e-6*beta[1:]]
    result=optimize.minimize(loss,start,jac=True,method='L-BFGS-B',options={'maxiter':300,'ftol':1e-10})
    mu=exposure*np.exp(np.clip(Z@result.x,-30,30))
    return mu,dict(coefficients=result.x.tolist(),feature_center=centers.tolist(),feature_scale=scales.tolist(),converged=bool(result.success))


def count_models(edges,y,exposure,covariates=None,seed=20260910):
    width=edges[1]-edges[0];mid=(edges[:-1]+edges[1:])/2
    complete=exposure>=width*(1-1e-6)
    train=complete&(np.arange(len(y))<int(.7*len(y)));test=complete&~train
    if train.sum()<64 or test.sum()<32 or y[train].sum()<50 or y[test].sum()<20:return dict(status='insufficient_complete_train_test_bins'),{}
    X=[(mid-mid[0])/(mid[-1]-mid[0])];names=['linear_record_time']
    if mid[-1]-mid[0]>2*86400:
        for period,label in [(86400,'daily'),(7*86400,'weekly')]:
            for order in [1,2]:
                X.extend([np.sin(2*np.pi*order*mid/period),np.cos(2*np.pi*order*mid/period)])
                names.extend([f'{label}_sin{order}',f'{label}_cos{order}'])
    if covariates is not None:
        for name in [c for c in covariates if c!='event_time']:
            values=np.interp(mid,covariates.event_time,covariates[name])
            X.append(np.log1p(np.maximum(0,values)) if 'speed' in name else values);names.append(name)
    X=np.column_stack(X)
    rate=y[train].sum()/exposure[train].sum();mu_hpp=rate*exposure
    mu,nhpp=_poisson_fit(y,exposure,X,train)
    predictions={'homogeneous_poisson':mu_hpp,'covariate_poisson':mu}
    candidates=[]
    for tau_bins in [1,4,16,64]:
        decay=np.exp(-1/tau_bins)
        history=signal.lfilter([0.,1-decay],[1.,-decay],y)
        # Disallow excitation carried across observation gaps: recursive reset.
        state=0.
        for i in range(len(history)):
            if not complete[i]:state=0.;history[i]=0.
            else:history[i]=state;state=decay*state+(1-decay)*y[i]
        def loss(v):
            estimate=np.maximum(v[0]*mu+v[1]*history,1e-12)
            residual=1-y[train]/estimate[train]
            return float((estimate[train]-y[train]*np.log(estimate[train])).sum()),np.array([residual@mu[train],residual@history[train]])
        fit=optimize.minimize(loss,[1.,.05],jac=True,method='L-BFGS-B',bounds=[(.00001,10),(0,.98)])
        predicted=np.maximum(fit.x[0]*mu+fit.x[1]*history,1e-12)
        candidates.append(dict(tau_bins=tau_bins,tau_seconds=float(tau_bins*width),baseline_multiplier=float(fit.x[0]),offspring_parameter=float(fit.x[1]),training_loss=float(fit.fun),converged=bool(fit.success),prediction=predicted))
    chosen=min(candidates,key=lambda x:x['training_loss']);predictions['binned_self_exciting']=chosen['prediction']
    rng=np.random.default_rng(seed);scores={}
    for name,pred in predictions.items():
        yt=y[test];mt=np.maximum(pred[test],1e-12)
        ll=float(np.sum(stats.poisson.logpmf(yt,mt)))
        pit=stats.poisson.cdf(yt-1,mt)+rng.random(len(yt))*stats.poisson.pmf(yt,mt)
        residual=(yt-mt)/np.sqrt(mt)
        scores[name]=dict(test_log_likelihood=ll,test_log_likelihood_per_event=ll/yt.sum(),randomized_pit_KS_D=float(stats.kstest(pit,'uniform').statistic),pearson_dispersion=float(np.mean(residual**2)),residual_lag1_correlation=float(np.corrcoef(residual[:-1],residual[1:])[0,1]) if np.std(residual)>0 else None,nominal_test_p_values_omitted=True)
    # Parametric calibration of the simple HPP count-distribution diagnostic.
    observed=scores['homogeneous_poisson']['pearson_dispersion'];simulated=[]
    for _ in range(199):
        yy=rng.poisson(mu_hpp);rr=yy[train].sum()/exposure[train].sum();expected=np.maximum(rr*exposure[test],1e-12)
        simulated.append(float(np.mean((yy[test]-expected)**2/expected)))
    p=(1+sum(abs(v-1)>=abs(observed-1) for v in simulated))/(len(simulated)+1)
    report=dict(status='held_out_count_diagnostics',bin_seconds=float(width),training_fraction=.7,training_complete_bins=int(train.sum()),test_complete_bins=int(test.sum()),test_events=int(y[test].sum()),covariates=names,covariate_poisson=nhpp,models=scores,self_exciting={k:v for k,v in chosen.items() if k!='prediction'},kernel_candidates=[{k:v for k,v in v.items() if k!='prediction'} for v in candidates],hpp_dispersion_parametric_bootstrap_p=float(p),bootstrap_replicates=199,model_note='Binned conditional Poisson with an exponential nonnegative count-history kernel; a discrete-time Hawkes approximation. Kernels selected using training data; held-out scores are one-step predictions using observed past counts. Parameter is not causal branching.',nonstationarity_note='Daily/weekly harmonics and trend, plus available behavior covariates, are finite baseline controls; unmeasured common inputs may remain.',pit_note='Randomized count PIT accommodates ties; diagnostic discrepancies, not proof of Poisson equivalence.')
    return finite(report),predictions


def time_rescaling(times,edges,mu,precision=0.):
    t=np.sort(np.asarray(times,float));t=t[(t>=edges[int(.7*(len(edges)-1))])&(t<edges[-1])]
    if len(t)<30:return dict(status='insufficient_events')
    if np.any(np.diff(t)<=0) or np.median(np.diff(t))<=10*precision:
        return dict(status='continuous_rescaling_not_used_for_tied_or_coarse_clock',alternative='randomized count PIT')
    bins=np.searchsorted(edges,t,side='right')-1;width=np.diff(edges)
    cumulative=np.r_[0,np.cumsum(mu)]
    integrated=cumulative[bins]+mu[bins]*(t-edges[bins])/width[bins]
    z=np.diff(integrated);u=-np.expm1(-z)
    return finite(dict(status='held_out_piecewise_constant_intensity_rescaling',intervals=len(z),exponential_KS_D=float(stats.kstest(z,'expon').statistic),uniform_KS_D=float(stats.kstest(u,'uniform').statistic),rescaled_mean=float(z.mean()),lag1_correlation=float(np.corrcoef(z[:-1],z[1:])[0,1]),note='No p value: finite intensity resolution and fitted parameters require additional calibration for confirmatory inference.'))


def avalanche_metrics(y,mask,width):
    active=(np.asarray(y)>0)&mask
    changes=np.flatnonzero(np.diff(np.r_[False,active,False]));sizes=[];durations=[]
    for a,b in zip(changes[::2],changes[1::2]):
        # Boundary-censored avalanches do not have a verified preceding/following silence.
        if a==0 or b==len(y) or not mask[a-1] or not mask[b]:continue
        sizes.append(float(np.sum(y[a:b])));durations.append(float((b-a)*width))
    valid=mask[:-1]&mask[1:]&(np.asarray(y[:-1])>0)
    ratio=float(np.sum(y[1:][valid])/np.sum(y[:-1][valid])) if valid.any() else None
    return dict(avalanche_count=len(sizes),sizes=sizes,durations_seconds=durations,empirical_count_ratio=ratio,nonempty_bin_fraction=float(active.sum()/mask.sum()) if mask.any() else None,note='Consecutive nonempty bins bounded by observed empty bins; sensitivity to bin width required. Empirical ratio is not a causal branching ratio; power-law or criticality is not inferred.')


def analyze_source(prepared,output,population=True,seed=20260910):
    prepared=Path(prepared);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    events=pd.read_parquet(prepared/'events.parquet');coverage=pd.read_parquet(prepared/'observation_intervals.parquet')
    import json
    prep=json.loads((prepared/'preparation.json').read_text(encoding='utf-8'));precision=prep['time_precision_seconds']
    by_cov={str(k):g[['start_seconds','stop_seconds']].to_numpy(float) for k,g in coverage.groupby('entity_id')}
    rows=[];renewals={}
    for entity,g in events.groupby('entity_id',sort=True):
        c=by_cov.get(str(entity))
        if c is None:continue
        row=interval_metrics(g.event_time.to_numpy(),c);row['entity_id']=str(entity);rows.append(row)
    table=pd.DataFrame(rows);table.to_csv(output/'entity_metrics.csv',index=False)
    eligible=table.loc[table.complete_intervals>=30,'entity_id'].to_numpy()
    chosen=np.sort(np.random.default_rng(seed).choice(eligible,min(24,len(eligible)),replace=False))
    for entity in chosen:
        renewals[str(entity)]=renewal_comparison(events.loc[events.entity_id.astype(str)==str(entity),'event_time'].to_numpy(),by_cov[str(entity)],precision)
    save_json(output/'renewal_models.json',finite(renewals))
    summary=dict(source=prep['source'],events=len(events),entities=int(events.entity_id.nunique()),units_with_CV=int(table.CV.notna().sum()),entity_metric_medians={key:float(table[key].median()) if table[key].notna().any() else None for key in ['CV','CV2','LV','burstiness','event_rate_hz']},renewal_entities=len(renewals),renewal_selection='Uniform fixed-seed sample of up to 24 entities with >=30 complete intervals',population_analysis=population)
    if population:
        series_times=events.event_time.to_numpy();support=merge_intervals(coverage[['start_seconds','stop_seconds']].to_numpy())
        series_label='catalog_population'
    else:
        # Choose one observed individual deterministically for plotting only;
        # no alignment or synthetic simultaneous animal population is created.
        ordered=table.sort_values(['complete_intervals','entity_id'],kind='stable')
        candidate=ordered.iloc[(len(ordered)-1)//2].entity_id
        series_times=events.loc[events.entity_id.astype(str)==candidate,'event_time'].to_numpy();support=by_cov[candidate];series_label='individual_'+candidate
        summary['population_analysis_note']='Not applicable: asynchronous GPS deployments and observation gaps. Per-animal distributions are reported; reference trace is a median-interval-count animal, not a simultaneous population.'
    summary['trace_label']=series_label
    fano=multiscale_fano(series_times,support,precision);save_json(output/'multiscale_fano.json',fano)
    edges,y,exposure=count_series(series_times,support);width=edges[1]-edges[0];mask=exposure>=width*(1-1e-6)
    pospath=prepared/'position_covariates.parquet';covariates=pd.read_parquet(pospath) if pospath.exists() else None
    models,predictions=count_models(edges,y,exposure,covariates,seed)
    summary['models']=models
    segment=longest_run(mask);values=y[segment]
    summary['DFA']=dfa(values);summary['trace_complete_bins']=int(mask.sum())
    summary['time_rescaling']={name:time_rescaling(series_times,edges,pred,precision) for name,pred in predictions.items() if name!='binned_self_exciting'} if np.all(mask) else {'status':'not_evaluated_across_observation_gaps'}
    frequencies,power=signal.welch(values,fs=1/width,nperseg=min(512,len(values))) if len(values)>=64 else (np.array([]),np.array([]))
    np.savez_compressed(output/'trace_diagnostics.npz',edges=edges,counts=y,exposure=exposure,acf=np.asarray(acf_with_mask(y,mask)),frequency_hz=frequencies,power=power,**{name+'_mean':value for name,value in predictions.items()})
    if population:
        avalanches={}
        for factor in [1,4,16]:
            ee,yy,xx=count_series(series_times,support,bins=4096*factor);ww=ee[1]-ee[0];avalanches[str(ww)]=avalanche_metrics(yy,xx>=ww*(1-1e-6),ww)
        save_json(output/'population_avalanches.json',finite(avalanches))
    save_json(output/'summary.json',finite(summary))
    return finite(summary)
