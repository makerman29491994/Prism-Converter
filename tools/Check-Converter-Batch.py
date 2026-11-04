"""Automatic texture associations, independent batch bundles and preview transforms."""
import base64,io,json,sys,tempfile,threading
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path("src").resolve()))
from PrismConverter import ModelSource,match_texture,batch_convert,build_model
from PrismConverterPreview import preview_mesh,render_preview

def geometry(name):
    return {"minecraft:geometry":[{"description":{"identifier":"geometry."+name,"texture_width":16,"texture_height":16},
        "bones":[{"name":"base","pivot":[2,2,0],"rotation":[10,20,30],"cubes":[{"origin":[0,0,0],"size":[2,2,2],"uv":[0,0]}]},
                 {"name":"child","parent":"base","pivot":[2,4,0],"rotation":[0,45,0],"cubes":[{"origin":[1,3,0],"size":[2,2,2],"uv":[0,0]}]}]}]}

with tempfile.TemporaryDirectory(dir="work",prefix="batch-check-") as tmp:
    root=Path(tmp);pack=root/"pack"
    for folder in ("models/entity","textures/entity","textures/other","entity","models/other"):(pack/folder).mkdir(parents=True)
    for name,color in (("different_name",(200,20,30,255)),("sheep",(30,200,20,255)),("hat",(20,30,200,255))):
        Image.new("RGBA",(16,16),color).save(pack/f"textures/entity/{name}.png")
    Image.new("RGBA",(16,16),(200,200,30,255)).save(pack/"textures/other/hat.png")
    for name in ("robot","sheep","hat","missing"):(pack/f"models/entity/{name}.geo.json").write_text(json.dumps(geometry(name)))
    (pack/"models/other/sheep.geo.json").write_text(json.dumps(geometry("sheep")))
    (pack/"entity/robot.entity.json").write_text(json.dumps({"minecraft:client_entity":{"description":{
        "geometry":{"default":"geometry.robot"},"textures":{"default":"textures/entity/different_name"}}}}))
    source=ModelSource(pack);indices={Path(m["file"]).parent.as_posix()+"/"+Path(m["file"]).name:i for i,m in enumerate(source.models)}
    index=lambda name:indices[f"models/entity/{name}.geo.json"]
    assert match_texture(source,index("robot"))["texture"]=="textures/entity/different_name.png"
    assert match_texture(source,index("sheep"))["texture"]=="textures/entity/sheep.png"
    assert match_texture(source,index("hat"))["status"]=="ambiguous"
    assert match_texture(source,index("missing"))["status"]=="missing"
    single=ModelSource(pack/"models/entity/robot.geo.json")
    assert len(single.models)==1 and match_texture(single,0)["status"]=="matched"
    model,atlas,_=build_model(single,0);mesh=preview_mesh(model,atlas)
    assert mesh and sum(len(face[2]) for face in mesh)<40000
    a=render_preview(mesh,(300,400),30,14);b=render_preview(mesh,(300,400),120,70)
    assert a.tobytes()!=b.tobytes()
    assert a.getbbox() and any(pixel==(200,20,30) for pixel in a.getdata()),"Preview lost the matched texture"
    out=root/"batch";report=batch_convert(source,out)
    assert report["exported"]==3 and report["skipped"]==2 and report["failed"]==0,report
    folders=[r["folder"] for r in report["models"] if r["status"]=="exported"]
    assert len({x.casefold() for x in folders})==3,"Duplicate model names collided"
    for folder in folders:
        assert (out/folder/(folder+".mimodel")).is_file() and (out/folder/(folder+"_texture.png")).is_file()
    assert len(json.loads((out/"batch-report.json").read_text())["models"])==5
    try:batch_convert(source,out)
    except FileExistsError:pass
    else:raise AssertionError("Batch overwrote existing folder")
    corrected=batch_convert(source,root/"corrected",{index("hat"):("textures/entity/hat.png",None)})
    assert corrected["exported"]==4
    stop=threading.Event()
    def progress(i,total,name):
        if i==1:stop.set()
    cancelled=batch_convert(source,root/"cancelled",progress=progress,cancel=stop)
    assert cancelled["cancelled"] and cancelled["processed"]==2
    (pack/"models/entity/robot.geo.json").write_text(json.dumps({"minecraft:geometry":[{"description":{"identifier":"geometry.robot"},"bones":[]}]}))
    failure=batch_convert(ModelSource(pack),root/"failure")
    assert failure["failed"]==1 and failure["exported"]==2
print("Converter batch passed: reference/name matching, ambiguity, single-file discovery, textured 3D orbit, collisions, independent bundles, overrides, cancellation and failure isolation.")
