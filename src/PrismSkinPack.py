"""Independent PNG-to-skin-pack builder. No account or Minecraft-file changes."""
from pathlib import Path
import io,json,math,uuid,zipfile
from PIL import Image,ImageDraw


def load_skin(path):
    with Image.open(path) as image:
        if image.format != "PNG" or image.size not in ((64,32),(64,64),(128,128)):
            raise ValueError("Choose a 64×64 or 128×128 skin PNG (64×32 classic skins also work).")
        skin=image.convert("RGBA")
    if skin.size == (64,32):
        original=skin
        skin=Image.new("RGBA",(64,64));skin.paste(original,(0,0))
        # Mirror the six right-limb UV faces into the modern left-limb slots.
        mappings=[((4,16,8,20),(20,48)),((8,16,12,20),(24,48)),((8,20,12,32),(16,52)),((4,20,8,32),(20,52)),((0,20,4,32),(24,52)),((12,20,16,32),(28,52)),((44,16,48,20),(36,48)),((48,16,52,20),(40,48)),((48,20,52,32),(32,52)),((44,20,48,32),(36,52)),((40,20,44,32),(40,52)),((52,20,56,32),(44,52))]
        for box,destination in mappings:
            skin.paste(original.crop(box).transpose(Image.Transpose.FLIP_LEFT_RIGHT),destination)
    return skin


def load_cape(path):
    if not path:
        return None
    with Image.open(path) as image:
        if image.format != "PNG" or image.width > 2048 or image.height > 2048 or image.width < 1 or image.height < 1:
            raise ValueError("Choose a cape PNG no larger than 2048×2048.")
        image=image.convert("RGBA")
    if image.width==image.height*2:
        return image.resize((64,32),Image.Resampling.NEAREST)
    # A plain picture becomes the front/back of a Minecraft-layout cape.
    layout=Image.new("RGBA",(64,32))
    panel=image.resize((10,16),Image.Resampling.LANCZOS)
    layout.paste(panel,(1,1));layout.paste(panel.transpose(Image.Transpose.FLIP_LEFT_RIGHT),(12,1))
    for x in (0,11):layout.paste(panel.crop((0,0,1,16)),(x,1))
    layout.paste(panel.crop((0,0,10,1)),(1,0));layout.paste(panel.crop((0,15,10,16)),(11,0))
    return layout


def box_uv(u,v,w,h,d,scale=1,offset=(0,0)):
    coords={"north":(u+d,v+d,w,h),"east":(u,v+d,d,h),"west":(u+d+w,v+d,d,h),"south":(u+2*d+w,v+d,w,h),"up":(u+d,v,w,d),"down":(u+d+w,v+d,w,-d)}
    return {face:{"uv":[a*scale+offset[0],b*scale+offset[1]],"uv_size":[c*scale,e*scale]} for face,(a,b,c,e) in coords.items()}


def prepare_model(skin,cape=None,slim=False,zombie=False,identifier="geometry.prism.custom"):
    scale=skin.width//64
    atlas=Image.new("RGBA",(skin.width*2,skin.height*2)) if cape is not None else skin.copy()
    if cape is not None:
        atlas.paste(skin,(0,0));atlas.paste(cape.resize((64*scale,32*scale),Image.Resampling.NEAREST),(0,64*scale))
    bones=[{"name":"root","pivot":[0,0,0]}]
    def part(name,origin,size,pivot,uv,overlay,parent="root",rotation=None):
        cube={"origin":origin,"size":size,"uv":box_uv(*uv,*size,scale=scale)}
        cubes=[cube]
        if overlay is not None:
            cubes.append({"origin":origin,"size":size,"inflate":.5 if name=="head" else .25,"uv":box_uv(*overlay,*size,scale=scale)})
        bone={"name":name,"parent":parent,"pivot":pivot,"cubes":cubes}
        if rotation:bone["rotation"]=rotation
        bones.append(bone)
    part("body",[-4,12,-2],[8,12,4],[0,24,0],(16,16),(16,32))
    part("head",[-4,24,-4],[8,8,8],[0,24,0],(0,0),(32,0))
    part("rightLeg",[-4,0,-2],[4,12,4],[-2,12,0],(0,16),(0,32))
    part("leftLeg",[0,0,-2],[4,12,4],[2,12,0],(16,48),(0,48))
    width=3 if slim else 4
    part("prism_right_arm" if zombie else "rightArm",[-7 if slim else -8,12,-2],[width,12,4],[-5,22,0],(40,16),(40,32),"body",[-90,0,0] if zombie else None)
    part("prism_left_arm" if zombie else "leftArm",[4,12,-2],[width,12,4],[5,22,0],(32,48),(48,48),"body",[-90,0,0] if zombie else None)
    if cape is not None:
        cape_uv=box_uv(0,0,10,16,1,scale=scale,offset=(0,64*scale))
        # Cape layouts put the outward artwork at (1,1); a body box puts
        # that panel on north, which faces the player's back here.
        cape_uv["north"],cape_uv["south"]=cape_uv["south"],cape_uv["north"]
        cape_uv["east"],cape_uv["west"]=cape_uv["west"],cape_uv["east"]
        bones.append({"name":"prism_cape","parent":"body","pivot":[0,24,2.5],"rotation":[8,0,0],"cubes":[{"origin":[-5,8,2.5],"size":[10,16,1],"uv":cape_uv}]})
    geometry={"description":{"identifier":identifier,"texture_width":atlas.width,"texture_height":atlas.height,"visible_bounds_width":4,"visible_bounds_height":4,"visible_bounds_offset":[0,1.5,0]},"bones":bones}
    return atlas,geometry


def prepare_preview_mesh(atlas,geometry):
    """Build immutable textured faces once; camera movement only projects them."""
    mesh=[];pixels=atlas.load()
    for bone in geometry["bones"]:
        pivot=bone.get("pivot",[0,0,0]);rotation=math.radians(-bone.get("rotation",[0,0,0])[0])
        cr,sr=math.cos(rotation),math.sin(rotation)
        def rotate(point):
            dy,dz=point[1]-pivot[1],point[2]-pivot[2]
            return (point[0],pivot[1]+dy*cr-dz*sr,pivot[2]+dy*sr+dz*cr)
        for cube in bone.get("cubes",[]):
            x,y,z=cube["origin"];w,h,d=cube["size"];inflate=cube.get("inflate",0)
            x-=inflate;y-=inflate;z-=inflate;w+=2*inflate;h+=2*inflate;d+=2*inflate
            faces={"north":((x,y+h,z),(x+w,y+h,z),(x+w,y,z),(x,y,z)),"south":((x+w,y+h,z+d),(x,y+h,z+d),(x,y,z+d),(x+w,y,z+d)),"east":((x,y+h,z+d),(x,y+h,z),(x,y,z),(x,y,z+d)),"west":((x+w,y+h,z),(x+w,y+h,z+d),(x+w,y,z+d),(x+w,y,z)),"up":((x,y+h,z+d),(x+w,y+h,z+d),(x+w,y+h,z),(x,y+h,z)),"down":((x,y,z),(x+w,y,z),(x+w,y,z+d),(x,y,z+d))}
            for face,corners in faces.items():
                uv=cube["uv"][face];u,v=uv["uv"];uw,vh=uv["uv_size"];cols,rows=int(abs(uw)),int(abs(vh))
                vertices=[];indices={};texels=[]
                for iy in range(rows):
                    for ix in range(cols):
                        px=int(u+ix if uw>0 else u-ix-1);py=int(v+iy if vh>0 else v-iy-1)
                        if not (0<=px<atlas.width and 0<=py<atlas.height):continue
                        color=pixels[px,py]
                        if color[3]==0:continue
                        quad=[]
                        for key in ((ix,iy),(ix+1,iy),(ix+1,iy+1),(ix,iy+1)):
                            if key not in indices:
                                fx,fy=key[0]/cols,key[1]/rows;a,b,c,e=corners
                                point=[a[k]*(1-fx)*(1-fy)+b[k]*fx*(1-fy)+c[k]*fx*fy+e[k]*(1-fx)*fy for k in range(3)]
                                indices[key]=len(vertices);vertices.append(rotate(point))
                            quad.append(indices[key])
                        texels.append((tuple(quad),color))
                if texels:mesh.append((tuple(rotate(p) for p in corners[:3]),tuple(vertices),tuple(texels)))
    return tuple(mesh)


def preview_model(atlas,geometry,size=(340,400),yaw=30,pitch=None,mesh=None,background="#17251f"):
    # Shared texel vertices avoid repeating model construction during an orbit.
    if mesh is None:mesh=prepare_preview_mesh(atlas,geometry)
    polygons=[];angle=math.radians(yaw);zoom=min(size[0]/35,size[1]/42)
    ca,sa=math.cos(angle),math.sin(angle)
    tilt=math.radians(pitch or 0);ct,st=math.cos(tilt),math.sin(tilt)
    def project(point):
        x,y,z=point;xx=x*ca+z*sa;zz=z*ca-x*sa
        if pitch is not None:
            yy=(y-16)*ct+zz*st;depth=zz*ct-(y-16)*st
            return (size[0]/2+xx*zoom,size[1]*.48-yy*zoom,depth)
        return (size[0]/2+xx*zoom,size[1]*.88-y*zoom-zz*zoom*.25,zz)
    for corners,vertices,texels in mesh:
        a,b,c=(project(p) for p in corners)
        if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]) < -1e-9:continue
        projected=[project(p) for p in vertices]
        for indices,color in texels:
            quad=[projected[i] for i in indices];a,b,c=quad[:3]
            if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])<=0:continue
            polygons.append((sum(p[2] for p in quad)/len(quad),[(p[0],p[1]) for p in quad],color))
    image=Image.new("RGB",size,background);draw=ImageDraw.Draw(image,"RGBA")
    for depth,points,color in sorted(polygons,key=lambda item:item[0],reverse=True):draw.polygon(points,fill=color)
    return image


def _png(image):
    stream=io.BytesIO();image.save(stream,format="PNG");return stream.getvalue()


def export_pack(skin_path,output,name="My Skin Pack",slim=False,zombie=False,cape_path=None,include_custom=False):
    return export_collection([{"skin_path":skin_path,"name":name,"slim":slim,"zombie":zombie,"cape_path":cape_path}],output,name,include_custom)


def export_collection(entries,output,name="My Skin Pack",include_custom=False):
    output=Path(output)
    if output.suffix.lower()!=".mcpack":raise ValueError("Save the pack with a .mcpack extension.")
    name=name.strip()
    if not name or len(name)>80 or any(c in name for c in "\r\n="):raise ValueError("Use a pack name of 1–80 characters without line breaks or =.")
    if not entries:raise ValueError("Add at least one skin to your pack.")
    token="prism_"+uuid.uuid4().hex
    manifest={"format_version":2,"header":{"name":name,"description":"Created with Prism Skin Studio","uuid":str(uuid.uuid4()),"version":[1,0,0]},"modules":[{"type":"skin_pack","uuid":str(uuid.uuid4()),"version":[1,0,0]}]}
    skins=[];enhanced=0;preview_only=0;files={"manifest.json":json.dumps(manifest,indent=2).encode()}
    language=[f"skinpack.{token}={name}",f"skinpack.{token}.by=Made with Prism"]
    for index,entry in enumerate(entries):
        skin=entry["skin"].copy() if "skin" in entry else load_skin(entry["skin_path"])
        cape=entry.get("cape") if "cape" in entry else load_cape(entry.get("cape_path"))
        slim=entry.get("slim",False);zombie=False
        skin_name=entry.get("name",f"Skin {index+1}").strip()
        if not skin_name or len(skin_name)>80 or any(c in skin_name for c in "\r\n="):
            raise ValueError("Give each skin a name of 1–80 characters without line breaks or =.")
        prefix="" if len(entries)==1 else f"skin_{index+1}_"
        normal=prefix+"normal"
        texture=prefix+"skin.png"
        definition={"localization_name":normal,"geometry":"geometry.humanoid.customSlim" if slim else "geometry.humanoid.custom","texture":texture,"type":"free"}
        skins.append(definition)
        files[texture]=_png(skin)
        language.append(f"skin.{token}.{normal}={skin_name}")
        if (zombie or cape is not None) and not include_custom:preview_only+=1
        atlas,geometry=prepare_model(skin,cape if include_custom else None,slim,zombie if include_custom else False)
        if index==0:files["pack_icon.png"]=_png(preview_model(atlas,geometry,(128,128)))
        if include_custom and (zombie or cape is not None):
            enhanced+=1
            # Native skin-pack fields keep the body texture at its original size.
            # A SkinMaster-style installation is required for cape/pose support.
            if cape is not None:
                definition["cape"]=prefix+"cape.png";files[definition["cape"]]=_png(cape)
            if zombie:definition["animations"]={"move.arms":"animation.player.move.arms.zombie"}
    if enhanced:
        files["README.txt"]=("Cape textures are included as separate PNGs referenced by each skin's cape field.\nOpening this .mcpack normally in Minecraft may import the body skin without displaying its cape.\nFor capes on Windows, use Skin Studio > Install skins, with Minecraft closed.\nYou can install the Studio collection or select this saved .mcpack in the direct installer.\nReopen Minecraft and select this pack under Classic Skins / Owned.\nA PNG skin image alone cannot contain a separate native cape.\n").encode()
    files["skins.json"]=json.dumps({"serialize_name":token,"localization_name":token,"skins":skins},indent=2).encode()
    files["texts/en_US.lang"]=("\n".join(language)+"\n").encode()
    files["texts/languages.json"]=b'["en_US"]'
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,"x",zipfile.ZIP_DEFLATED) as archive:
        for path,data in files.items():archive.writestr(path,data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:raise ValueError("The saved skin pack did not pass its file check.")
        saved=json.loads(archive.read("skins.json"))["skins"]
        cape_skins=sum("cape" in skin for skin in saved)
        for skin in saved:
            if "cape" not in skin:continue
            with Image.open(io.BytesIO(archive.read(skin["cape"]))) as image:
                if image.format!="PNG" or image.size!=(64,32):raise ValueError("A saved cape texture is missing or has invalid dimensions.")
    return {"path":str(output),"skins":len(entries),"variants":len(skins),"custom_geometry":False,"enhanced_skins":enhanced,"preview_only":preview_only,"cape_skins":cape_skins}
