"""Long ZIP paths remain distinguishable, searchable and fully readable."""
import json,sys,tempfile,tkinter as tk,zipfile
from pathlib import Path
from tkinter import ttk
from PIL import Image
import io
sys.path.insert(0,str(Path('src').resolve()))
from PrismConverter import ModelSource
from PrismConverterUI import Converter,DirtButton
from PrismConverterPreview import render_preview
from PrismSkinPack import preview_model

with tempfile.TemporaryDirectory(dir='work',prefix='picker-check-') as tmp:
    archive=Path(tmp)/'pack.zip';prefix='A very long resource pack folder name/'+'nested-folder/'*12
    stream=io.BytesIO();Image.new('RGBA',(16,16),(100,180,220,255)).save(stream,format='PNG')
    with zipfile.ZipFile(archive,'w') as z:
        for name in ('alpha','beta'):
            geometry={'minecraft:geometry':[{'description':{'identifier':'geometry.'+name,'texture_width':16,'texture_height':16},'bones':[{'name':'root','cubes':[{'origin':[0,0,0],'size':[2,2,2],'uv':[0,0]}]}]}]}
            z.writestr(prefix+'models/entity/'+name+'.geo.json',json.dumps(geometry))
            z.writestr(prefix+'textures/entity/'+name+'.png',stream.getvalue())
    root=tk.Tk();root.geometry('1000x960');viewer=Converter(root)
    try:
        viewer.loaded(ModelSource(archive));root.update()
        assert viewer.model['values'][0].startswith('alpha.geo.json')
        viewer.browse_models();root.update()
        window=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
        listing=next(w for w in window.winfo_children() if isinstance(w,tk.Listbox))
        search=next(w for w in window.winfo_children() if isinstance(w,tk.Entry))
        details=next(w for w in window.winfo_children() if isinstance(w,tk.Text))
        assert prefix in details.get('1.0','end') and 'alpha.geo.json' in details.get('1.0','end')
        assert any(isinstance(w,ttk.Scrollbar) and str(w['orient'])=='horizontal' for w in window.winfo_children())
        search.insert(0,'beta');root.update();assert listing.size()==1 and listing.get(0).startswith('beta.geo.json')
        next(w for w in window.winfo_children() if isinstance(w,DirtButton)).invoke();root.update()
        assert viewer.model.current()==1
    finally:root.destroy()
empty=render_preview((),(300,400),30,14)
assert len(set(empty.getdata()))==1,'Converter still renders a decorative shadow'
empty=preview_model(None,None,(300,400),mesh=())
assert len(set(empty.getdata()))==1,'Skin preview still renders a decorative shadow'
print('Long ZIP model picker and shadow-free previews passed.')
