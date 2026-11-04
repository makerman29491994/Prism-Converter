"""Conversion fixtures exercise hierarchy, textures, archives and failure isolation."""
import base64, io, json, sys, tempfile, zipfile
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path("src").resolve()))
from PrismConverter import ModelSource, convert_model, json_data

assert json_data(b'{/* hi */"url":"https://example.org", "x":1// comment\n}')["x"]==1
with tempfile.TemporaryDirectory(dir="work",prefix="converter-check-") as tmp:
    root=Path(tmp);pack=root/"pack";pack.mkdir()
    image=Image.new("RGBA",(64,64),(0,0,0,0))
    for y in range(64):
        for x in range(64):image.putpixel((x,y),(x*4,y*4,100,255))
    image.save(pack/"robot.png")
    geometry={"description":{"identifier":"geometry.robot","texture_width":64,"texture_height":64},"bones":[
        {"name":"body","pivot":[2,12,0],"cubes":[{"origin":[-2,0,-2],"size":[4,12,4],"uv":[0,0]}]},
        {"name":"head","parent":"body","pivot":[2,12,0],"rotation":[10,20,30],"cubes":[{"origin":[-2,12,-2],"size":[4,4,4],"uv":[16,0]}]}]}
    (pack/"robot.geo.json").write_text(json.dumps({"minecraft:geometry":[geometry]}))
    source=ModelSource(pack);assert len(source.models)==1
    out=root/"converted";report=convert_model(source,0,out,"robot.png")
    result=json.loads((out/"converted.mimodel").read_text())
    assert report["cubes"]==2 and report["parts"]==2
    body=result["parts"][0];head=body["parts"][0]
    assert body["position"]==[2,12,0] and head["position"]==[0,0,0]
    assert head["rotation"]==[10,-20,-30]
    assert body["shapes"][0]["uv"]==[4,4]
    assert result["texture_size"]==[64,64], "Box texture was duplicated per cube"
    assert Image.open(out/"converted_texture.png").tobytes()==image.tobytes()
    before=(out/"converted.mimodel").read_bytes()
    try:convert_model(source,0,out,"robot.png")
    except FileExistsError:pass
    else:raise AssertionError("Existing export overwritten")
    assert (out/"converted.mimodel").read_bytes()==before
    archive=root/"pack.mcpack"
    with zipfile.ZipFile(archive,"w") as z:
        for f in pack.iterdir():z.write(f,f.name)
        z.writestr("../ignored.png",b"not an image")
    zipped=ModelSource(archive);assert "../ignored.png" not in zipped.files
    convert_model(zipped,0,root/"archive-export","robot.png")
    stream=io.BytesIO();image.save(stream,format="PNG")
    bb={"name":"Robot","meta":{"box_uv":True},"resolution":{"width":64,"height":64},
        "textures":[{"source":"data:image/png;base64,"+base64.b64encode(stream.getvalue()).decode()}],
        "elements":[{"uuid":"cube","from":[0,0,0],"to":[4,4,4],"origin":[2,2,2],"uv_offset":[0,0]}],
        "outliner":[{"uuid":"body","name":"body","origin":[2,2,2],"children":["cube"]}]}
    bbpath=pack/"robot.bbmodel";bbpath.write_text(json.dumps(bb))
    source=ModelSource(bbpath);assert len(source.models)==1
    convert_model(source,0,root/"bb-export")
    converted=json.loads((root/"bb-export/bb-export.mimodel").read_text())
    assert converted["parts"][0]["position"]==[-2,2,-2]
    assert converted["parts"][0]["shapes"][0]["position"]==[0,0,0]
    # Per-face UVs rebake the chosen texture region into a box atlas.
    bb["meta"]["box_uv"]=False
    bb["elements"][0]["faces"]={"north":{"uv":[8,8,12,12],"texture":0}}
    bbpath.write_text(json.dumps(bb));source=ModelSource(bbpath)
    convert_model(source,0,root/"face-export")
    texture=Image.open(root/"face-export/face-export_texture.png")
    assert texture.crop((4,4,8,8)).tobytes()==image.crop((8,8,12,12)).tobytes()
    assert texture.getpixel((0,0))[3]==0
    bb["elements"][0]["faces"]["north"]["uv"]=[8,8,24,24]
    bbpath.write_text(json.dumps(bb));source=ModelSource(bbpath)
    convert_model(source,0,root/"dense-face")
    dense=json.loads((root/"dense-face/dense-face.mimodel").read_text())
    assert dense["texture_scale"]==4
    assert Image.open(root/"dense-face/dense-face_texture.png").crop((16,16,32,32)).tobytes()==image.crop((8,8,24,24)).tobytes()
    # Modern Blockbench stores group properties separately from the outliner.
    bb["groups"]=[{k:v for k,v in bb["outliner"][0].items() if k!="children"}]
    bb["outliner"]=[{"uuid":"body","children":["cube"]}]
    bbpath.write_text(json.dumps(bb));source=ModelSource(bbpath)
    convert_model(source,0,root/"modern-bb")
    modern=json.loads((root/"modern-bb/modern-bb.mimodel").read_text())
    assert modern["parts"][0]["position"]==[-2,2,-2]
    # Never emit a partial bundle when a model cannot be represented.
    bb["elements"][0]["type"]="mesh";bbpath.write_text(json.dumps(bb))
    try:convert_model(ModelSource(bbpath),0,root/"bad")
    except ValueError:pass
    else:raise AssertionError("Mesh silently accepted")
    assert not (root/"bad").exists()
    geometry["bones"][0]["parent"]="head"
    (pack/"cycle.json").write_text(json.dumps({"minecraft:geometry":[geometry]}))
    try:convert_model(ModelSource(pack/"cycle.json"),0,root/"cycle","robot.png")
    except ValueError as exc:assert "cycle" in str(exc)
    else:raise AssertionError("Cyclic hierarchy accepted")
    named=root/"named-bundle"
    report=convert_model(ModelSource(pack/"robot.geo.json"),0,named,"robot.png",export_name="My Robot")
    model=json.loads((named/"My Robot.mimodel").read_text())
    assert model["name"]=="My Robot" and model["texture"]=="My Robot_texture.png"
    assert (named/model["texture"]).is_file() and report["model_file"]=="My Robot.mimodel"
    assert "My Robot.mimodel" in (named/"Read me.txt").read_text()
    for invalid in ("", "../outside", "CON", "bad:name", "trailing."):
        try:convert_model(source,0,root/"bad-name",export_name=invalid)
        except ValueError:pass
        else:raise AssertionError("Unsafe export name accepted")
        assert not (root/"bad-name").exists()
print("Converter passed: Bedrock and Blockbench transforms, hierarchy, embedded/selected textures, face UVs, archive input, cycles, unsupported meshes and overwrite protection.")
