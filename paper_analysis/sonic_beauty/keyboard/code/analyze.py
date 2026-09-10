"""v2 score descriptors. Not fitted to listener judgments.
X: template affinity plus roughness, exact duration integration.
Y: multiscale optimal pitch-distribution transport, all registers included.
Run in this directory: python analyze.py [--controls N]
"""
from pathlib import Path
import csv,json,argparse
from collections import defaultdict
import numpy as np
from core_metrics import harmony,transport_cost
ROOT=Path(__file__).resolve().parent
SPANS=(.5,1.,2.,4.)

def merged_intervals(rows):
 by=defaultdict(list)
 for r in rows:by[r['pitch']].append((r['onset'],r['onset']+r['duration']))
 result={}
 for p,intervals in by.items():
  out=[]
  for a,b in sorted(intervals):
   if out and a<=out[-1][1]+1e-8:out[-1]=(out[-1][0],max(out[-1][1],b))
   else:out.append((a,b))
  result[p]=out
 return result

def pitch_windows(intervals,end,span,phase=0.):
 # Include only complete windows; score pickup/ending partial windows omitted.
 starts=np.arange(phase*span,end-span+1e-8,span)
 occ=np.zeros((len(starts),88))
 for p,segments in intervals.items():
  for a,b in segments:occ[:,p-21]+=np.maximum(0,np.minimum(starts+span,b)-np.maximum(starts,a))
 return occ

def motion_cost(intervals,end,span,phase=0.):
 occ=pitch_windows(intervals,end,span,phase);cs=[]
 for a,b in zip(occ,occ[1:]):
  ia,ib=np.flatnonzero(a),np.flatnonzero(b)
  if len(ia) and len(ib):cs.append(transport_cost(ia+21,a[ia],ib+21,b[ib]))
 return float(np.mean(cs)) if cs else float('nan')

def motion(rows,end):
 intervals=merged_intervals(rows)
 by_span=[np.mean([motion_cost(intervals,end,s,p) for p in (0.,.5)]) for s in SPANS]
 m=float(np.mean(by_span))
 return dict(M=m,Y=float(100*np.exp(-m)),Y_min=float(100*np.exp(-max(by_span))),Y_max=float(100*np.exp(-min(by_span))),**{f'M_span_{s:g}':float(c) for s,c in zip(SPANS,by_span)})

def evaluate(rows,end,sensitivity=True):
 h=harmony(rows,end,.5);y=motion(rows,end)
 if sensitivity:
  xs=[harmony(rows,end,t)['X'] for t in (0.,.25,.5,1.)]
  h.update(X_min=min(xs),X_max=max(xs))
 return {**h,**y}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--controls',type=int,default=0);args=parser.parse_args()
 meta=json.load(open(ROOT/'metadata.json'));notes=list(csv.DictReader(open(ROOT/'notes.csv')))
 for r in notes:
  for k in ('onset','duration'):r[k]=float(r[k])
  for k in ('pitch','bar'):r[k]=int(r[k])
 results=[];nulls=[]
 for i,m in enumerate(meta,1):
  rows=[r for r in notes if r['piece']==m['id']];end=m['duration_quarters']
  result=dict(number=i,id=m['id'],composer=m['composer'],title=m['title'],short=m['short'],noteheads=m['noteheads'],duration_quarters=end,**evaluate(rows,end))
  print(i,m['id'],round(result['X'],2),round(result['Y'],2),flush=True)
  if args.controls:
   rng=np.random.default_rng(20260910+i);xs=[];ys=[]
   # Shuffle pitches among written noteheads within the piece, preserving
   # the global pitch histogram, note onsets, durations and polyphony skeleton.
   for k in range(args.controls):
    pitches=rng.permutation([r['pitch'] for r in rows]);sh=[dict(r,pitch=int(p)) for r,p in zip(rows,pitches)]
    z=evaluate(sh,end,False);xs.append(z['X']);ys.append(z['Y'])
    nulls.append(dict(id=m['id'],replicate=k,X=z['X'],Y=z['Y']))
   result.update(shuffle_n=args.controls,shuffle_X_mean=float(np.mean(xs)),shuffle_Y_mean=float(np.mean(ys)),shuffle_X_sd=float(np.std(xs,ddof=1)),shuffle_Y_sd=float(np.std(ys,ddof=1)))
  results.append(result)
  (ROOT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 with (ROOT/'results.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
 if nulls:
  with (ROOT/'shuffle_controls.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(nulls[0]));w.writeheader();w.writerows(nulls)
if __name__=='__main__':main()
