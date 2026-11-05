"""Run actual background preview/batch workflows through the Converter UI."""
import json,sys,tempfile,time,tkinter as tk,zipfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path("src").resolve()))
from PrismConverterUI import Converter

def pump(root,condition):
    deadline=time.monotonic()+15
    while not condition():
        root.update()
        if time.monotonic()>deadline:raise AssertionError("Background UI work timed out")
        time.sleep(.01)

with tempfile.TemporaryDirectory(dir="work",prefix="converter-flow-") as tmp:
    base=Path(tmp);pack=base/"pack";pack.mkdir()
    for name,color in (("robot",(240,40,40,255)),("sheep",(40,240,40,255))):
        Image.new("RGBA",(16,16),color).save(pack/(name+".png"))
        geometry={"minecraft:geometry":[{"description":{"identifier":"geometry."+name,"texture_width":16,"texture_height":16},
            "bones":[{"name":"body","pivot":[0,0,0],"cubes":[{"origin":[-2,0,-2],"size":[4,8,4],"uv":[0,0]}]}]}]}
        (pack/(name+".geo.json")).write_text(json.dumps(geometry))
    root=tk.Tk();root.geometry("1000x900");converter=Converter(root)
    try:
        converter.load(pack)
        pump(root,lambda:converter.source is not None and converter.mesh is not None)
        assert converter.texture.get()=="robot.png"
        canvas=converter.canvas;canvas.event_generate("<ButtonPress-1>",x=50,y=50);canvas.event_generate("<B1-Motion>",x=100,y=100)
        assert (converter.yaw,converter.pitch)==(0,44)
        cached=converter.mesh;converter.render();assert converter.mesh is cached
        canvas.event_generate("<ButtonRelease-1>",x=100,y=100);converter.reset_view()
        assert (converter.yaw,converter.pitch)==(30,14)
        converter.model.current(1);converter.select_model()
        pump(root,lambda:converter.mesh is not None)
        assert converter.texture.get()=="sheep.png" and converter.mesh is not cached
        # Latest selection wins if previous background preview is still running.
        converter.model.current(0);converter.select_model();converter.model.current(1);converter.select_model()
        pump(root,lambda:converter.mesh is not None)
        assert converter.texture.get()=="sheep.png"
        converter.export_name.set("Snow Sheep")
        converter.model.current(0);converter.select_model();converter.export_name.set("Blue Robot")
        converter.model.current(1);converter.select_model()
        assert converter.export_name.get()=="Snow Sheep"
        out=base/"all"
        with patch("PrismConverterUI.filedialog.asksaveasfilename",return_value=str(out)),patch("PrismConverterUI.messagebox.showinfo") as notice:
            converter.batch();pump(root,lambda:not converter.busy)
            assert notice.called
        report=json.loads((out/"batch-report.json").read_text())
        assert report["exported"]==2 and not report["failed"]
        for name in ("Snow Sheep","Blue Robot"):
            model=json.loads((out/name/(name+".mimodel")).read_text())
            assert model["name"]==name and model["texture"]==name+"_texture.png"
            assert (out/name/model["texture"]).is_file()
        assert "2 exported" in converter.status.get(),converter.status.get()
        assert converter.output==out and converter.batch_button.text=="Export all models…"
        data=json.loads((pack/"robot.geo.json").read_text());bone=data["minecraft:geometry"][0]["bones"][0]
        bone["binding"]="q.item_slot_to_bone_name(c.item_slot)"
        binding=pack/"bound.geo.json";binding.write_text(json.dumps(data))
        converter.load(binding)
        pump(root,lambda:not converter.busy and converter.source.path==binding and converter.mesh is not None)
        assert converter.convert_button.enabled
        bound_out=base/"bound-export"
        with patch("PrismConverterUI.filedialog.asksaveasfilename",return_value=str(bound_out)),patch("PrismConverterUI.messagebox.showinfo"):
            converter.convert();pump(root,lambda:not converter.busy)
        assert (bound_out/"bound.mimodel").is_file()
        bone["poly_mesh"]={"positions":[[0,0,0],[8,0,0],[0,8,0]],"uvs":[[0,0],[16,0],[0,16]],"polys":"tri_list"}
        polygon=pack/"polygon.geo.json";polygon.write_text(json.dumps(data))
        converter.load(polygon)
        pump(root,lambda:not converter.busy and converter.source.path==polygon and converter.mesh is not None)
        assert not converter.convert_button.enabled
        assert "Polygon mesh preview" in converter.details.get("1.0","end")
        # Multiple available colors should still produce a textured preview.
        colors=base/'colors';colors.mkdir()
        for name,color in [('red','red'),('blue','blue')]:
            Image.new('RGBA',(16,16),color).save(colors/('armor_body_'+name+'.png'))
        colored_geometry=json.loads(json.dumps(geometry))
        colored_geometry['minecraft:geometry'][0]['description']['identifier']='geometry.demo_armor_body'
        (colors/'armor_body.geo.json').write_text(json.dumps(colored_geometry))
        archive=base/'asset-only.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for asset in colors.iterdir():
                folder='models/entity' if asset.suffix=='.json' else 'textures/entity'
                z.write(asset,f'Example Pack/{folder}/{asset.name}')
        converter.load(archive)
        pump(root,lambda:not converter.busy and converter.source.path==archive and converter.mesh is not None)
        assert converter.texture.get()=='Example Pack/textures/entity/armor_body_blue.png','No deterministic default color selected'
        assert 'Showing one available texture' in converter.details.get('1.0','end')
        from PrismConverterPreview import render_preview
        blue=render_preview(converter.mesh,(200,200),30,14).tobytes()
        red_path='Example Pack/textures/entity/armor_body_red.png'
        converter.texture.set(red_path);converter.texture_changed()
        pump(root,lambda:converter.mesh is not None)
        red=render_preview(converter.mesh,(200,200),30,14).tobytes()
        assert red!=blue,'Switching color did not update the textured preview'
        converter.select_model();pump(root,lambda:converter.mesh is not None)
        assert converter.texture.get()==red_path,'Automatic default overwrote manual color choice'
    finally:root.destroy()
print("Converter workflow passed: background loading/preview, matching, mouse orbit/reset, stale selection handling and separate batch exports.")
