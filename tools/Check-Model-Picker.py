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

def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)

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
        search=next(w for w in descendants(window) if isinstance(w,tk.Entry))
        assert any(isinstance(w,ttk.Scrollbar) and str(w['orient'])=='horizontal' for w in window.winfo_children())
        bar=next(w for w in window.winfo_children() if isinstance(w,ttk.Scrollbar) and str(w['orient'])=='horizontal')
        grip=[x for x in range(bar.winfo_width()) if bar.identify(x,bar.winfo_height()//2).endswith('grip')]
        assert grip and max(grip)-min(grip)<16,'Scrollbar grip should stay small when its handle stretches'
        use=next(w for w in descendants(window) if isinstance(w,DirtButton) and w.text=='Use selected model')
        for size in ('900x620','680x480'):
            window.geometry(size);root.update()
            for button in (w for w in descendants(window) if isinstance(w,DirtButton)):
                assert button.winfo_rooty()+button.winfo_height()<=window.winfo_rooty()+window.winfo_height(),button.text
        # Custom-drawn ttk elements retain the native scrollbar hit targets.
        listing.insert('end',*('Temporary row '+str(i)+' x'*100 for i in range(100)))
        root.update();listing.yview_moveto(.4);root.update()
        vertical=next(w for w in window.winfo_children() if isinstance(w,ttk.Scrollbar) and str(w['orient'])=='vertical')
        x,y=vertical.winfo_width()//2,vertical.winfo_height()-8
        assert vertical.identify(x,y).endswith('downarrow')
        before=listing.yview()[0]
        vertical.event_generate('<ButtonPress-1>',x=x,y=y);vertical.event_generate('<ButtonRelease-1>',x=x,y=y);root.update()
        assert listing.yview()[0]>before,'Drawn scrollbar arrow stopped scrolling'
        listing.yview_moveto(.2);root.update()
        thumb=[y for y in range(vertical.winfo_height()) if vertical.identify(vertical.winfo_width()//2,y).endswith('thumb')]
        assert thumb
        x,y=vertical.winfo_width()//2,thumb[len(thumb)//2]
        before=listing.yview()[0]
        vertical.event_generate('<ButtonPress-1>',x=x,y=y)
        vertical.event_generate('<B1-Motion>',x=x,y=y+20,state=256)
        vertical.event_generate('<ButtonRelease-1>',x=x,y=y+20);root.update()
        assert listing.yview()[0]>before,'Drawn scrollbar handle stopped dragging'
        horizontal=next(w for w in window.winfo_children() if isinstance(w,ttk.Scrollbar) and str(w['orient'])=='horizontal')
        listing.xview_moveto(.4);root.update()
        x,y=horizontal.winfo_width()-8,horizontal.winfo_height()//2
        assert horizontal.identify(x,y).endswith('downarrow')
        before=listing.xview()[0]
        horizontal.event_generate('<ButtonPress-1>',x=x,y=y);horizontal.event_generate('<ButtonRelease-1>',x=x,y=y);root.update()
        assert listing.xview()[0]>before,'Drawn horizontal arrow stopped scrolling'
        search.insert(0,'no-such-model');root.update()
        assert listing.size()==0 and not use.enabled
        use.invoke();assert window.winfo_exists() and viewer.model.current()==0
        next(w for w in descendants(window) if isinstance(w,DirtButton) and w.text=='Clear').invoke();root.update()
        assert listing.size()==2 and use.enabled
        search.insert(0,'beta');root.update();assert listing.size()==1 and listing.get(0).startswith('beta.geo.json')
        use.invoke();root.update()
        assert viewer.model.current()==1
        viewer.browse_models();root.update()
        window=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
        listing=next(w for w in window.winfo_children() if isinstance(w,tk.Listbox))
        assert listing.curselection()==(1,),'Picker did not preserve the current model'
        next(w for w in descendants(window) if isinstance(w,DirtButton) and w.text=='Cancel').invoke();root.update()
        assert viewer.model.current()==1
    finally:root.destroy()
empty=render_preview((),(300,400),30,14)
assert len(set(empty.getdata()))==1,'Converter still renders a decorative shadow'
empty=preview_model(None,None,(300,400),mesh=())
assert len(set(empty.getdata()))==1,'Skin preview still renders a decorative shadow'
print('Long ZIP model picker and shadow-free previews passed.')
