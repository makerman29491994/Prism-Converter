"""Hand-drawn charcoal/grey workspace for model conversion."""
import os
import sys
import queue
import threading
import time
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image,ImageTk
from PrismConverter import ModelSource, normalize_model, convert_model, build_model, match_texture, batch_convert,validate_export_name
from PrismConverterPreview import preview_mesh, render_preview
from PrismPolygonPreview import prepare_source_preview,model_has_polygons

BG="#202020";CARD="#2d2d2d";INK="#eeeeee";MUTED="#bdbdbd";EDGE="#858585";ACCENT="#c4c4c4"


class DirtButton(tk.Canvas):
    def __init__(self,parent,text,command,width=160,primary=False):
        super().__init__(parent,width=width,height=42,bg=parent.cget("background"),highlightthickness=0,cursor="hand2",takefocus=True)
        self.text=text;self.command=command;self.primary=primary;self.enabled=True
        self.bind("<Configure>",self.draw);self.bind("<FocusIn>",self.draw);self.bind("<FocusOut>",self.draw)
        self.bind("<Button-1>",self.invoke);self.bind("<Return>",self.invoke);self.bind("<space>",self.invoke)
    def invoke(self,event=None):
        if self.enabled:self.focus_set();self.command()
    def draw(self,event=None):
        self.delete("all");w,h=self.winfo_width(),self.winfo_height()
        self.create_polygon(10,3,w*.45,4,w-10,3,w-3,10,w-4,h-10,w-10,h-3,10,h-4,3,h-10,4,10,fill=ACCENT if self.primary else "#414141",outline=INK if str(self.tk.call("focus"))==str(self) else EDGE,width=2,smooth=True)
        self.create_text(w/2,h/2,text=self.text,font=("Ink Free",13,"bold"),fill=(BG if self.primary else INK) if self.enabled else EDGE)


class Converter:
    def __init__(self,parent):
        self.parent=parent;self.source=None;self.output=None;self.busy=False;self.events=queue.Queue();self.alive=True
        self.texture_path=None
        self.export_names={};self.export_name=tk.StringVar(parent)
        self.export_name.trace_add("write",self.remember_name)
        self.selection_has_polygons=False
        self.overrides={};self.mesh=None;self.yaw=30;self.pitch=14;self.drag=None;self.render_job=None
        self._last_frame=0.;self._last_render_mesh=None;self._last_render_state=None
        self.preview_revision=0;self.preview_future=None;self.preview_events=queue.Queue()
        self.preview_worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix="PrismPreview")
        self.batch_cancel=threading.Event();self.batch_active=False
        parent.configure(background=BG)
        self.frame=tk.Frame(parent,bg=BG,padx=32,pady=24);self.frame.pack(fill="both",expand=True)
        head=tk.Canvas(self.frame,bg=BG,height=110,highlightthickness=0);head.pack(fill="x")
        resource_dir=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent))
        with Image.open(resource_dir/"Converter-logo.png") as source:
            logo=source.convert("RGBA")
        bounds=logo.getchannel("A").point(lambda a:255 if a>128 else 0).getbbox()
        if bounds:logo=logo.crop(bounds)
        logo.thumbnail((88,88),Image.Resampling.LANCZOS)
        self._header_logo=ImageTk.PhotoImage(logo,master=head)
        head.create_image(47,48,image=self._header_logo)
        head.create_text(100,32,text="Converter",anchor="w",font=("Ink Free",32,"bold"),fill=INK)
        head.create_text(102,76,text="From your pack to your next animation.",anchor="w",font=("Ink Free",15),fill=MUTED)
        head.create_line(102,99,180,96,260,100,354,97,fill=ACCENT,width=3,smooth=True)
        paper=tk.Canvas(self.frame,bg=BG,highlightthickness=0);paper.pack(fill="both",expand=True,pady=(6,12))
        card=tk.Frame(paper,bg=CARD,padx=24,pady=20);window=paper.create_window(12,12,window=card,anchor="nw")
        def draw(event=None):
            w,h=paper.winfo_width(),paper.winfo_height()
            paper.itemconfigure(window,width=max(1,w-24),height=max(1,h-24));paper.delete("outline")
            paper.create_polygon(18,5,w*.4,7,w-18,5,w-5,18,w-7,h-20,w-20,h-5,18,h-7,5,h-18,7,18,fill=CARD,outline=EDGE,width=2,smooth=True,tags="outline");paper.tag_lower("outline")
        paper.bind("<Configure>",draw)
        card.columnconfigure(0,weight=5,minsize=405);card.columnconfigure(1,weight=4,minsize=290);card.rowconfigure(7,weight=1)
        self.label(card,"1. Open your model or resource pack",0)
        actions=tk.Frame(card,bg=CARD);actions.grid(row=1,column=0,sticky="w",pady=(6,12))
        self.buttons=[DirtButton(actions,"Open model / ZIP…",self.open_file,190),DirtButton(actions,"Open pack folder…",self.open_folder,190)]
        for b in self.buttons:b.pack(side="left",padx=(0,10))
        self.path=tk.StringVar(value=".bbmodel · Bedrock geometry JSON · .mcpack · ZIP · pack folder")
        tk.Label(card,textvariable=self.path,bg=CARD,fg=MUTED,font=("Ink Free",12),wraplength=390,anchor="w",justify="left").grid(row=2,column=0,sticky="ew")
        self.label(card,"2. Choose a model",3,pady=(18,6))
        style=ttk.Style(parent)
        style.configure("Converter.TCombobox",fieldbackground=BG,foreground=INK,background="#414141",arrowcolor=ACCENT,padding=7,font=("Ink Free",12))
        style.map("Converter.TCombobox",fieldbackground=[("readonly",BG)],foreground=[("readonly",INK)])
        self.model=ttk.Combobox(card,state="readonly",style="Converter.TCombobox");self.model.grid(row=4,column=0,sticky="ew");self.model.bind("<<ComboboxSelected>>",self.select_model)
        self.label(card,"3. Choose the matching texture",5,pady=(18,6))
        texrow=tk.Frame(card,bg=CARD);texrow.grid(row=6,column=0,sticky="ew");texrow.columnconfigure(0,weight=1)
        self.texture=ttk.Combobox(texrow,state="readonly",style="Converter.TCombobox",width=16);self.texture.grid(row=0,column=0,sticky="ew",padx=(0,10));self.texture.bind("<<ComboboxSelected>>",self.texture_changed)
        for combo in (self.model,self.texture):
            combo.configure(postcommand=lambda c=combo:self.theme_popup(c))
        browse=DirtButton(texrow,"Choose PNG…",self.pick_texture,145);browse.grid(row=0,column=1);self.buttons.append(browse)
        info=tk.Frame(card,bg=CARD);info.grid(row=7,column=0,sticky="nsew",pady=(12,12))
        tk.Label(info,text="Export name",bg=CARD,fg=INK,font=("Ink Free",14,"bold"),anchor="w").pack(fill="x")
        self.name_entry=tk.Entry(info,textvariable=self.export_name,bg=BG,fg=INK,insertbackground=INK,selectbackground=ACCENT,selectforeground=BG,font=("Ink Free",13),relief="flat",highlightthickness=1,highlightbackground=EDGE)
        self.name_entry.pack(fill="x",ipady=5,pady=(4,8))
        self.details=tk.Text(info,height=4,width=30,bg=CARD,fg=MUTED,relief="flat",wrap="word",font=("Ink Free",12),highlightthickness=0,state="disabled")
        self.details.pack(fill="both",expand=True)
        viewer=tk.Frame(card,bg=CARD);viewer.grid(row=0,column=1,rowspan=8,sticky="nsew",padx=(18,0),pady=(0,12));viewer.columnconfigure(0,weight=1);viewer.rowconfigure(1,weight=1)
        tk.Label(viewer,text="Your model",bg=CARD,fg=INK,font=("Ink Free",17,"bold")).grid(row=0,column=0,pady=(0,10))
        self.canvas=tk.Canvas(viewer,bg="#252525",highlightthickness=1,highlightbackground=EDGE,width=280,height=340,cursor="hand2")
        self.canvas.grid(row=1,column=0,sticky="nsew")
        self.canvas.bind("<Configure>",lambda e:self.queue_render())
        self.canvas.bind("<ButtonPress-1>",self.begin_rotate);self.canvas.bind("<B1-Motion>",self.drag_rotate);self.canvas.bind("<ButtonRelease-1>",self.end_rotate)
        tk.Label(viewer,text="Drag to rotate in any direction",bg=CARD,fg=MUTED,font=("Ink Free",11)).grid(row=2,column=0,pady=(8,2))
        DirtButton(viewer,"Reset view",self.reset_view,130).grid(row=3,column=0)
        self.render()
        bottom=tk.Frame(card,bg=CARD);bottom.grid(row=8,column=0,columnspan=2,sticky="ew")
        self.open_button=DirtButton(bottom,"Open export folder",self.open_output,190);self.open_button.pack(side="left")
        self.convert_button=DirtButton(bottom,"Make my .mimodel…",self.convert,220,True);self.convert_button.pack(side="right")
        self.batch_button=DirtButton(bottom,"Export all models…",self.batch,205);self.batch_button.pack(side="right",padx=10)
        self.buttons.extend([self.open_button,self.convert_button])
        self.status=tk.StringVar(value="Bring your cubes. Keep your parts. Make them move.")
        tk.Label(self.frame,textvariable=self.status,bg=BG,fg=MUTED,font=("Ink Free",12),anchor="w",wraplength=850,justify="left").pack(fill="x")
        self.set_details("Exports a .mimodel with a PNG texture beside it. Bone/group hierarchy and pivots stay available for animation.\n\nBound and fractional-size cube models can be previewed and exported. Polygon meshes can be previewed only. Existing animations and Java block-model JSON are not converted.")
        parent.bind("<Destroy>",self.destroyed,add="+")
        self.poll_job=parent.after(60,self.poll)
    def label(self,parent,text,row,pady=0):
        tk.Label(parent,text=text,bg=CARD,fg=INK,font=("Ink Free",16,"bold"),anchor="w").grid(row=row,column=0,sticky="w",pady=pady)
    def remember_name(self,*args):
        if self.source and self.model.current()>=0:self.export_names[self.model.current()]=self.export_name.get()
    def theme_popup(self,combo):
        popup=combo.tk.call("ttk::combobox::PopdownWindow",str(combo))
        combo.tk.call(str(popup)+".f.l","configure","-background",BG,"-foreground",INK,"-selectbackground",ACCENT,"-selectforeground",BG)
    def set_details(self,text):
        self.details.configure(state="normal");self.details.delete("1.0","end");self.details.insert("1.0",text);self.details.configure(state="disabled")
    def run(self,work,done):
        if self.busy:return
        self.busy=True
        for b in self.buttons:b.enabled=False;b.draw()
        self.batch_button.enabled=self.batch_active;self.batch_button.draw()
        self.model.configure(state="disabled");self.texture.configure(state="disabled")
        def worker():
            try:self.events.put((done,work(),None))
            except Exception as exc:self.events.put((done,None,str(exc)))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        try:
            while True:
                done,result,error=self.events.get_nowait();self.busy=False
                for b in self.buttons:b.enabled=True;b.draw()
                self.batch_active=False;self.batch_button.text="Export all models…";self.batch_button.enabled=True;self.batch_button.draw()
                self.model.configure(state="readonly");self.texture.configure(state="readonly")
                if error:self.status.set("Couldn't finish. Your source files are unchanged.");messagebox.showerror("Converter",error,parent=self.parent)
                else:done(result)
        except queue.Empty:pass
        try:
            while True:
                revision,mesh,error=self.preview_events.get_nowait()
                if revision=="progress":
                    if self.batch_active:self.status.set(mesh)
                    continue
                if revision!=self.preview_revision:continue
                self.mesh=mesh;self.preview_note=error or "";self.queue_render()
        except queue.Empty:pass
        if not self.busy and self.source:
            allowed=not self.selection_has_polygons
            if self.convert_button.enabled!=allowed:self.convert_button.enabled=allowed;self.convert_button.draw()
        if self.alive:self.poll_job=self.parent.after(60,self.poll)
    def open_file(self):
        path=filedialog.askopenfilename(parent=self.parent,title="Open model or resource pack",filetypes=[("Models and packs","*.bbmodel *.json *.mcpack *.zip"),("All files","*.*")])
        if path:self.load(path)
    def open_folder(self):
        path=filedialog.askdirectory(parent=self.parent,title="Choose resource-pack folder")
        if path:self.load(path)
    def load(self,path):
        self.status.set("Finding models and textures…")
        self.run(lambda:ModelSource(path),self.loaded)
    def loaded(self,source):
        self.source=source;self.texture_path=None;self.overrides={};self.export_names={};self.path.set(str(source.path))
        self.model.configure(values=[m["label"] for m in source.models]);self.model.current(0)
        self.texture.configure(values=["Use embedded Blockbench textures"]+source.textures);self.texture.current(0)
        self.select_model();self.status.set(f"Found {len(source.models)} models and {len(source.textures)} textures. Preview one, or export all."+(f" {len(source.warnings)} files skipped." if source.warnings else ""))
    def select_model(self,event=None):
        if not self.source:return
        record=self.source.models[self.model.current()]
        default=Path(record["file"]).stem
        for suffix in (".geometry",".geo"):
            if default.endswith(suffix):default=default[:-len(suffix)]
        self.export_name.set(self.export_names.get(self.model.current(),default))
        self.selection_has_polygons=model_has_polygons(record)
        try:
            name,_,groups,warnings=normalize_model(record,allow_mesh=True)
            self.set_details(f"{name}\n{len(groups)} animation parts · {sum(len(g['cubes']) for g in groups)} cubes\n\nParts: "+", ".join(g["name"] for g in groups)+("\n\n"+"\n".join(warnings) if warnings else ""))
        except (ValueError,KeyError,TypeError) as exc:self.set_details(str(exc))
        if self.selection_has_polygons:
            self.set_details(self.details.get("1.0","end").strip()+"\n\nPolygon mesh preview. Cube and polygon parts are shown together. Polygon faces cannot be exported in .mimodel format.")
        self.convert_button.enabled=not self.selection_has_polygons;self.convert_button.draw()
        self.model_description=self.details.get("1.0","end").strip()
        index=self.model.current();match=match_texture(self.source,index)
        self.texture_path=None;self.texture.current(0)
        if index in self.overrides:
            texture,self.texture_path=self.overrides[index]
            self.texture.set(self.texture_path or texture or "Use embedded Blockbench textures")
        elif match["status"]=="matched":self.texture.set(match["texture"])
        elif match["status"]!="embedded":
            self.texture.set("Choose texture: "+match["status"])
            self.set_details(self.details.get("1.0","end").strip()+"\n\n"+("Multiple matching textures; choose a PNG." if match["status"]=="ambiguous" else "No matching texture. Choose a PNG or open the pack folder."))
        self.request_preview()
    def pick_texture(self):
        path=filedialog.askopenfilename(parent=self.parent,title="Choose the model's texture",filetypes=[("PNG texture","*.png")])
        if path:
            self.texture_path=path;self.texture.set(path)
            if self.source:self.overrides[self.model.current()]=(None,path);self.request_preview()
    def texture_changed(self,event=None):
        self.texture_path=None
        if self.source:
            choice=self.texture.get();self.overrides[self.model.current()]=(choice if choice in self.source.textures else None,None)
            self.request_preview()
    def request_preview(self):
        self.preview_revision+=1;revision=self.preview_revision
        self.mesh=None;self.preview_note="Preparing preview…";self.queue_render()
        if self.preview_future:self.preview_future.cancel()
        source=self.source;index=self.model.current();choice=self.texture.get()
        texture=choice if choice in source.textures else None;path=self.texture_path
        if path or texture:note="Texture: "+str(path or texture)
        else:
            match=match_texture(source,index)
            note="Blockbench textures" if match["status"]=="embedded" else "Multiple matching textures; choose a PNG." if match["status"]=="ambiguous" else "No matching texture. Choose a PNG or open the pack folder."
        self.set_details(getattr(self,"model_description","")+"\n\n"+note)
        def work():
            try:
                mesh=prepare_source_preview(source,index,texture,path)
                self.preview_events.put((revision,mesh,None))
            except Exception as exc:self.preview_events.put((revision,None,str(exc)))
        self.preview_future=self.preview_worker.submit(work)
    def queue_render(self):
        if self.render_job is None:
            delay=max(1,math.ceil((self._last_frame+1/30-time.perf_counter())*1000))
            self.render_job=self.parent.after(delay,self.render)
    def render(self):
        if self.render_job is not None:self.parent.after_cancel(self.render_job)
        self.render_job=None
        w,h=max(100,self.canvas.winfo_width()),max(100,self.canvas.winfo_height())
        state=(w,h,self.yaw,self.pitch,getattr(self,"preview_note",""))
        if self.mesh is self._last_render_mesh and state==self._last_render_state:return
        self._last_render_mesh=self.mesh;self._last_render_state=state;self._last_frame=time.perf_counter()
        self.canvas.delete("all")
        if not self.mesh:
            self.canvas.create_text(w/2,h/2,text=getattr(self,"preview_note","Open a model to see it here"),width=max(80,w-30),fill=MUTED,font=("Ink Free",13),justify="center")
            return
        image=render_preview(self.mesh,(w,h),self.yaw,self.pitch)
        self._preview_image=ImageTk.PhotoImage(image,master=self.canvas)
        self.canvas.create_image(w/2,h/2,image=self._preview_image)
    def begin_rotate(self,event):
        if self.mesh:self.drag=(event.x,event.y);self.canvas.configure(cursor="fleur")
    def drag_rotate(self,event):
        if self.drag is None:return
        if self.drag==(event.x,event.y):return
        x,y=self.drag;self.yaw=(self.yaw-(event.x-x)*.6)%360;self.pitch=(self.pitch+(event.y-y)*.6)%360
        self.drag=(event.x,event.y);self.queue_render()
    def end_rotate(self,event):
        self.drag=None;self.canvas.configure(cursor="hand2")
    def reset_view(self):
        self.yaw=30;self.pitch=14;self.queue_render()
    def batch(self):
        if self.batch_active:
            self.batch_cancel.set();self.status.set("Stopping after the current model…");return
        if not self.source:messagebox.showinfo("Open a folder first","Open a model folder or resource pack, then export all models.",parent=self.parent);return
        path=filedialog.asksaveasfilename(parent=self.parent,title="Name a NEW batch export folder",initialfile="Converted-Models",filetypes=[("Batch folder","*")])
        if not path:return
        source=self.source;overrides=dict(self.overrides);names=dict(self.export_names);self.batch_cancel.clear();self.batch_active=True
        self.batch_button.text="Cancel batch";self.status.set("Starting batch export…")
        def progress(index,total,name):self.preview_events.put(("progress",f"Exporting {index+1}/{total}: {name}",None))
        def done(report):
            self.output=Path(path)
            summary=f"{report['exported']} exported · {report['skipped']} need textures · {report['failed']} failed"
            if report["cancelled"]:summary+=" · cancelled"
            self.status.set(summary)
            self.set_details(summary+"\n\nEach exported model has its own folder, .mimodel and texture. See batch-report.json for all results.\n\n"+"\n".join(f"{r['model']}: {r.get('reason','')}" for r in report["models"] if r["status"]!="exported"))
            messagebox.showinfo("Batch export finished",summary+"\n\n"+path+"\nSee batch-report.json for details.",parent=self.parent)
        self.run(lambda:batch_convert(source,path,overrides,progress,self.batch_cancel,names_override=names),done)
    def convert(self):
        if not self.source:messagebox.showinfo("Open a model first","Choose a model file or resource pack to get started.",parent=self.parent);return
        if model_has_polygons(self.source.models[self.model.current()]):
            messagebox.showinfo("Polygon preview only","This model can be previewed, but arbitrary polygon faces cannot be stored in a .mimodel. Convert its mesh to cubes in Blockbench before exporting.",parent=self.parent);return
        try:name=validate_export_name(self.export_name.get())
        except ValueError as exc:messagebox.showerror("Choose a model name",str(exc),parent=self.parent);return
        path=filedialog.asksaveasfilename(parent=self.parent,title="Choose a NEW folder for "+name,initialfile=name,filetypes=[("Model bundle folder","*")])
        if not path:return
        source=self.source;index=self.model.current();choice=self.texture.get()
        texture=choice if choice in source.textures else None;texture_path=self.texture_path
        self.status.set("Building animation parts and texture atlas…")
        def done(report):
            self.output=Path(path);self.status.set(f"Ready! {report['parts']} parts and {report['cubes']} cubes exported.")
            self.set_details("Saved to "+path+f"\n\nImport {report['model_file']} in Mine-imator. Keep {report['texture_file']} beside it.\n\n"+"\n".join(report["warnings"]))
            messagebox.showinfo("Your model is ready",f"Saved {report['parts']} parts and {report['cubes']} cubes.\n\nImport {report['model_file']} in Mine-imator.\n{path}"+("\n\n"+"\n".join(report["warnings"]) if report["warnings"] else ""),parent=self.parent)
        self.run(lambda:convert_model(source,index,path,texture,texture_path,export_name=name),done)
    def open_output(self):
        if self.output and self.output.is_dir():os.startfile(self.output)
    def destroyed(self,event):
        if event.widget==self.parent:
            self.alive=False;self.parent.after_cancel(self.poll_job);self.batch_cancel.set()
            self.preview_worker.shutdown(wait=False,cancel_futures=True)
            if self.render_job is not None:self.parent.after_cancel(self.render_job)
