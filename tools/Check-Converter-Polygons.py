"""Binding exports and textured indexed/list/Blockbench polygon previews."""
import base64,copy,io,json,sys,tempfile
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path("src").resolve()))
from PrismConverter import ModelSource,convert_model,normalize_model
from PrismPolygonPreview import prepare_source_preview,triangulate
from PrismConverterPreview import render_preview

with tempfile.TemporaryDirectory(dir="work",prefix="polygon-check-") as tmp:
    root=Path(tmp);image=Image.new("RGBA",(16,16),(230,50,80,255));image.save(root/"robot.png")
    poly={"normalized_uvs":True,"positions":[[-4,0,0],[4,0,0],[4,8,0],[-4,8,0]],
          "normals":[[0,0,-1]],"uvs":[[0,1],[1,1],[1,0],[0,0]],"polys":[[[0,0,0],[3,0,3],[2,0,2],[1,0,1]]]}
    data={"minecraft:geometry":[{"description":{"identifier":"geometry.robot","texture_width":16,"texture_height":16},
        "bones":[{"name":"root","pivot":[0,0,0],"binding":"q.item_slot_to_bone_name(c.item_slot)","poly_mesh":poly}]}]}
    path=root/"robot.geo.json"
    def save(value):path.write_text(json.dumps(value));return ModelSource(path)
    source=save(data);mesh=prepare_source_preview(source,0)
    assert mesh and all(len(texel[0])==3 for face in mesh for texel in face[2])
    views=[render_preview(mesh,(300,400),angle,14).tobytes() for angle in (0,30,180,210)]
    assert len(set(views))>=3,"Polygon orbit did not change the view"
    assert any((230,50,80) in set(render_preview(mesh,(300,400),angle,14).getdata()) for angle in (0,180)),"Polygon texture is missing"
    pixels=copy.deepcopy(data);pixels["minecraft:geometry"][0]["bones"][0]["poly_mesh"]["normalized_uvs"]=False
    pixels["minecraft:geometry"][0]["bones"][0]["poly_mesh"]["uvs"]=[[u*16,v*16] for u,v in poly["uvs"]]
    mesh_pixels=prepare_source_preview(save(pixels),0)
    assert render_preview(mesh,(300,400),180,14).tobytes()==render_preview(mesh_pixels,(300,400),180,14).tobytes()
    lists=copy.deepcopy(data);p=lists["minecraft:geometry"][0]["bones"][0]["poly_mesh"]
    p["polys"]="quad_list";p["normals"]=[[0,0,-1]]*4
    assert prepare_source_preview(save(lists),0)
    p["positions"]=p["positions"][:3];p["uvs"]=p["uvs"][:3];p["polys"]="tri_list"
    assert prepare_source_preview(save(lists),0)
    invalid=copy.deepcopy(data);invalid["minecraft:geometry"][0]["bones"][0]["poly_mesh"]["polys"][0][0][0]=-1
    try:prepare_source_preview(save(invalid),0)
    except ValueError:pass
    else:raise AssertionError("Negative polygon index accepted")
    source=save(data)
    try:convert_model(source,0,root/"invalid-export")
    except ValueError as exc:assert "preview" in str(exc)
    else:raise AssertionError("Polygon faces silently discarded during export")
    assert not (root/"invalid-export").exists()
    binding=copy.deepcopy(data);bone=binding["minecraft:geometry"][0]["bones"][0];bone.pop("poly_mesh")
    bone["cubes"]=[{"origin":[-2,0,-2],"size":[4,8,4],"uv":[0,0]}]
    source=save(binding);report=convert_model(source,0,root/"bound-export")
    assert report["cubes"]==1 and any("binding" in w for w in report["warnings"])
    assert prepare_source_preview(source,0)
    mixed=copy.deepcopy(binding);mixed["minecraft:geometry"][0]["bones"].append({"name":"panel","parent":"root","pivot":[0,4,0],"rotation":[0,40,20],"poly_mesh":poly})
    assert prepare_source_preview(save(mixed),0)
    stream=io.BytesIO();image.save(stream,format="PNG")
    bb={"name":"Concave mesh","resolution":{"width":16,"height":16},"textures":[{"source":"data:image/png;base64,"+base64.b64encode(stream.getvalue()).decode()}],
        "elements":[{"type":"mesh","uuid":"mesh","origin":[2,3,4],"rotation":[0,20,0],
        "vertices":{"a":[0,0,0],"b":[8,0,0],"c":[8,8,0],"d":[4,4,0],"e":[0,8,0]},
        "faces":{"face":{"vertices":["a","b","c","d","e"],"uv":{"a":[0,16],"b":[16,16],"c":[16,0],"d":[8,8],"e":[0,0]},"texture":0}}}],
        "outliner":[{"name":"root","uuid":"root","origin":[0,0,0],"rotation":[20,0,0],"children":["mesh"]}]}
    bbpath=root/"mesh.bbmodel";bbpath.write_text(json.dumps(bb))
    assert prepare_source_preview(ModelSource(bbpath),0)
    assert len(triangulate([(0,0,0),(8,0,0),(8,8,0),(4,4,0),(0,8,0)]))==3

print("Binding/polygon checks passed: standalone bound export, textured Bedrock indexed/list and Blockbench meshes, concave faces, mixed cubes/meshes, rotation and safe polygon export rejection.")
