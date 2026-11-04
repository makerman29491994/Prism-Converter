"""Bounded, cached textured preview of the exact model/atlas being exported."""
import math
from PrismSkinPack import box_uv, preview_model
from PIL import Image,ImageDraw


class RenderMesh(tuple):
    """Immutable preview geometry with reusable arrays for camera projection."""
    def __new__(cls,faces):
        import numpy as np
        mesh=super().__new__(cls,faces)
        vertices=[];corners=[];indices=[];owners=[];colors=[];counts=[]
        for face,(face_corners,points,texels) in enumerate(mesh):
            offset=len(vertices);vertices.extend(points);corners.append(face_corners)
            for polygon,color in texels:
                count=len(polygon)
                padded=list(polygon)+[polygon[-1]]*(4-count)
                indices.append([i+offset for i in padded]);owners.append(face);colors.append(color);counts.append(count)
        mesh.vertices=np.asarray(vertices,dtype=np.float64).reshape((-1,3))
        mesh.corners=np.asarray(corners,dtype=np.float64).reshape((-1,3,3))
        mesh.indices=np.asarray(indices,dtype=np.int32).reshape((-1,4))
        mesh.owners=np.asarray(owners,dtype=np.int32);mesh.colors=colors
        mesh.counts=np.asarray(counts,dtype=np.int8)
        for array in (mesh.vertices,mesh.corners,mesh.indices,mesh.owners,mesh.counts):array.setflags(write=False)
        return mesh


def prepare_render_mesh(mesh):
    return mesh if isinstance(mesh,RenderMesh) else RenderMesh(mesh)


def rotate(point,angles):
    x,y,z=point
    ax,ay,az=map(math.radians,angles)
    c,s=math.cos(ax),math.sin(ax);y,z=y*c-z*s,y*s+z*c
    c,s=math.cos(ay),math.sin(ay);x,z=x*c+z*s,z*c-x*s
    c,s=math.cos(az),math.sin(az);x,y=x*c-y*s,x*s+y*c
    return x,y,z


def preview_mesh(model,atlas,fit_model=True):
    faces=[];scale=model.get("texture_scale",1);pixels=atlas.load()
    def transform(point,chain):
        # Mesh UVs follow Blockbench's box layout; transforms are stored in MI space.
        point=(-point[0],point[1],-point[2])
        for item in chain:
            point=tuple(a*b for a,b in zip(point,item.get("scale",[1,1,1])))
            point=rotate(point,item.get("rotation",[0,0,0]))
            point=tuple(a+b for a,b in zip(point,item.get("position",[0,0,0])))
        return (-point[0],point[1],-point[2])
    def walk(parts,parents=()):
        for part in parts:
            chain=(part,)+parents
            for shape in part.get("shapes",[]):
                a,b=shape["from"],shape["to"]
                x,y,z=-b[0],a[1],-b[2];w,h,d=[q-p for p,q in zip(a,b)]
                u,v=shape["uv"];uv=box_uv(u-d,v-d,w,h,d,scale=scale)
                if shape.get("texture_mirror"):
                    uv["east"],uv["west"]=uv["west"],uv["east"]
                    for value in uv.values():
                        value["uv"][0]+=value["uv_size"][0];value["uv_size"][0]*=-1
                inflate=shape.get("inflate",0);x-=inflate;y-=inflate;z-=inflate;w+=2*inflate;h+=2*inflate;d+=2*inflate
                corners={"north":((x,y+h,z),(x+w,y+h,z),(x+w,y,z),(x,y,z)),"south":((x+w,y+h,z+d),(x,y+h,z+d),(x,y,z+d),(x+w,y,z+d)),"east":((x,y+h,z+d),(x,y+h,z),(x,y,z),(x,y,z+d)),"west":((x+w,y+h,z),(x+w,y+h,z+d),(x+w,y,z+d),(x+w,y,z)),"up":((x,y+h,z+d),(x+w,y+h,z+d),(x+w,y+h,z),(x,y+h,z)),"down":((x,y,z),(x+w,y,z),(x+w,y,z+d),(x,y,z+d))}
                for face,points in corners.items():
                    faces.append((tuple(transform(p,(shape,)+chain) for p in points),uv[face]))
            walk(part.get("parts",[]),chain)
    walk(model["parts"])
    points=[p for face,_ in faces for p in face]
    low=[min(p[k] for p in points) for k in range(3)];high=[max(p[k] for p in points) for k in range(3)]
    center=[(a+b)/2 for a,b in zip(low,high)]
    # Fit the bounding sphere, including when the model is viewed from above.
    diameter=math.sqrt(sum((b-a)**2 for a,b in zip(low,high))) or 1
    factor=29/diameter
    def fit(p):return ((p[0]-center[0])*factor,(p[1]-center[1])*factor+16,(p[2]-center[2])*factor) if fit_model else p
    area=sum(abs(v["uv_size"][0]*v["uv_size"][1]) for _,v in faces)
    density=min(1,math.sqrt(30000/max(1,area)))
    mesh=[]
    for corners,value in faces:
        u,v=value["uv"];du,dv=value["uv_size"]
        if not du or not dv:continue
        cols=max(1,math.ceil(abs(du)*density));rows=max(1,math.ceil(abs(dv)*density))
        vertices=[];indices={};texels=[]
        for iy in range(rows):
            for ix in range(cols):
                px=math.floor(u+(ix+.5)*du/cols);py=math.floor(v+(iy+.5)*dv/rows)
                if not (0<=px<atlas.width and 0<=py<atlas.height):continue
                color=pixels[px,py]
                if not color[3]:continue
                quad=[]
                for key in ((ix,iy),(ix+1,iy),(ix+1,iy+1),(ix,iy+1)):
                    if key not in indices:
                        fx,fy=key[0]/cols,key[1]/rows;a,b,c,d=corners
                        point=tuple(a[k]*(1-fx)*(1-fy)+b[k]*fx*(1-fy)+c[k]*fx*fy+d[k]*(1-fx)*fy for k in range(3))
                        indices[key]=len(vertices);vertices.append(fit(point))
                    quad.append(indices[key])
                texels.append((tuple(quad),color))
        if texels:mesh.append((tuple(fit(p) for p in corners[:3]),tuple(vertices),tuple(texels)))
    return prepare_render_mesh(mesh) if fit_model else tuple(mesh)


def ground_shadow_bounds(projected,size,pitch=14):
    """Keep the contact shadow against the visible model, regardless of shape."""
    if not len(projected) or math.sin(math.radians(pitch))<=1e-6:return None
    left=float(projected[...,0].min());right=float(projected[...,0].max())
    bottom=float(projected[...,1].max());center=(left+right)/2
    radius=max(5,(right-left)*.44)
    height=max(5,min(22,(right-left)*.09))
    gap=max(2,min(5,size[1]*.008))
    top=min(size[1]-height-2,bottom+gap)
    return (max(2,center-radius),top,min(size[0]-2,center+radius),top+height)


def render_preview(mesh,size,yaw,pitch,grounded=True):
    import numpy as np
    mesh=prepare_render_mesh(mesh)
    angle=math.radians(yaw);tilt=math.radians(pitch)
    ca,sa=math.cos(angle),math.sin(angle);ct,st=math.cos(tilt),math.sin(tilt)
    zoom=min(size[0]/35,size[1]/42)
    def project(points):
        x,y,z=points[...,0],points[...,1],points[...,2]
        xx=x*ca+z*sa;zz=z*ca-x*sa
        yy=(y-16)*ct+zz*st;depth=zz*ct-(y-16)*st
        return np.stack((size[0]/2+xx*zoom,size[1]*.48-yy*zoom,depth),axis=-1)
    def facing(points):
        a,b,c=points[...,0,:],points[...,1,:],points[...,2,:]
        return (b[...,0]-a[...,0])*(c[...,1]-a[...,1])-(b[...,1]-a[...,1])*(c[...,0]-a[...,0])
    visible=facing(project(mesh.corners))>=-1e-9
    ids=np.flatnonzero(visible[mesh.owners])
    projected=project(mesh.vertices)[mesh.indices[ids]]
    front=facing(projected)>0
    ids=ids[front];projected=projected[front]
    depth=projected[:,0,2]+projected[:,1,2]+projected[:,2,2]
    depth=np.where(mesh.counts[ids]==4,depth+projected[:,3,2],depth)/mesh.counts[ids]
    order=np.argsort(-depth,kind="stable")
    image=Image.new("RGB",size,"#252525");draw=ImageDraw.Draw(image,"RGBA")
    shadow=ground_shadow_bounds(projected,size,pitch) if grounded else (size[0]*.2,size[1]*.87,size[0]*.8,size[1]*.96)
    if shadow is not None:draw.ellipse(shadow,fill=(0,0,0,80) if grounded else (5,15,10,80))
    points=projected[order,:,:2].reshape((-1,8)).tolist()
    for polygon,index in zip(points,ids[order].tolist()):draw.polygon(polygon,fill=mesh.colors[index])
    return image
