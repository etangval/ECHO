from pathlib import Path
import json,csv,hashlib,shutil
from collections import defaultdict
from music21 import converter,note,chord

ROOT=Path('/workspace/scratch/0c9800343be2')
OUT=ROOT/'output/digital_creativity_rewrite/Full_score_transcriptions_DRAFT'
OUT.mkdir(parents=True,exist_ok=True)
SPECS=[('Berg_Op1','berg',list(range(1,10)),'Berg_Sonata_Op1_CC0.pdf','berg',None),
 ('Webern_Op27_I','webern_I',[2,3,4],'Webern_Variations_Op27_CC0.pdf','webern',.75),
 ('Webern_Op27_II','webern_II',[5],'Webern_Variations_Op27_CC0.pdf','webern',2),
 ('Webern_Op27_III','webern_III',[6,7,8,9,10],'Webern_Variations_Op27_CC0.pdf','webern',6)]

summaries=[];allrows=[];notes=[];ledger=[]
for title,stem,pages,pdf,folder,expected in SPECS:
    base='analysis/full_scores_3600_berg_final' if title=='Berg_Op1' else 'analysis/full_scores'
    source=ROOT/base/stem/(stem+'.mxl')
    target=OUT/(title+'_unverified.mxl');shutil.copy2(source,target)
    shutil.copy2(source.with_suffix('.omr'),OUT/(title+'_Audiveris.omr'))
    s=converter.parse(source)
    for i,part in enumerate(s.parts,1):
        measures=list(part.getElementsByClass('Measure'))
        nums=[m.number for m in measures]
        missing=sorted(set(range(min(nums),max(nums)+1))-set(nums))
        eventcount=sum(len(n.pitches) for n in part.recurse().notes)
        summaries.append(dict(work=title,part=i,part_id=part.id,measures=len(measures),first_measure=min(nums),last_measure=max(nums),missing_measure_numbers=missing,noteheads=eventcount,raw_end_quarters=float(part.highestTime),status='UNVERIFIED; not used in numerical results'))
        for m in measures:
            dur=float(m.highestTime);bar_expected=expected
            if title=='Webern_Op27_II' and m.number==0:bar_expected=1 # source pickup
            flags=[]
            if bar_expected is not None and abs(dur-bar_expected)>1e-6:flags.append('duration differs from reference grid; verify rests/voices/tuplets')
            if title=='Webern_Op27_I' and not list(m.recurse().getElementsByClass('TimeSignature')) and m.number==min(nums):flags.append('missing 3/16 time signature')
            if title=='Berg_Op1' and len(s.parts)!=2:flags.append('unexpected part count; inspect staff assignment')
            allrows.append(dict(work=title,part=i,omr_measure=m.number,raw_onset=float(m.getOffsetInHierarchy(s)),raw_duration=dur,reference_duration=bar_expected,flags='; '.join(flags),manual_review_complete=False))
            for n in m.recurse().notes:
                if float(n.duration.quarterLength)<=0:continue
                for p in n.pitches:
                    notes.append(dict(work=title,part=i,omr_measure=m.number,raw_onset=float(n.getOffsetInHierarchy(s)),onset_in_measure=float(n.getOffsetInHierarchy(m)),raw_duration=float(n.duration.quarterLength),midi_pitch=p.midi,spelled_pitch=p.nameWithOctave,tie=n.tie.type if n.tie else '',status='UNVERIFIED'))
    for page in pages:ledger.append(dict(work=title,pdf=pdf,pdf_page_one_based=page,page_processed=True,full_note_review_complete=False))
    try:s.write('midi',fp=OUT/(title+'_unverified.mid'))
    except Exception as e:(OUT/(title+'_MIDI_export_error.txt')).write_text(str(e))

for name,rows in [('measure_audit',allrows),('raw_note_candidates',notes),('source_page_ledger',ledger)]:
    with (OUT/(name+'.csv')).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(OUT/'transcription_summary.json').write_text(json.dumps(summaries,indent=2,ensure_ascii=False))
readme='''# Full-score transcription candidates — NOT VERIFIED

2026-09-10

ベルク Op.1 は9ページすべて、ウェーベルン Op.27 は全3楽章の全楽譜ページを処理した自動採譜候補です。
音符が正確に全て転記された「確定フルバージョン」ではありません。原譜との照合で誤りが見つかっており、論文の数値には使用していません。

## 内容

- `*_unverified.mxl`: 全ページからの MusicXML 候補。MuseScore等で開いて修正できます。
- `*_Audiveris.omr`: 元画像と認識結果を保持する Audiveris 編集用ファイル。
- `*_unverified.mid`: 同じ候補からの確認用再生データ。音高・リズムの正しさや演奏を保証しません。
- `raw_note_candidates.csv`: 未校正の全音符候補。ここから美しさ指標を計算しないでください。
- `measure_audit.csv`: 小節・声部ごとの自動照合項目。フラグなしは正しさを意味しません。
- `source_page_ledger.csv`: PDFページと楽章の対応。

## 判明した問題

ベルクは3600ピクセル幅で全9ページを再処理した2段譜候補を採用しています。初回にあった余分な「Voice」パートはなくなりましたが、小節番号の欠落と局所的な音価・声部の誤りが残っています。
ウェーベルン第I楽章では3/16拍子が認識されておらず、全休符が4拍として展開される箇所があります。途中の音部記号変更の読み落としが音高にも影響しています。
第II・III楽章にも小節長や臨時記号、休符、声部の照合が必要です。
以前の比較値は第I楽章の別ページを第II楽章として集計していました。そのウェーベルンの点は撤回しています。

## 原譜

ベルク: Antoine Portesによる2020年の浄書、IMSLP #651355。IMSLPは浄書をCC0と表示しています。
https://imslp.org/wiki/Piano_Sonata,_Op.1_(Berg,_Alban)

ウェーベルン: Cheston Rewly / Roside Edition 2024、IMSLP #898272。IMSLPは浄書をCC0と表示していますが、原作品には米国での保護表示があります。浄書ライセンスと原作品の各国の著作権を同一視しないでください。
https://imslp.org/wiki/Variations_for_Piano,_Op.27_(Webern,_Anton)

どちらも、この作業では全小節・全音符の独立した校正を完了できていません。
修正後には、全曲版同士の解析または各作品の冒頭版と全曲版の明示的な対応比較として再計算してください。冒頭23項目の図へ全曲2項目だけを混ぜると評価範囲が不統一になります。
'''
(OUT/'README_ja.md').write_text(readme)
for spec in SPECS:
 title,stem,pages,pdf,folder,_=spec
 p=ROOT/'analysis/new_modern'/folder/pdf
 if p.exists():
  with (OUT/'source_hashes.txt').open('a') as f:f.write(f'{pdf}: {hashlib.sha256(p.read_bytes()).hexdigest()}\n')
print(json.dumps(summaries,indent=2))
