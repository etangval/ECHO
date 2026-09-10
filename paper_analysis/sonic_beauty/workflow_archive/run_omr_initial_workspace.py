from pathlib import Path
import fitz
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import subprocess
ROOT=Path('/workspace/scratch/0c9800343be2')
items=[('berg','berg/Berg_Sonata_Op1_CC0.pdf',list(range(9))),('webern_I','webern/Webern_Variations_Op27_CC0.pdf',[1,2,3]),('webern_II','webern/Webern_Variations_Op27_CC0.pdf',[4]),('webern_III','webern/Webern_Variations_Op27_CC0.pdf',[5,6,7,8,9])]
def job(item):
 name,p,ixs=item; out=ROOT/'analysis/full_scores'/name;out.mkdir(exist_ok=True)
 doc=fitz.open(ROOT/'analysis/new_modern'/p); ims=[]
 for i in ixs:
  pix=doc[i].get_pixmap(matrix=fitz.Matrix(2600/doc[i].rect.width,2600/doc[i].rect.width),colorspace=fitz.csGRAY)
  ims.append(Image.frombytes('L',(pix.width,pix.height),pix.samples))
 tif=out/(name+'.tif');ims[0].save(tif,save_all=True,append_images=ims[1:],compression='tiff_lzw')
 with (out/'run.log').open('w') as log:
  x=subprocess.run([str(ROOT/'analysis/audiveris/opt/audiveris/bin/Audiveris'),'-batch','-transcribe','-export','-output',str(out),str(tif)],stdout=log,stderr=subprocess.STDOUT)
 print(name,'done',x.returncode,flush=True)
with ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(job,items))
