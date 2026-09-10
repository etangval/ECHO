"""Extract Webern's three movements from a pinned public Humdrum encoding.

Optional acquisition/extraction step; requires music21==10.5.0.
python code/extract_webern.py --fetch
or: python code/extract_webern.py --source-dir /path/to/kern/files

The normal offline run_all.py uses the bundled opening events and needs no
music21. Complete source encodings are downloaded to ignored data/, not shipped.
Written repeats are not expanded; zero-duration grace notes are omitted.
"""
from pathlib import Path
import argparse, hashlib, json, sys, urllib.request
import numpy as np
import pandas as pd
from music21 import converter
from analyze import evaluate

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '335cbdc617c919d29e9384c4e490cabca5736f73'
BASE = f'https://raw.githubusercontent.com/automata/ana-music/{COMMIT}/corpus/classical/users/craig/classical/webern/op27/'
GIT_SHA = ['89c8e2d4b5978576ef12385af86b4ddf672386af',
           'eda654f085ebbb3d62e5ae11435eedad15c663d1',
           '06f34eceda479d0cd32312bd7e534ea522db6fc4']

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fetch', action='store_true')
    p.add_argument('--source-dir', type=Path, default=ROOT/'data/webern')
    args = p.parse_args()
    args.source_dir.mkdir(parents=True, exist_ok=True)
    openings=[]; reports=[]; full_results=[]
    for movement, expected_sha in enumerate(GIT_SHA, 1):
        name=f'variations-{movement}.krn'; f=args.source_dir/name
        if args.fetch:
            with urllib.request.urlopen(BASE+name, timeout=30) as response:
                f.write_bytes(response.read())
        raw=f.read_bytes()
        sha=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
        if sha != expected_sha:
            raise ValueError(f'Unexpected source content for {name}: {sha}')
        score=converter.parse(f)
        if len(score.parts)!=2: raise ValueError('Expected two keyboard staves')
        # Four scales and two phases require >=10 quarter notes. In movement I,
        # fourteen 3/16 bars supply 10.5 quarters; the other movements use 8 bars.
        last_bar={1:14,2:8,3:8}[movement]
        full=[]; selected=[]; ends=[]; measure_counts=[]; grace=0
        for staff,part in enumerate(score.parts,1):
            measures=[m for m in part.getElementsByClass('Measure') if m.highestTime>0]
            measure_counts.append(len(measures))
            for m in measures:
                bar=m.number; start=float(m.getOffsetInHierarchy(score))
                duration=float(m.highestTime)
                expected={1:.75,2:2.,3:6.}[movement]
                if movement==2 and bar==0: expected=1.
                if abs(duration-expected)>1e-7:
                    raise ValueError(f'Movement {movement}, bar {bar}: duration {duration}')
                if bar<=last_bar: ends.append(start+duration)
                for n in m.recurse().notes:
                    if n.duration.quarterLength<=0:
                        grace+=len(n.pitches);continue
                    for pitch in n.pitches:
                        r=dict(selection='webern_27',unit=movement,
                               onset=float(n.getOffsetInHierarchy(score)),
                               duration=float(n.duration.quarterLength),pitch=int(pitch.midi),
                               staff=str(staff),voice='',bar=bar,
                               measure_position=float(n.getOffsetInHierarchy(m)))
                        if not 21<=r['pitch']<=108: raise ValueError('Pitch outside piano range')
                        full.append(r)
                        if bar<=last_bar: selected.append(r)
        openings.extend(selected)
        end=float(score.highestTime)
        if measure_counts != {1:[54,54],2:[23,23],3:[66,66]}[movement]:
            raise ValueError('Unexpected movement coverage')
        z=evaluate(full,end)
        full_results.append(dict(movement=movement,notes=len(full),quarters=end,**z))
        reports.append(dict(movement=movement,source_url=BASE+name,
                            git_blob_sha1=sha,sha256=hashlib.sha256(raw).hexdigest(),
                            measures_per_staff=measure_counts,quarters=end,notes=len(full),
                            grace_noteheads_omitted=grace,opening_last_bar=last_bar,
                            opening_end_quarters=max(ends),opening_notes=len(selected)))
    ext=ROOT/'extensions';ext.mkdir(exist_ok=True)
    pd.DataFrame(openings).to_csv(ext/'webern_openings.csv',index=False)
    pd.DataFrame(full_results).to_csv(ext/'webern_full_movements.csv',index=False)
    keys=list(evaluate(full,end))
    aggregate={k:float(np.mean([r[k] for r in full_results])) for k in keys}
    (ext/'webern_full_summary.json').write_text(json.dumps(dict(
        work='Webern: Variations Op.27',aggregation='equal mean of three movements',
        repeats='written score, not expanded',movements=reports,coordinates=aggregate),indent=2)+'\n')
    print(json.dumps(reports,indent=2))

if __name__=='__main__': main()
