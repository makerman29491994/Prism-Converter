"""Camera-fit invariance, fast-render equivalence and redraw throttling."""
import copy,json,math,random,sys,time,tkinter as tk
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path("src").resolve()))
from PrismConverterPreview import preview_mesh,render_preview,prepare_render_mesh
from PrismSkinPack import preview_model
from PrismConverterUI import Converter

rng=random.Random(42);atlas=Image.new("RGBA",(128,128))
atlas.putdata([(rng.randrange(256),rng.randrange(256),rng.randrange(256),rng.choice((0,128,255))) for _ in range(128*128)])
model={"texture_scale":1,"parts":[{"position":[0,0,0],"rotation":[20,30,10],"shapes":[
    {"from":[x,-8,-8],"to":[x+12,8,8],"position":[0,0,0],"rotation":[0,25,0],"uv":[16,16]} for x in (-16,0,16)]}]}
mesh=preview_mesh(model,atlas)
huge=copy.deepcopy(model)
huge["texture_scale"]=.001
for part in huge["parts"]:
    part["position"]=[x*1000 for x in part["position"]]
    for shape in part["shapes"]:
        for key in ("from","to","position"):shape[key]=[x*1000 for x in shape[key]]
        shape["uv"]=[x*1000 for x in shape["uv"]]
large=preview_mesh(huge,atlas)
assert len(mesh)==len(large)
for left,right in zip(mesh,large):
    for a,b in zip(left[1],right[1]):assert max(abs(x-y) for x,y in zip(a,b))<1e-10
before=after=0.;frames=0
for size in ((300,400),(360,470)):
    for yaw in range(0,360,15):
        for pitch in (14,90,225):
            start=time.perf_counter();old=preview_model(None,None,size,yaw,pitch,mesh,background="#252525");before+=time.perf_counter()-start
            start=time.perf_counter();new=render_preview(mesh,size,yaw,pitch);after+=time.perf_counter()-start
            assert old.tobytes()==new.tobytes(),(size,yaw,pitch)
            frames+=1
            # Check all model vertices, not the decorative shadow/background.
            ca,sa=math.cos(math.radians(yaw)),math.sin(math.radians(yaw));ct,st=math.cos(math.radians(pitch)),math.sin(math.radians(pitch));zoom=min(size[0]/35,size[1]/42)
            for face in large:
                for x,y,z in face[0]:
                    xx=x*ca+z*sa;zz=z*ca-x*sa;yy=(y-16)*ct+zz*st
                    assert 0<size[0]/2+xx*zoom<size[0]
                    assert 0<size[1]*.48-yy*zoom<size[1]
# Triangle meshes use average depth for three vertices, including mixed alpha.
triangle=prepare_render_mesh([(((0,8,0),(8,8,0),(0,24,0)),((0,8,0),(8,8,0),(0,24,0)),(((0,1,2),(230,50,80,128)),))])
for yaw in (0,45,180):
    assert render_preview(triangle,(300,400),yaw,14).tobytes()==preview_model(None,None,(300,400),yaw,14,triangle,background="#252525").tobytes()
root=tk.Tk();root.geometry("1000x900");viewer=Converter(root)
try:
    root.update();viewer.mesh=mesh
    with patch("PrismConverterUI.render_preview",wraps=render_preview) as render:
        viewer.render();calls=render.call_count
        viewer.render();viewer.render()
        assert render.call_count==calls,"Unchanged camera redrew the model"
        saved_time=viewer._last_frame;viewer._last_frame=100
        with patch("PrismConverterUI.time.perf_counter",return_value=100.01),patch.object(root,"after",return_value="queued") as schedule:
            viewer.queue_render();viewer.queue_render()
            assert schedule.call_count==1 and schedule.call_args.args[0]==24,"Camera frame rate was not throttled to 30 FPS"
        viewer.render_job=None;viewer._last_frame=saved_time
        # Burst mouse motion queues one frame with the latest camera angle.
        viewer.drag=(50,50)
        for x in range(51,101):viewer.drag_rotate(type("Motion",(),{"x":x,"y":50})())
        assert viewer.render_job is not None
        deadline=time.monotonic()+.12
        while time.monotonic()<deadline:root.update();time.sleep(.002)
        assert render.call_count==calls+1,"Motion burst queued duplicate frames"
finally:root.destroy()
report={"identical_frames":frames,"before_seconds":before,"after_seconds":after,"speedup":before/after,"large_model_scale_test":1000}
Path("build/converter-camera-performance.json").write_text(json.dumps(report,indent=2))
print("Camera checks passed:",json.dumps(report))
