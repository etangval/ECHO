"""Aggregate blinded paired ratings without exporting participant-level records.

Positive scores favour the optimized mapping. Seven-point ratings are ordinal;
means describe location on the coded scale, not equal perceptual distances.
"""
import numpy as np
from scipy import stats
from numbers import Integral

DIMENSIONS = ('beauty', 'pleasantness', 'preference')


def orient_rating(rating, first_condition):
    if isinstance(rating, bool) or not isinstance(rating, Integral) or rating not in range(1, 8):
        raise ValueError('Expected an integer rating from 1 (A) to 7 (B)')
    if first_condition not in ('optimized', 'random'):
        raise ValueError('The identity of A must be recorded')
    return (4 - rating) * (1 if first_condition == 'optimized' else -1)


def holm(pvalues):
    p = np.asarray(pvalues, float)
    order = np.argsort(p)
    result = np.empty(len(p))
    result[order] = np.minimum(1, np.maximum.accumulate(p[order] * np.arange(len(p), 0, -1)))
    return result.tolist()


def describe_scores(values, rng=None, replicates=20000):
    a = np.asarray(values, float)
    if not len(a):
        return {'n': 0}
    rng = np.random.default_rng(20260910) if rng is None else rng
    positive, neutral, negative = int((a > 0).sum()), int((a == 0).sum()), int((a < 0).sum())
    decisive = positive + negative
    test = stats.binomtest(positive, decisive, .5) if decisive else None
    ci = test.proportion_ci(method='exact') if test else (float('nan'), float('nan'))
    boot = rng.choice(a, size=(replicates, len(a)), replace=True).mean(axis=1)
    return dict(n=len(a), optimized=positive, equal=neutral, random=negative,
                distribution=[int((a == k).sum()) for k in range(-3, 4)],
                mean=float(a.mean()), median=float(np.median(a)),
                mean_bootstrap_95ci=np.quantile(boot, [.025, .975]).tolist(),
                optimized_share_all=positive/len(a),
                optimized_share_decisive=positive/decisive if decisive else None,
                decisive_share_exact_95ci=list(ci) if test else None,
                sign_p=float(test.pvalue) if test else 1.)


def summarize(rows, seed=20260910, replicates=20000):
    if not rows:
        raise ValueError('No responses')
    domains = sorted({r['domain'] for r in rows})
    for r in rows:
        if r.get('scaleOrientation', '1=A,4=equal,7=B') != '1=A,4=equal,7=B':
            raise ValueError('Unexpected scale orientation')
        for k in DIMENSIONS:
            orient_rating(r['comparisons'][k], r['firstCondition'])
    rng = np.random.default_rng(seed)
    output = {'n': len(rows), 'domains': domains, 'seed': seed, 'bootstrap_replicates': replicates,
              'interpretation': 'Conditional on these fixed audio excerpts and responding volunteers; listeners are the resampling units. No stimulus-population inference or universal aesthetic claim.',
              'outcomes': {}}
    for key in DIMENSIONS:
        scores = {d: np.array([orient_rating(r['comparisons'][key], r['firstCondition']) for r in rows if r['domain'] == d]) for d in domains}
        overall = describe_scores(np.concatenate(list(scores.values())), rng, replicates)
        per_domain = {d: describe_scores(a, rng, replicates) for d, a in scores.items()}
        # Equal domain weights prevent sample-size imbalance defining the target.
        boot = sum(rng.choice(a, size=(replicates, len(a))).mean(axis=1) for a in scores.values())/len(domains)
        balanced = dict(mean=float(np.mean([a.mean() for a in scores.values()])),
                        mean_bootstrap_95ci=np.quantile(boot, [.025, .975]).tolist())
        output['outcomes'][key] = dict(overall=overall, by_domain=per_domain, equal_domain_weighted=balanced)
    corrected = holm([output['outcomes'][k]['overall']['sign_p'] for k in DIMENSIONS])
    for k, p in zip(DIMENSIONS, corrected):
        output['outcomes'][k]['overall']['sign_p_holm_3'] = p
    pairs = [(k,d) for k in DIMENSIONS for d in domains]
    corrected = holm([output['outcomes'][k]['by_domain'][d]['sign_p'] for k,d in pairs])
    for (k,d),p in zip(pairs,corrected):
        output['outcomes'][k]['by_domain'][d]['sign_p_holm_9'] = p
    return output


def adjusted_means(rows):
    """Exploratory HC3 linear adjustment; not an ordinal latent-variable model.

    Average fitted scores at each observed domain/variant, balanced over A/B.
    A/B placement effects are allowed to differ between source domains.
    """
    domains = sorted({r['domain'] for r in rows})
    variants = sorted({str(r['randomVariant']) for r in rows})
    def design(r, placement=None):
        ds = [float(r['domain'] == d) for d in domains]
        # Separate intercepts and A/B effects by domain; nested variant offsets.
        a = float(r['firstCondition'] == 'optimized') if placement is None else placement
        return ds + [x*a for x in ds] + [x*float(str(r['randomVariant']) == v) for x in ds for v in variants[1:]]
    X = np.array([design(r) for r in rows])
    inv = np.linalg.pinv(X.T@X)
    leverage = np.einsum('ij,jk,ik->i',X,inv,X)
    target = np.mean([np.mean([design(r,.5) for r in rows if r['domain']==d],axis=0) for d in domains],axis=0)
    result = {}
    for key in DIMENSIONS:
        y = np.array([orient_rating(r['comparisons'][key],r['firstCondition']) for r in rows])
        beta = inv@X.T@y
        residual = (y-X@beta)/np.maximum(1-leverage,1e-9)
        covariance = inv@(X.T@(X*residual[:,None]**2))@inv
        estimate = float(target@beta)
        se = float(np.sqrt(max(0,target@covariance@target)))
        result[key] = dict(adjusted_equal_domain_mean=estimate,HC3_95ci=[estimate-1.96*se,estimate+1.96*se],
                           optimized_in_A_effect_by_domain={d:float(beta[len(domains)+i]) for i,d in enumerate(domains)},
                           model_rank=int(np.linalg.matrix_rank(X)))
    return result
