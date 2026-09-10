"""Reproduce every reported coordinate from the supplied excerpt events.
Usage: python code/reproduce.py [--controls]
Requirements: Python 3.12, numpy, pandas (see requirements.txt).
No network access or OMR software is required.
"""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from analyze import evaluate
ROOT=Path(__file__).resolve().parents[1]

def aggregate(parts,sensitivity=True):
    zs=[evaluate(rows,end,sensitivity) for rows,end in parts]
    if any(not np.isfinite(v) for z in zs for v in z.values()):
        raise ValueError('Undefined metric in an intended component')
    return {k:float(np.mean([z[k] for z in zs])) for k in zs[0]}

parser=argparse.ArgumentParser();parser.add_argument('--controls',action='store_true');a=parser.parse_args()
notes=pd.read_csv(ROOT/'analysis_notes_25.csv',keep_default_na=False)
manifest=pd.read_csv(ROOT/'excerpt_manifest_25.csv');ref=pd.read_csv(ROOT/'comparison_25.csv')
rowsout=[];nullout=[];maximum=0.
for selection in ref.itertuples():
    parts=[]
    for unit in manifest[manifest.id==selection.id].itertuples():
        rows=notes[(notes.selection==selection.id)&(notes.unit==unit.unit)].to_dict('records')
        assert rows and all(21<=r['pitch']<=108 and r['duration']>0 and r['onset']>=0 and r['onset']+r['duration']<=unit.end_quarters+1e-7 for r in rows)
        parts.append((rows,float(unit.end_quarters)))
    z=aggregate(parts);maximum=max(maximum,max(abs(z[k]-getattr(selection,k)) for k in ['X','Y','H','R','M','coverage','X_min','X_max','Y_min','Y_max']))
    rowsout.append(dict(id=selection.id,**z))
    if a.controls:
        rng=np.random.default_rng(20260910+selection.number)
        for b in range(99):
            pp=[]
            for rr,end in parts:
                pitches=rng.permutation([r['pitch'] for r in rr])
                pp.append(([dict(r,pitch=int(p)) for r,p in zip(rr,pitches)],end))
            zz=aggregate(pp,False);nullout.append(dict(id=selection.id,replicate=b,X=zz['X'],Y=zz['Y']))
assert maximum<1e-8,maximum
pd.DataFrame(rowsout).to_csv(ROOT/'reproduced_coordinates_25.csv',index=False)
report=dict(selections=len(rowsout),units=len(manifest),noteheads=len(notes),max_coordinate_difference=maximum,all_components_defined=True,omr_included=False)
if a.controls:
    actual=pd.DataFrame(nullout);expected=pd.read_csv(ROOT/'permutation_controls_25.csv')
    assert (actual[['id','replicate']].values==expected[['id','replicate']].values).all()
    error=float(np.max(np.abs(actual[['X','Y']].values-expected[['X','Y']].values)))
    assert error<1e-8,error
    report['max_control_difference']=error
print(json.dumps(report,indent=2))
