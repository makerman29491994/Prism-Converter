"""Preview Bedrock indexed/list polygon meshes and Blockbench mesh elements.

Polygon data is never emitted into the cube-only .mimodel writer.
Bedrock data layout follows Microsoft's minecraft:geometry schema.
"""
import math
from PrismConverter import normalize_model,load_model_textures,build_model,vector
from PrismConverterPreview import preview_mesh,rotate,prepare_render_mesh


def model_has_polygons(record):
    data=record["data"]
    return any(b.get("poly_mesh") is not None for b in data.get("bones",[])) if record["kind"]=="bedrock" else any(e.get("type")=="mesh" for e in data.get("elements",[]))


def triangulate(points):
    """Ear clipping retains concave polygon outlines instead of filling the notch."""
    if len(points)==3:return [(0,1,2)]
    normal=[sum((points[i][(k+1)%3]-points[(i+1)%len(points)][(k+1)%3])*(points[i][(k+2)%3]+points[(i+1)%len(points)][(k+2)%3]) for i in range(len(points))) for k in range(3)]
    axis=max(range(3),key=lambda k:abs(normal[k]));axes=[k for k in range(3) if k!=axis]
    flat=[(p[axes[0]],p[axes[1]]) for p in points]
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    area=sum(flat[i][0]*flat[(i+1)%len(flat)][1]-flat[(i+1)%len(flat)][0]*flat[i][1] for i in range(len(flat)))
    if abs(area)<1e-10:return []
    sign=1 if area>0 else -1;remaining=list(range(len(points)));triangles=[]
    while len(remaining)>3:
        for j,index in enumerate(remaining):
            before,after=remaining[j-1],remaining[(j+1)%len(remaining)]
            a,b,c=flat[before],flat[index],flat[after]
            if cross(a,b,c)*sign<=1e-10:continue
            if any(all(cross(x,y,flat[k])*sign>=-1e-10 for x,y in ((a,b),(b,c),(c,a))) for k in remaining if k not in (before,index,after)):continue
            triangles.append((before,index,after));remaining.pop(j);break
        else:raise ValueError("Polygon is self-intersecting or has invalid vertex order.")
    triangles.append(tuple(remaining));return triangles


def source_triangles(record,groups,resolution,textures):
    ids={g.get("id",g["name"]):g for g in groups}
    if len(ids)!=len(groups):raise ValueError("Duplicate part identifiers in polygon model.")
    def world(point,group):
        visited=set()
        while group is not None:
            key=group.get("id",group["name"])
            if key in visited:raise ValueError("Polygon bone hierarchy contains a cycle.")
            visited.add(key);pivot=vector(group["pivot"])
            point=rotate(tuple(a-b for a,b in zip(point,pivot)),vector(group["rotation"]))
            point=tuple(a+b for a,b in zip(point,pivot))
            parent=group.get("parent")
            if parent is not None and parent not in ids:raise ValueError("Polygon model has a missing parent bone.")
            group=ids.get(parent)
        return point
    result=[]
    def polygon(points,uvs,texture,group,reverse=False):
        if len(points)<3 or len(points)!=len(uvs):raise ValueError("A polygon needs at least three vertices and UVs.")
        if reverse:points=list(reversed(points));uvs=list(reversed(uvs))
        points=[world(p,group) for p in points]
        for indices in triangulate(points):
            result.append((tuple(points[i] for i in indices),tuple(uvs[i] for i in indices),texture))
    for group in groups:
        poly=group.get("poly_mesh")
        if poly is not None:
            image=textures[0];positions=[vector(p) for p in poly.get("positions",[])];uvs=[vector(uv,2) for uv in poly.get("uvs",[])]
            normals=poly.get("normals",[])
            positions=[(-p[0],p[1],p[2]) for p in positions]
            if poly.get("normalized_uvs",False):uvs=[(u*image.width,v*image.height) for u,v in uvs]
            else:uvs=[(u*image.width/resolution[0],v*image.height/resolution[1]) for u,v in uvs]
            polys=poly.get("polys",[])
            if isinstance(polys,str):
                if polys not in ("tri_list","quad_list"):raise ValueError("Unknown Bedrock polygon list type.")
                count=3 if polys=="tri_list" else 4
                if len(positions)%count or len(uvs)!=len(positions):raise ValueError("Polygon list vertex/UV counts do not match.")
                polys=[[[i,i,i] for i in range(start,start+count)] for start in range(0,len(positions),count)]
            if not isinstance(polys,list):raise ValueError("Invalid polygon index data.")
            for face in polys:
                if not isinstance(face,list) or len(face) not in (3,4):raise ValueError("Bedrock polygons must have three or four vertices.")
                points=[];coords=[]
                for entry in face:
                    if not isinstance(entry,list) or len(entry)!=3 or any(not isinstance(i,(int,float)) or isinstance(i,bool) or not math.isfinite(i) or i<0 or int(i)!=i for i in entry):raise ValueError("Invalid polygon vertex indices.")
                    pi,ni,ui=map(int,entry)
                    if pi>=len(positions) or ui>=len(uvs) or (normals and ni>=len(normals)):raise ValueError("Polygon index is outside its vertex/UV/normal array.")
                    points.append(positions[pi]);coords.append(uvs[ui])
                polygon(points,coords,image,group,reverse=True)
        for mesh in group.get("bb_meshes",[]):
            positions={key:vector(p) for key,p in mesh.get("vertices",{}).items()}
            for face in mesh.get("faces",{}).values():
                tid=face.get("texture")
                if tid is None:continue
                if isinstance(tid,str):tid=int(tid.lstrip("#"))
                image=textures.get(tid)
                if image is None:raise ValueError(f"Polygon texture {tid} is missing.")
                points=[];uvs=[]
                for key in face.get("vertices",[]):
                    if key not in positions or key not in face.get("uv",{}):raise ValueError("Blockbench mesh face has a missing vertex or UV.")
                    point=rotate(positions[key],vector(mesh.get("rotation",[0,0,0])))
                    points.append(tuple(a+b for a,b in zip(point,vector(mesh.get("origin",[0,0,0])))))
                    u,v=vector(face["uv"][key],2);uvs.append((u*image.width/resolution[0],v*image.height/resolution[1]))
                polygon(points,uvs,image,group)
    if len(result)>100000:raise ValueError("Polygon preview is limited to 100,000 triangles.")
    return result


def triangle_mesh(triangles):
    """Subdivide textured triangles once, then reuse the existing orbit renderer."""
    mesh=[];budget=max(1,30000//max(1,len(triangles)))
    for points,uvs,image in triangles:
        a,b,c=points;ua,ub,uc=uvs
        area=abs((ub[0]-ua[0])*(uc[1]-ua[1])-(ub[1]-ua[1])*(uc[0]-ua[0]))/2
        steps=max(1,min(64,math.ceil(math.sqrt(min(area,budget)))))
        pixels=image.load();vertices=[];texels=[]
        def vertex(i,j):
            u,v=i/steps,j/steps
            return tuple(a[k]*(1-u-v)+b[k]*u+c[k]*v for k in range(3))
        def emit(keys):
            u=sum(i for i,j in keys)/(3*steps);v=sum(j for i,j in keys)/(3*steps)
            tx=ua[0]*(1-u-v)+ub[0]*u+uc[0]*v;ty=ua[1]*(1-u-v)+ub[1]*u+uc[1]*v
            # Permit an exact UV edge at width/height without wrapping it.
            px=min(image.width-1,math.floor(tx));py=min(image.height-1,math.floor(ty))
            if px<0 or py<0:return
            color=pixels[px,py]
            if not color[3]:return
            start=len(vertices);vertices.extend(vertex(i,j) for i,j in keys)
            texels.append(((start,start+1,start+2),color))
        for i in range(steps):
            for j in range(steps-i):
                emit(((i,j),(i+1,j),(i,j+1)))
                if i+j<steps-1:emit(((i+1,j),(i+1,j+1),(i,j+1)))
        if texels:mesh.append((points,tuple(vertices),tuple(texels)))
    return mesh


def prepare_source_preview(source,index,texture=None,texture_path=None):
    record=source.models[index]
    if not model_has_polygons(record):
        model,atlas,_=build_model(source,index,texture,texture_path)
        return preview_mesh(model,atlas)
    _,resolution,groups,_=normalize_model(record,allow_mesh=True)
    resolution=vector(resolution,2)
    if min(resolution)<=0:raise ValueError("Invalid polygon texture resolution.")
    textures=load_model_textures(source,index,texture,texture_path)
    triangles=source_triangles(record,groups,resolution,textures)
    mesh=triangle_mesh(triangles)
    if any(g["cubes"] for g in groups):
        model,atlas,_=build_model(source,index,texture,texture_path,allow_mesh=True)
        mesh.extend(preview_mesh(model,atlas,fit_model=False))
    points=[p for face in mesh for p in face[1]]
    if not points:raise ValueError("This polygon model has no visible textured faces.")
    low=[min(p[k] for p in points) for k in range(3)];high=[max(p[k] for p in points) for k in range(3)]
    center=[(a+b)/2 for a,b in zip(low,high)];diameter=math.sqrt(sum((b-a)**2 for a,b in zip(low,high))) or 1
    def fit(p):return ((p[0]-center[0])*29/diameter,(p[1]-center[1])*29/diameter+16,(p[2]-center[2])*29/diameter)
    return prepare_render_mesh(tuple((tuple(fit(p) for p in corners),tuple(fit(p) for p in vertices),texels) for corners,vertices,texels in mesh))
