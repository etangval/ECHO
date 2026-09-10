"""Core chord affinity, roughness and transport costs for score-model v2.
Chord vocabulary and roughness adapted from digitalcreativity v0.1.0,
MIT, Copyright (c) 2026 Yuji Ikegaya. See LICENSE-digitalcreativity.txt.
These are uncalibrated computational descriptors, not human beauty ratings.
"""
from pathlib import Path
from collections import defaultdict
import csv, json
import numpy as np

ROOT=Path(__file__).resolve().parent

def chord_table():
    qualities=[([0,4,7],0),([0,3,7],0),([0,2,7],.05),([0,5,7],.05),
      ([0,3,6],.10),([0,4,8],.13),([0,4,7,10],.02),([0,4,7,11],.03),
      ([0,3,7,10],.02),([0,4,7,9],.02),([0,3,7,9],.02),
      ([0,3,6,10],.07),([0,3,6,9],.09),([0,2,4,7],.05),
      ([0,2,3,7],.05),([0,2,4,7,10],.10),([0,2,4,7,11],.11),
      ([0,2,3,7,10],.10),([0,2,4,7,9],.10)]
    vocab={}
    for ints,prior in qualities:
        for root in range(12):
            pcs=tuple(sorted((root+x)%12 for x in ints))
            if pcs not in vocab:vocab[pcs]=prior
    sets=((np.arange(4096)[:,None] & (1<<np.arange(12)))>0).astype(float)
    templates=np.array([np.isin(np.arange(12),s) for s in vocab],float)
    n=sets.sum(1); overlap=sets@templates.T; nt=templates.sum(1)
    costs=3*(n[:,None]-overlap)/np.maximum(1,n[:,None])+.45*(nt-overlap)/nt+np.array(list(vocab.values()))
    table=costs.min(1);table[n<=1]=0
    return table

def roughness_table():
    f=440*2**((np.arange(21,109)-69)/12)
    r=np.zeros((88,88))
    for h in range(1,7):
        for k in range(1,7):
            a,b=f[:,None]*h,f[None,:]*k
            x=.24*np.abs(a-b)/(.021*np.minimum(a,b)+19)
            r+=(np.exp(-3.5*x)-np.exp(-5.75*x))/(h*k)**1.4
    r/=r.max();np.fill_diagonal(r,0)
    return r

H=chord_table(); R=roughness_table()

def movement(d):
    return d/12 + .5*(max(0,d-7)/12)**2

def transport_cost(pa,ma,pb,mb):
    """Exact 1D monotone transport for convex movement cost; mass sums to one.
    This is an implicit-voice motion lower bound, not recovered true voices.
    """
    ia=np.argsort(pa);ib=np.argsort(pb)
    pa,ma=np.asarray(pa)[ia],np.asarray(ma,dtype=float)[ia]
    pb,mb=np.asarray(pb)[ib],np.asarray(mb,dtype=float)[ib]
    ma/=ma.sum();mb/=mb.sum()
    i=j=0;cost=0
    while i<len(pa) and j<len(pb):
        dm=min(ma[i],mb[j]);cost+=dm*movement(abs(float(pa[i]-pb[j])))
        ma[i]-=dm;mb[j]-=dm
        if ma[i]<1e-10:i+=1
        if mb[j]<1e-10:j+=1
    return float(cost)

def harmony(rows,end,tail=.5):
    """Exact duration integration of unique sounding pitches; no time grid.
    The assumed release extension is in quarter-note units, not real seconds.
    Monophonic and silent regions are not assigned perfect harmony ratings.
    """
    changes=defaultdict(list)
    changes[0.];changes[end]
    for r in rows:
        start=r['onset'];stop=min(end,start+r['duration']+tail)
        if stop>start:
            changes[start].append((r['pitch'],1));changes[stop].append((r['pitch'],-1))
    times=sorted(changes);active=defaultdict(int)
    duration=total_h=total_r=0
    for k,t in enumerate(times[:-1]):
        for p,delta in changes[t]:active[p]+=delta
        pitches=sorted(p for p,n in active.items() if n>0)
        dt=times[k+1]-t
        if len(pitches)<2:continue
        mask=sum(1<<pc for pc in set(p%12 for p in pitches))
        ids=np.array(pitches)-21
        rv=R[np.ix_(ids,ids)].sum()/(len(ids)*(len(ids)-1))
        total_h+=dt*H[mask];total_r+=dt*rv;duration+=dt
    if duration==0:return dict(H=None,R=None,coverage=0,X=None)
    mh,mr=total_h/duration,total_r/duration
    return dict(H=float(mh),R=float(mr),coverage=duration/end,X=float(100*np.exp(-mh-.3*mr)))
