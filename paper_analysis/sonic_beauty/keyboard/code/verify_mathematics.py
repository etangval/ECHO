"""Finite verification of the higher-order table and transport algorithm."""
import json
import numpy as np
from scipy.optimize import linprog
from core_metrics import H,transport_cost,movement

coeff=H.copy()
for b in range(12):
 for s in range(4096):
  if s&(1<<b):coeff[s]-=coeff[s^(1<<b)]
reconstructed=coeff.copy()
for b in range(12):
 for s in range(4096):
  if s&(1<<b):reconstructed[s]+=reconstructed[s^(1<<b)]
err=float(np.max(abs(reconstructed-H)));assert err<1e-12
rot=0.
for s in range(4096):
 for r in range(12):
  ss=((s<<r)|(s>>(12-r)))&4095
  rot=max(rot,abs(H[s]-H[ss]))
assert rot<1e-12
assert abs(coeff[(1<<0)|(1<<4)|(1<<7)]+.45)<1e-12
rng=np.random.default_rng(2401);errs=[]
for _ in range(12):
 pa=np.sort(rng.choice(np.arange(21,109),4,False));pb=np.sort(rng.choice(np.arange(21,109),5,False))
 ma=rng.random(4);ma/=ma.sum();mb=rng.random(5);mb/=mb.sum()
 cost=np.array([[movement(abs(int(p-q))) for q in pb] for p in pa])
 A=[]
 for i in range(4):row=np.zeros((4,5));row[i,:]=1;A.append(row.ravel())
 for j in range(5):row=np.zeros((4,5));row[:,j]=1;A.append(row.ravel())
 lp=linprog(cost.ravel(),A_eq=A,b_eq=np.r_[ma,mb],bounds=(0,None),method='highs')
 assert lp.success
 errs.append(abs(lp.fun-transport_cost(pa,ma.copy(),pb,mb.copy())))
assert max(errs)<1e-9
print(json.dumps(dict(sets=4096,rotations_per_set=12,rotation_error=rot,mobius_reconstruction_error=err,major_triad_third_order_coefficient=float(coeff[145]),transport_linear_program_cases=12,transport_max_error=max(errs)),indent=2))
