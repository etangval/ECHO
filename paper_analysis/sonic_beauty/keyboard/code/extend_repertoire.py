"""Build the 25-selection reference from the original 23 plus Berg and Webern.

Run from any directory: python keyboard/code/extend_repertoire.py
All numerical inputs are bundled; the script performs 99 seeded controls for
each added selection and preserves the original 23 coordinates and controls.
"""
from pathlib import Path
import json,re
import numpy as np
import pandas as pd
from analyze import evaluate
ROOT=Path(__file__).resolve().parents[1]

def mean_results(parts, sensitivity=True):
    zs=[evaluate(rows,end,sensitivity) for rows,end in parts]
    if not all(np.isfinite(v) for z in zs for v in z.values()):
        raise ValueError('Undefined descriptor')
    return {k:float(np.mean([z[k] for z in zs])) for k in zs[0]}

def midi(name):
    match=re.fullmatch(r'([A-G])([#-]*)(\d)',name)
    if not match: raise ValueError(name)
    step,accidental,octave=match.groups()
    return 12*(int(octave)+1)+dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[step]+accidental.count('#')-accidental.count('-')

def main():
    notes=pd.read_csv(ROOT/'analysis_notes.csv',keep_default_na=False)
    manifest=pd.read_csv(ROOT/'excerpt_manifest.csv')
    reference=pd.read_csv(ROOT/'comparison_23.csv')
    controls=pd.read_csv(ROOT/'permutation_controls.csv')
    berg=json.loads((ROOT/'extensions/berg_opening.json').read_text())
    added=[]
    for bar,staff,onset,duration,pitches in berg['events']:
        for name in pitches.split():
            added.append(dict(selection='berg_1',unit=1,onset=(0 if bar==0 else 2+3*(bar-1))+onset,
                              duration=duration,pitch=midi(name),staff=str(staff),voice='',bar=bar,measure_position=onset))
    extra=pd.concat([pd.DataFrame(added),pd.read_csv(ROOT/'extensions/webern_openings.csv',keep_default_na=False)],ignore_index=True)
    w=json.loads((ROOT/'extensions/webern_full_summary.json').read_text())
    metas=[dict(id='berg_1',unit=1,end_quarters=26.,notes=len(added),scope='pickup plus complete bars 1-8',source=berg['source'])]
    for r in w['movements']:
        metas.append(dict(id='webern_27',unit=r['movement'],end_quarters=r['opening_end_quarters'],notes=r['opening_notes'],
                          scope=f"pickup, if any, plus complete bars 1-{r['opening_last_bar']}",source=r['source_url']))
    values=[];nullrows=[]
    for number,ident,composer,title in [(24,'berg_1','Berg','Piano Sonata Op.1'),(25,'webern_27','Webern','Variations Op.27 (3 movements)')]:
        ms=[m for m in metas if m['id']==ident]
        parts=[(extra[(extra.selection==ident)&(extra.unit==m['unit'])].to_dict('records'),m['end_quarters']) for m in ms]
        for rows,end in parts:
            assert all(21<=r['pitch']<=108 and r['onset']>=0 and r['duration']>0 and r['onset']+r['duration']<=end+1e-7 for r in rows)
        z=mean_results(parts);rng=np.random.default_rng(20260910+number);null=[]
        for b in range(99):
            shuffled=[([dict(r,pitch=int(p)) for r,p in zip(rows,rng.permutation([r['pitch'] for r in rows]))],end) for rows,end in parts]
            zz=mean_results(shuffled,False);null.append(zz)
            nullrows.append(dict(id=ident,replicate=b,X=zz['X'],Y=zz['Y']))
        row=dict(number=number,id=ident,composer=composer,title=title,source=ms[0]['source'],units=len(parts),notes=sum(len(rows) for rows,end in parts),quarters=sum(end for rows,end in parts),**z)
        for k in ['X','Y']:
            ns=np.array([zz[k] for zz in null])
            row.update({f'null_{k}_mean':float(ns.mean()),f'null_{k}_sd':float(ns.std(ddof=1)),f'null_{k}_tail_fraction':float((1+(ns>=z[k]).sum())/100)})
        values.append(row)
    result=pd.concat([reference,pd.DataFrame(values)],ignore_index=True)
    result.to_csv(ROOT/'comparison_25.csv',index=False)
    pd.concat([notes,extra],ignore_index=True).to_csv(ROOT/'analysis_notes_25.csv',index=False)
    pd.concat([manifest,pd.DataFrame(metas)],ignore_index=True).to_csv(ROOT/'excerpt_manifest_25.csv',index=False)
    pd.concat([controls,pd.DataFrame(nullrows)],ignore_index=True).to_csv(ROOT/'permutation_controls_25.csv',index=False)
    register=result[['number','id','composer','title','X','Y']].copy();register['status']='opening excerpt'
    register.to_csv(ROOT/'selection_register_25.csv',index=False)
    print(result.tail(2)[['composer','X','Y','notes','quarters']].to_string(index=False))

if __name__=='__main__': main()
