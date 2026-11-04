"""Cube-model conversion to Mine-imator's documented Modelbench JSON format.

Format references (schema only; no third-party implementation bundled):
https://github.com/NimiSqrd/Modelbench
https://github.com/JannisX11/blockbench-plugins/blob/master/plugins/mimodel_format.js
"""
import base64
import io
import json
import math
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from PIL import Image


def json_data(raw):
    # Resource packs commonly contain JSON comments.
    text = raw.decode("utf-8-sig")
    text = re.sub(r'("(?:\\.|[^"\\])*" )|//[^\n]*|/\*.*?\*/',
                  lambda m: m[0] if m[1] else "", text, flags=re.S | re.X)
    return json.loads(text)


class ModelSource:
    def __init__(self, path):
        self.path = Path(path)
        self.files = {}
        self.models = []
        self.textures = []
        self.warnings = []
        self.texture_links = {}
        self.archive = None
        if self.path.is_file() and zipfile.is_zipfile(self.path):
            with zipfile.ZipFile(self.path) as archive:
                for info in archive.infolist():
                    name = PurePosixPath(info.filename.replace("\\", "/"))
                    if info.is_dir() or name.is_absolute() or ".." in name.parts:
                        continue
                    if info.file_size > 32 * 1024 * 1024:
                        continue
                    if name.suffix.lower() in (".json", ".bbmodel", ".png"):
                        if str(name) in self.files:
                            raise ValueError("Archive contains duplicate asset paths.")
                        self.files[str(name)] = info.filename
            self.archive = self.path
            selected = None
        else:
            selected = self.path if self.path.is_file() else None
            root = selected.parent if selected else self.path
            if selected:
                for ancestor in selected.parents:
                    if (ancestor / "manifest.json").is_file():
                        root = ancestor
                        break
                    if ancestor.name.lower() in ("models", "model"):
                        root = ancestor.parent
                        break
            for file in root.rglob("*"):
                if file.is_file() and file.suffix.lower() in (".json", ".bbmodel", ".png"):
                    self.files[file.relative_to(root).as_posix()] = file
            selected = selected.relative_to(root).as_posix() if selected else None
        if len(self.files) > 50000:
            raise ValueError("Choose a resource-pack folder rather than a whole drive.")
        if self.archive:
            with zipfile.ZipFile(self.archive) as archive:
                self._scan(selected, archive)
        else:
            self._scan(selected)
        if not self.models:
            raise ValueError("No Bedrock cube geometry or Blockbench .bbmodel files were found. Choose a model file or an unpacked/ZIP resource pack.")

    def _scan(self, selected, archive=None):
        for name in sorted(self.files):
            if name.lower().endswith(".png"):
                self.textures.append(name)
                continue
            try:
                data = json_data(archive.read(self.files[name]) if archive else self.read(name))
                if not isinstance(data, dict):
                    continue
                for entity_key in ("minecraft:client_entity", "minecraft:attachable"):
                    description=data.get(entity_key,{}).get("description",{})
                    geometries=description.get("geometry",{})
                    textures=description.get("textures",{})
                    if not isinstance(geometries,dict) or not isinstance(textures,dict):continue
                    prefix=re.split(r"(?:^|/)(?:entity|attachables)/",name,maxsplit=1)[0].rstrip("/")
                    if prefix==name:prefix=""
                    for alias,identifier in geometries.items():
                        choices=[textures[alias]] if alias in textures else [textures["default"]] if "default" in textures else list(textures.values())
                        for texture in choices:
                            if isinstance(texture,str) and isinstance(identifier,str):
                                asset=texture.replace("\\","/").removesuffix(".png")+".png"
                                self.texture_links.setdefault(identifier,set()).add(f"{prefix}/{asset}".lstrip("/"))
                if selected and name != selected:continue
                if name.lower().endswith(".bbmodel") and "elements" in data:
                    self.models.append({"label": name, "file": name, "kind": "bbmodel", "data": data})
                elif isinstance(data.get("minecraft:geometry"), list):
                    for geometry in data["minecraft:geometry"]:
                        identifier = geometry.get("description", {}).get("identifier", "geometry")
                        self.models.append({"label": f"{name} · {identifier}", "file": name, "kind": "bedrock", "data": geometry})
                else:
                    for key, geometry in data.items():
                        if key.startswith("geometry.") and isinstance(geometry, dict) and "bones" in geometry:
                            geometry = dict(geometry, description={"identifier": key,
                                "texture_width": geometry.get("texturewidth", 64),
                                "texture_height": geometry.get("textureheight", 64)})
                            self.models.append({"label": f"{name} · {key}", "file": name, "kind": "bedrock", "data": geometry})
            except (ValueError, OSError, KeyError, TypeError) as exc:
                self.warnings.append(f"Skipped {name}: {exc}")

    def read(self, name):
        if self.archive:
            with zipfile.ZipFile(self.archive) as archive:
                return archive.read(self.files[name])
        path = self.files[name]
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Asset exceeds 32 MiB.")
        return path.read_bytes()


def vector(value, count=3):
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError(f"Expected a {count}-number coordinate.")
    result = [float(x) for x in value]
    if not all(math.isfinite(x) and abs(x) <= 1000000 for x in result):
        raise ValueError("Model coordinates must be finite and within supported bounds.")
    return result


def space(value):
    x, y, z = vector(value)
    return [-x, y, -z]


def relative(value, pivot):
    return space([a-b for a, b in zip(vector(value), vector(pivot))])


def normalize_model(record, allow_mesh=False):
    """Return common groups/cubes with absolute source-space pivots."""
    data = record["data"]
    warnings = []
    if record["kind"] == "bedrock":
        description = data.get("description", {})
        resolution = [description.get("texture_width", 64), description.get("texture_height", 64)]
        groups = []
        for bone in data.get("bones", []):
            if bone.get("poly_mesh") is not None and not allow_mesh:
                raise ValueError("Polygon meshes can be previewed, but cannot be exported as cube-based .mimodel files.")
            if bone.get("binding"):
                warnings.append(f"{bone['name']}: Minecraft attachment binding is omitted; the standalone model keeps its parts and pivots.")
            group = {"name": bone["name"], "parent": bone.get("parent"),
                     "pivot": vector(bone.get("pivot", [0, 0, 0])),
                     "rotation": vector(bone.get("rotation", [0, 0, 0])), "cubes": [], "poly_mesh":bone.get("poly_mesh")}
            for cube in bone.get("cubes", []):
                origin = vector(cube["origin"]);size = vector(cube["size"])
                end = [a+b for a,b in zip(origin,size)]
                if any(x < 0 for x in size):
                    warnings.append(f"{bone['name']}: reversed cube bounds were normalized; check texture placement against the source model.")
                group["cubes"].append({"from": [min(a,b) for a,b in zip(origin,end)], "to": [max(a,b) for a,b in zip(origin,end)],
                    "pivot": cube.get("pivot", group["pivot"]), "rotation": cube.get("rotation", [0,0,0]),
                    "inflate": cube.get("inflate", bone.get("inflate", 0)),
                    "mirror": cube.get("mirror", bone.get("mirror", False)), "uv": cube.get("uv", [0,0])})
            groups.append(group)
        # Bedrock reflects X and negates X/Y Euler angles when loaded by Blockbench.
        for group in groups:
            group["pivot"][0] *= -1
            group["rotation"] = [-group["rotation"][0],-group["rotation"][1],group["rotation"][2]]
            for cube in group["cubes"]:
                old_from,old_to=cube["from"],cube["to"]
                cube["from"]=[-old_to[0],old_from[1],old_from[2]]
                cube["to"]=[-old_from[0],old_to[1],old_to[2]]
                # A default pivot already references the converted group pivot.
                if cube["pivot"] is not group["pivot"]:
                    cube["pivot"]=vector(cube["pivot"]);cube["pivot"][0]*=-1
                r=vector(cube["rotation"]);cube["rotation"]=[-r[0],-r[1],r[2]]
        return description.get("identifier", "Model"), resolution, groups, warnings
    if data.get("animations"):
        warnings.append("Existing Blockbench animations are not transferred. Animate the exported parts in Mine-imator.")
    resolution = data.get("resolution", {"width":64,"height":64})
    resolution = [resolution.get("width",64),resolution.get("height",64)]
    elements = {x["uuid"]:x for x in data.get("elements", [])}
    group_definitions = {x["uuid"]:x for x in data.get("groups", [])}
    groups = [];used=set()
    def element(key, group):
        if key not in elements or key in used:
            raise ValueError("Outliner has a missing or repeated element.")
        used.add(key);cube=elements[key]
        if cube.get("type", "cube") == "mesh" and allow_mesh:
            group.setdefault("bb_meshes",[]).append(cube)
            return
        if cube.get("type", "cube") != "cube":
            raise ValueError("Polygon meshes can be previewed, but cannot be exported as cube-based .mimodel files.")
        if cube.get("visibility") is False:
            warnings.append(f"Hidden cube included: {cube.get('name','cube')}")
        # Per-face Blockbench UVs and Bedrock UVs use different representations.
        uv = cube.get("uv_offset", [0,0])
        if not cube.get("box_uv", data.get("meta",{}).get("box_uv",False)):
            uv = {face:dict(value, bb=True) for face,value in cube.get("faces",{}).items()}
        start,end=vector(cube["from"]),vector(cube["to"])
        if any(b<a for a,b in zip(start,end)):
            warnings.append(f"{cube.get('name','cube')}: reversed cube bounds were normalized; check texture placement against the source model.")
        group["cubes"].append({"from":[min(a,b) for a,b in zip(start,end)], "to":[max(a,b) for a,b in zip(start,end)],
            "pivot":cube.get("origin",[0,0,0]), "rotation":cube.get("rotation",[0,0,0]),
            "inflate":cube.get("inflate",0), "mirror":cube.get("mirror_uv",False), "uv":uv})
    def walk(items, parent=None):
        loose = None
        for item in items:
            if isinstance(item,str):
                if loose is None:
                    if parent is not None:
                        loose=next(g for g in groups if g.get("id")==parent)
                    else:
                        loose={"name":f"cubes_{len(groups)+1}","parent":None,"pivot":[0,0,0],"rotation":[0,0,0],"cubes":[]}
                        groups.append(loose)
                element(item,loose)
            elif isinstance(item,dict):
                item=dict(group_definitions.get(item.get("uuid"),{}),**item)
                group={"name":item.get("name","Part"), "id":item.get("uuid",f"part_{len(groups)}"),
                    "parent":parent,"pivot":item.get("origin",[0,0,0]),"rotation":item.get("rotation",[0,0,0]),"cubes":[]}
                groups.append(group)
                walk(item.get("children",[]),group["id"])
            else:raise ValueError("Unsupported Blockbench outliner entry.")
    walk(data.get("outliner",[]))
    missing=[key for key in elements if key not in used]
    if missing:walk(missing)
    for i,g in enumerate(groups):g.setdefault("id",f"loose_{i}")
    return data.get("name",Path(record["file"]).stem), resolution, groups, warnings


def image_data(raw):
    with Image.open(io.BytesIO(raw)) as image:
        if image.format != "PNG" or max(image.size)>8192:
            raise ValueError("Choose a PNG texture no larger than 8192 pixels per side.")
        return image.convert("RGBA")


def texture_reference_candidates(source, references, model_file):
    """Resolve portable asset paths without following stale absolute local paths."""
    actual={p.casefold():p for p in source.textures}
    for reference in references:
        if not isinstance(reference,str) or not reference or reference.startswith("data:"):continue
        ref=reference.replace("\\","/").casefold()
        if ":" in ref and not re.match(r"^[a-z]:/",ref):
            namespace,asset=ref.split(":",1)
            ref=f"assets/{namespace}/textures/{asset.removeprefix('textures/')}"
        if not ref.endswith(".png"):ref+=".png"
        relative=(PurePosixPath(model_file).parent/ref).as_posix()
        # Normalize .. segments for lookup only; no filesystem access occurs here.
        import posixpath
        exact={actual[x] for x in (ref,posixpath.normpath(relative)) if x in actual}
        if exact:return sorted(exact)
        suffix=[p for p in source.textures if p.casefold().endswith("/"+ref.lstrip("/"))]
        if suffix:return sorted(suffix)
        # Saved Blockbench paths often point to another computer. Preserve the
        # longest matching trailing path before falling back to the basename.
        pieces=ref.split("/")
        for length in range(len(pieces)-1,0,-1):
            tail="/".join(pieces[-length:])
            found=[p for p in source.textures if p.casefold()==tail or p.casefold().endswith("/"+tail)]
            if found:return sorted(found)
    return []


def blockbench_texture_candidates(source,item,model_file):
    return texture_reference_candidates(source,
        [item.get(key) for key in ("relative_path","path","source","name")],model_file)


def texture_name_key(value):
    value=str(value).replace("\\","/").rsplit("/",1)[-1].casefold()
    value=re.sub(r"\.(?:json|png|bbmodel)$","",value)
    value=re.sub(r"^(?:(?:geometry|geo|model)[._ -])+","",value)
    value=re.sub(r"(?:[._ -](?:geometry|geo|model|texture|diffuse|albedo))+$","",value)
    return re.sub(r"[\W_]","",value)


def match_texture(source,index):
    """Prefer declared references, then complete normalized names; never guess variants."""
    record=source.models[index];data=record["data"]
    if record["kind"]=="bbmodel" and data.get("textures"):
        declared=data["textures"]
        if all(t.get("source","").startswith("data:image/png;base64,") or
               len(blockbench_texture_candidates(source,t,record["file"]))==1 for t in declared):
            return {"status":"embedded","texture":None,"candidates":[],"reason":"Blockbench textures"}
        # An unresolved multi-texture model must not silently use one PNG for all faces.
        if len(declared)>1:
            return {"status":"missing","texture":None,"candidates":[],"reason":"Some Blockbench textures are missing or ambiguous; open the whole pack folder."}
    identifier=data.get("description",{}).get("identifier","")
    linked=source.texture_links.get(identifier,set())
    actual={p.casefold():p for p in source.textures}
    candidates=sorted({actual[p.casefold()] for p in linked if p.casefold() in actual})
    # ZIPs can contain multiple packs sharing the same geometry identifier.
    parts=record["file"].split("/")
    model_at=next((i for i,p in enumerate(parts) if p.casefold() in ("models","model")),None)
    if model_at is not None:
        pack_prefix="/".join(parts[:model_at]).casefold()
        scoped=[p for p in candidates if p.casefold().startswith(pack_prefix+"/")] if pack_prefix else candidates
        if scoped:candidates=scoped
    reason="Resource-pack texture reference"
    if not candidates and record["kind"]=="bbmodel" and data.get("textures"):
        candidates=blockbench_texture_candidates(source,data["textures"][0],record["file"])
        reason="Blockbench texture reference"
    if not candidates:
        names={texture_name_key(record["file"]),texture_name_key(identifier),texture_name_key(data.get("name",""))}-{''}
        candidates=[p for p in source.textures if texture_name_key(p) in names]
        reason="Matching texture name"
    status="matched" if len(candidates)==1 else "ambiguous" if candidates else "missing"
    if status=="ambiguous":reason="Multiple matching textures; choose one manually"
    return {"status":status,"texture":candidates[0] if status=="matched" else None,
            "candidates":candidates,"reason":reason if candidates else "No matching texture found"}


def validate_export_name(value):
    name=str(value).strip()
    if name.lower().endswith(".mimodel"):name=name[:-8]
    if not name or len(name)>120 or name.endswith(("."," ")) or re.search(r'[<>:"/\\|?*\x00-\x1f]',name):
        raise ValueError("Use a model name of 1–120 characters without file-path characters or a trailing dot.")
    if name.split(".")[0].upper() in {"CON","PRN","AUX","NUL",*(f"COM{i}" for i in range(1,10)),*(f"LPT{i}" for i in range(1,10))}:
        raise ValueError("That name is reserved by Windows. Choose another model name.")
    return name


def batch_convert(source,output,overrides=None,progress=None,cancel=None,names_override=None):
    """Each model is independent; failures and unresolved matches stay in the report."""
    root=Path(output)
    root.mkdir(parents=True,exist_ok=False)
    results=[];names=set();overrides=overrides or {}
    for index,record in enumerate(source.models):
        if cancel is not None and cancel.is_set():break
        if progress:progress(index,len(source.models),record["label"])
        match=match_texture(source,index);entry={"model":record["label"]}
        choice=overrides.get(index)
        if not choice and match["status"] in ("missing","ambiguous"):
            entry.update(status="skipped",reason=match["reason"],candidates=match["candidates"])
        else:
            stem=re.sub(r"(?:\.(?:geometry|geo))?$","",Path(record["file"]).stem)
            identifier=record["data"].get("description",{}).get("identifier","")
            if sum(r["file"]==record["file"] for r in source.models)>1:stem+="_"+identifier.removeprefix("geometry.")
            stem=re.sub(r'[^\w.-]+',"_",stem).strip(". ")[:100] or "Model"
            if stem.split(".")[0].upper() in {"CON","PRN","AUX","NUL",*(f"COM{i}" for i in range(1,10)),*(f"LPT{i}" for i in range(1,10))}:stem="_"+stem
            try:stem=validate_export_name((names_override or {}).get(index,stem))
            except ValueError as exc:
                entry.update(status="failed",reason=str(exc));results.append(entry);continue
            name=stem;n=2
            while name.casefold() in names:
                suffix=f"_{n}";name=stem[:120-len(suffix)]+suffix;n+=1
            names.add(name)
            try:
                texture,path=choice if choice else (match["texture"],None)
                report=convert_model(source,index,root/name,texture,path,export_name=name)
                entry.update(status="exported",folder=name,model_file=report["model_file"],texture_file=report["texture_file"],texture=path or texture or "Blockbench textures",warnings=report["warnings"])
            except Exception as exc:entry.update(status="failed",reason=str(exc))
        results.append(entry)
    report={"total":len(source.models),"processed":len(results),"cancelled":len(results)<len(source.models),"models":results,
            "exported":sum(r["status"]=="exported" for r in results),"skipped":sum(r["status"]=="skipped" for r in results),"failed":sum(r["status"]=="failed" for r in results)}
    (root/"batch-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report


def load_model_textures(source,index,texture=None,texture_path=None):
    record=source.models[index];data=record["data"]
    if texture is None and texture_path is None:
        match=match_texture(source,index)
        if match["status"]=="matched":texture=match["texture"]
        elif record["kind"]!="bbmodel" and match["status"] in ("missing","ambiguous"):
            raise ValueError("Multiple possible textures; choose the correct PNG." if match["status"]=="ambiguous" else "No matching texture found. Choose a PNG or open the whole pack folder.")
    textures={}
    if texture_path:
        textures[0]=image_data(Path(texture_path).read_bytes())
    elif texture:
        textures[0]=image_data(source.read(texture))
    elif record["kind"]=="bbmodel":
        for i,item in enumerate(data.get("textures",[])):
            raw=item.get("source","")
            if raw.startswith("data:image/png;base64,"):
                textures[i]=image_data(base64.b64decode(raw.split(",",1)[1],validate=True))
            else:
                candidates=blockbench_texture_candidates(source,item,record["file"])
                if len(candidates)==1:textures[i]=image_data(source.read(candidates[0]))
    if not textures:
        raise ValueError("Choose the model's PNG texture. No embedded texture was found.")
    if 0 not in textures:textures[0]=next(iter(textures.values()))
    return textures


def build_model(source, index, texture=None, texture_path=None, allow_mesh=False):
    record=source.models[index];data=record["data"]
    name,resolution,groups,warnings=normalize_model(record,allow_mesh=allow_mesh)
    textures=load_model_textures(source,index,texture,texture_path)
    resolution=vector(resolution,2)
    if any(x<1 or x>8192 for x in resolution):raise ValueError("Invalid model texture resolution.")
    pixel_scale=max(1,math.ceil(max(max(im.width/resolution[0],im.height/resolution[1]) for im in textures.values())))
    for group in groups:
        for cube in group["cubes"]:
            if not isinstance(cube["uv"],dict):continue
            w,h,d=[b-a for a,b in zip(vector(cube["from"]),vector(cube["to"]))]
            if any(abs(x-round(x))>1e-6 for x in (w,h,d)):continue
            for face,uv in cube["uv"].items():
                if not isinstance(uv,dict):continue
                fw,fh=(w,d) if face in ("up","down") else (d,h) if face in ("east","west") else (w,h)
                coords=uv.get("uv",[])
                if uv.get("bb") and len(coords)==4:
                    du,dv=abs(coords[2]-coords[0]),abs(coords[3]-coords[1])
                else:du,dv=map(abs,uv.get("uv_size",[fw,fh]))
                if uv.get("rotation",uv.get("uv_rotation",0)) in (90,270):du,dv=dv,du
                image_scale=max(im.width/resolution[0] for im in textures.values())
                pixel_scale=max(pixel_scale,math.ceil(max(du/fw if fw else 1,dv/fh if fh else 1)*image_scale))
    if pixel_scale>16:raise ValueError("Texture density exceeds 16 pixels per model unit. Reduce UV density in Blockbench.")
    # A single square texture atlas avoids external texture references per part.
    patches=[];cube_count=0;parts=[];box_texture=None
    ids={g.get("id",g["name"]):g for g in groups}
    if len(ids)!=len(groups):raise ValueError("Duplicate bone identifiers prevent preserving hierarchy.")
    emitted={};visiting=set();used_names=set()
    def emit(key):
        if key in visiting:raise ValueError("Model bone hierarchy contains a cycle.")
        if key in emitted:return emitted[key]
        visiting.add(key);g=ids[key];parent=g.get("parent")
        if parent is not None and parent not in ids:raise ValueError(f"Missing parent bone: {parent}")
        parent_group=ids[parent] if parent else None
        destination=emit(parent).setdefault("parts",[]) if parent else parts
        label=g["name"] or "Part";base=label;n=2
        while label in used_names:label=f"{base}_{n}";n+=1
        used_names.add(label)
        part={"name":label,"position":relative(g["pivot"],parent_group["pivot"] if parent_group else [0,0,0]),"rotation":space(g["rotation"]),"shapes":[]}
        emitted[key]=part;destination.append(part);visiting.remove(key)
        return part
    for key in ids:emit(key)
    for key,g in ids.items():
        for cube in g["cubes"]:
            size=[b-a for a,b in zip(vector(cube["from"]),vector(cube["to"]))]
            if any(x<0 or x>4096 for x in size):raise ValueError("Cube dimensions must be between 0 and 4096.")
            # Per-face UVs are rebaked onto a standard box layout.
            uv=cube["uv"];w,h,d=size
            shape_scale=None
            if isinstance(uv,dict):
                if any(abs(x-round(x))>1e-6 for x in size):
                    # Integer texture-space dimensions with an independent scale
                    # preserve arbitrary physical dimensions without rounding them.
                    inflate=float(cube["inflate"])
                    physical=[x+2*inflate for x in size]
                    if not math.isfinite(inflate) or any(x<0 for x in physical):raise ValueError("Cube inflation produces invalid bounds.")
                    dimensions=[max(1,math.ceil(x)) if x else 0 for x in physical]
                    for face,face_uv in uv.items():
                        if not isinstance(face_uv,dict):continue
                        axes=(0,2) if face in ("up","down") else (2,1) if face in ("east","west") else (0,1)
                        coords=face_uv.get("uv",[])
                        if face_uv.get("bb"):
                            if face_uv.get("texture") is None:continue
                            u0,v0,u1,v1=vector(coords,4);du,dv=abs(u1-u0),abs(v1-v0)
                        else:du,dv=map(abs,vector(face_uv.get("uv_size",[size[axes[0]],size[axes[1]]]),2))
                        if face_uv.get("rotation",face_uv.get("uv_rotation",0)) in (90,270):du,dv=dv,du
                        for axis,extent in zip(axes,(du,dv)):
                            if physical[axis]:dimensions[axis]=max(dimensions[axis],math.ceil(extent))
                    shape_scale=[physical[i]/dimensions[i] if dimensions[i] else 1 for i in range(3)]
                    w,h,d=dimensions
                else:w,h,d=map(round,size)
                if 2*(w+d)*pixel_scale>8192 or (h+d)*pixel_scale>8192:raise ValueError("Cube texture layout exceeds 8192 pixels.")
                patch=Image.new("RGBA",(max(1,2*(w+d)*pixel_scale),max(1,(h+d)*pixel_scale)))
                slots={"east":(0,d,d,h),"north":(d,d,w,h),"west":(d+w,d,d,h),"south":(2*d+w,d,w,h),"up":(d,0,w,d),"down":(d+w,0,w,d)}
                for face,(x,y,fw,fh) in slots.items():
                    face_uv=uv.get(face)
                    if not face_uv or not fw or not fh:continue
                    if face_uv.get("bb"):
                        if face_uv.get("texture") is None:continue
                        tid=face_uv.get("texture",0)
                        if isinstance(tid,str):tid=int(tid.lstrip("#"))
                        image=textures.get(tid)
                        if image is None:raise ValueError(f"Missing embedded texture {tid}; supply the model's textures.")
                        u,v,u2,v2=vector(face_uv["uv"],4)
                        sx,sy=image.width/resolution[0],image.height/resolution[1]
                        u,u2=u*sx,u2*sx;v,v2=v*sy,v2*sy
                    else:
                        image=textures[0];u,v=vector(face_uv["uv"],2)
                        default_size=[size[0],size[2]] if face in ("up","down") else [size[2],size[1]] if face in ("east","west") else [size[0],size[1]]
                        du,dv=vector(face_uv.get("uv_size",default_size),2);u2,v2=u+du,v+dv
                        if face in ("up","down"):u,u2,v,v2=u2,u,v2,v
                        sx,sy=image.width/resolution[0],image.height/resolution[1]
                        u,u2,v,v2=u*sx,u2*sx,v*sy,v2*sy
                    angle=face_uv.get("rotation",face_uv.get("uv_rotation",0))
                    if angle not in (0,90,180,270):raise ValueError("Only quarter-turn UV rotations are supported.")
                    sample_size=(fh*pixel_scale,fw*pixel_scale) if angle in (90,270) else (fw*pixel_scale,fh*pixel_scale)
                    # Sample continuous UV bounds directly, including subpixel
                    # rectangles and reversals; cropping would round their edges.
                    tile=image.transform(sample_size,Image.Transform.EXTENT,(u,v,u2,v2),Image.Resampling.NEAREST)
                    if angle:tile=tile.rotate(-angle,expand=True)
                    if face=="down":tile=tile.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                    patch.paste(tile,(x*pixel_scale,y*pixel_scale))
                offset=[d,d]
            else:
                if len(textures)>1:raise ValueError("Multiple textures with Box UV need a single texture atlas from Blockbench.")
                patch=box_texture if box_texture is not None else textures[0]
                # Preserve fractional Box UV dimensions without rebaking.
                target_size=tuple(int(x*pixel_scale) for x in resolution)
                if patch.size!=target_size:
                    if max(resolution)>8192 or min(resolution)<1:raise ValueError("Invalid texture resolution.")
                    patch=patch.resize(target_size,Image.Resampling.NEAREST)
                box_texture=patch
                u,v=vector(uv,2);offset=[u+d,v+d]
            pivot=cube["pivot"];a=relative(cube["from"],pivot);b=relative(cube["to"],pivot)
            shape={"type":"block","from":[min(x,y) for x,y in zip(a,b)],"to":[max(x,y) for x,y in zip(a,b)],
                "position":relative(pivot,g["pivot"]),"rotation":space(cube["rotation"]),"uv":offset,
                "inflate":float(cube["inflate"])}
            if shape_scale is not None:
                # Bake inflation into the physical bounds before scaling. This
                # keeps uniform source inflation exact under anisotropic scales.
                inflate=shape["inflate"]
                shape["from"]=[(x-inflate)/s for x,s in zip(shape["from"],shape_scale)]
                shape["to"]=[(x+inflate)/s for x,s in zip(shape["to"],shape_scale)]
                shape["scale"]=shape_scale;shape["inflate"]=0
            if not math.isfinite(shape["inflate"]):raise ValueError("Invalid cube inflation.")
            if cube["mirror"]:shape["texture_mirror"]=True
            emitted[key]["shapes"].append(shape);patches.append((patch,shape));cube_count+=1
    if not cube_count:raise ValueError("The selected model has no cubes.")
    # Reuse identical image objects (Box UV models share one PNG).
    unique={id(p):p for p,_ in patches}
    area=sum(p.width*p.height for p in unique.values())
    width=1
    while width<max(max(p.width for p in unique.values()),math.ceil(math.sqrt(area))):width*=2
    offsets={};x=y=row_height=0
    for patch,shape in patches:
        if id(patch) not in offsets:
            if x+patch.width>width:x=0;y+=row_height;row_height=0
            offsets[id(patch)]=(x,y);x+=patch.width;row_height=max(row_height,patch.height)
        ox,oy=offsets[id(patch)]
        shape["uv"][0]+=ox/pixel_scale;shape["uv"][1]+=oy/pixel_scale
    height=y+row_height
    side=1
    while side<max(width,height):side*=2
    if side>8192:raise ValueError("Converted texture atlas exceeds 8192 pixels. Split the model into smaller exports.")
    atlas=Image.new("RGBA",(side,side));done=set()
    for patch,_ in patches:
        if id(patch) not in done:atlas.paste(patch,offsets[id(patch)]);done.add(id(patch))
    model={"name":name,"texture":"texture.png","texture_size":[side/pixel_scale,side/pixel_scale],"texture_scale":pixel_scale,"floor_box_uvs":False,"parts":parts}
    report={"model":name,"parts":len(groups),"cubes":cube_count,"warnings":warnings,
            "source":str(source.path),"geometry":record["label"]}
    return model,atlas,report


def convert_model(source,index,output,texture=None,texture_path=None,export_name=None):
    output=Path(output)
    name=validate_export_name(output.name if export_name is None else export_name)
    model,atlas,report=build_model(source,index,texture,texture_path)
    model_file=name+".mimodel";texture_file=name+"_texture.png"
    model["name"]=name;model["texture"]=texture_file
    report.update(model=name,model_file=model_file,texture_file=texture_file)
    warnings=report["warnings"]
    output=Path(output)
    if output.exists():raise FileExistsError("Choose a new output folder; existing files will not be overwritten.")
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix=".prism-converter-",dir=output.parent))
    try:
        (temporary/model_file).write_text(json.dumps(model,indent=2,allow_nan=False),encoding="utf-8")
        atlas.save(temporary/texture_file)
        (temporary/"conversion.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        (temporary/"Read me.txt").write_text(f"In Mine-imator, import {model_file} as a custom model. Keep {texture_file} beside it.\nParts retain the source hierarchy and pivots for animation.\n"+"\n".join(warnings),encoding="utf-8")
        if temporary.parent.resolve()!=output.parent.resolve() or not temporary.name.startswith(".prism-converter-"):
            raise ValueError("Invalid export staging directory.")
        for attempt in range(5):
            if output.exists():raise FileExistsError("Output folder already exists; nothing was overwritten.")
            try:
                temporary.rename(output)
                break
            except PermissionError as exc:
                if getattr(exc,"winerror",None) not in (5,32,33) or attempt==4:raise
                time.sleep(.05*2**attempt)
    finally:
        if temporary.exists():shutil.rmtree(temporary)
    return report
