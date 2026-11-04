"""Fractional cube sizes retain exact physical bounds and independent face UVs."""
import copy,json,math,sys,tempfile
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path("src").resolve()))
from PrismConverter import ModelSource,build_model,convert_model
from PrismPolygonPreview import prepare_source_preview
from PrismConverterPreview import render_preview

with tempfile.TemporaryDirectory(dir="work",prefix="fractional-check-") as tmp:
    root=Path(tmp);image=Image.new("RGBA",(16,16))
    for y in range(16):
        for x in range(16):image.putpixel((x,y),(x*16,y*16,80,255))
    image.save(root/"detail.png")
    cube={"origin":[-1.125,2.25,-.875],"size":[.25,2.5,1.75],"pivot":[1,2,3],"rotation":[10,20,30],
          "uv":{"north":{"uv":[1,2],"uv_size":[4,3]}}}
    geometry={"description":{"identifier":"geometry.detail","texture_width":16,"texture_height":16},
              "bones":[{"name":"detail","pivot":[1,2,3],"cubes":[cube]}]}
    path=root/"detail.geo.json"
    def load():path.write_text(json.dumps({"minecraft:geometry":[geometry]}));return ModelSource(path)
    for inflation in (0,.125,-.05):
        cube["inflate"]=inflation;source=load();model,atlas,report=build_model(source,0)
        shape=model["parts"][0]["shapes"][0];scale=shape["scale"]
        for axis in range(3):
            physical=(shape["to"][axis]-shape["from"][axis])*scale[axis]
            assert math.isclose(physical,cube["size"][axis]+2*inflation,abs_tol=1e-10)
            assert math.isclose(shape["to"][axis]-shape["from"][axis],round(shape["to"][axis]-shape["from"][axis]),abs_tol=1e-10)
        assert shape["inflate"]==0 and shape["position"]==[0,0,0]
        assert shape["rotation"]==[10,-20,-30]
        u,v=shape["uv"];w=round(shape["to"][0]-shape["from"][0]);h=round(shape["to"][1]-shape["from"][1])
        assert atlas.crop((round(u),round(v),round(u)+w,round(v)+h)).tobytes()==image.crop((1,2,5,5)).resize((w,h),Image.Resampling.NEAREST).tobytes()
        assert prepare_source_preview(source,0)
    # Very thin geometry no longer triggers the old global texture-density limit.
    cube["inflate"]=0;cube["size"]=[.001,2.5,1.75];source=load()
    report=convert_model(source,0,root/"thin-export")
    shape=json.loads((root/"thin-export/thin-export.mimodel").read_text())["parts"][0]["shapes"][0]
    assert math.isclose((shape["to"][0]-shape["from"][0])*shape["scale"][0],.001,abs_tol=1e-12)
    # Subpixel UV rectangles sample continuously rather than rounding to an empty crop.
    cube["uv"]["north"]={"uv":[1.1,2.1],"uv_size":[.1,.1]};assert build_model(load(),0)
    cube["uv"]["north"]={"uv":[5,5],"uv_size":[-4,-3],"uv_rotation":90};assert prepare_source_preview(load(),0)
    cube["size"]=[0,2.5,1.75];cube["uv"]={"west":{"uv":[1,2],"uv_size":[3,4]}}
    assert prepare_source_preview(load(),0),"Fractional zero-thickness plane disappeared"
    # Blockbench per-face cubes use the same scaled-shape path.
    bb={"name":"Detail","resolution":{"width":16,"height":16},"meta":{"box_uv":False},
        "elements":[{"uuid":"cube","from":[0,0,0],"to":[.25,2.5,1.75],"faces":{"north":{"uv":[1,2,5,5],"texture":0}}}],"outliner":["cube"]}
    bbpath=root/"detail.bbmodel";bbpath.write_text(json.dumps(bb))
    assert prepare_source_preview(ModelSource(bbpath),0,texture_path=root/"detail.png")
print("Fractional cubes passed: exact scaled bounds, rotations/pivots, positive/negative inflation, face textures, tiny details, subpixel/reversed UVs, thin planes and Blockbench models.")
