"""Small monochrome pencil marks around the existing native controls."""
import tkinter as tk


class SketchField(tk.Canvas):
    def __init__(self,parent,variant=0,height=44,background='#2d2d2d'):
        super().__init__(parent,height=height,width=100,bg=background,highlightthickness=0)
        self.variant=variant;self.control=None
        self.bind('<Configure>',self.draw)

    def attach(self,control):
        self.control=control
        self.window=self.create_window(7,6,window=control,anchor='nw')
        control.bind('<FocusIn>',self.draw,add='+');control.bind('<FocusOut>',self.draw,add='+')

    def draw(self,event=None):
        w,h=self.winfo_width(),self.winfo_height();self.delete('pencil')
        if self.control is not None:self.itemconfigure(self.window,width=max(1,w-14),height=max(1,h-12))
        paths=(
            (5,4,w*.38,3,w-9,5,w-3,10,w-5,h-5,w*.61,h-3,4,h-5,3,11),
            (7,3,w*.58,5,w-5,3,w-3,h-8,w-8,h-4,w*.33,h-5,3,h-3,4,8),
            (4,5,w*.28,3,w-6,4,w-4,h*.56,w-6,h-4,w*.66,h-3,5,h-5,3,12))
        # Native ttk dropdowns are Tcl windows, not registered Python widgets.
        focused=self.control is not None and str(self.tk.call('focus'))==str(self.control)
        self.create_polygon(*paths[self.variant%3],fill='',outline='#eeeeee' if focused else '#858585',width=1,tags='pencil')
        # One short overlapping stroke reads as pencil, rather than a second box.
        x=w*.28 if self.variant%2 else w*.64
        self.create_line(x,h-3,x+20,h-4,x+30,h-3,fill='#858585',width=1,tags='pencil')


def doodle(parent,kind,background='#2d2d2d'):
    c=tk.Canvas(parent,width=24,height=25,bg=background,highlightthickness=0)
    def line(*p,**kw):c.create_line(*p,fill=kw.pop('fill','#bdbdbd'),width=1.4,capstyle='round',joinstyle='round',**kw)
    if kind=='model':
        # Keep the faces empty; vary only the graphite shade of the edges.
        line(3,9,11,4,21,8,fill='#c4c4c4')
        line(3,9,4,18,12,23,fill='#858585')
        line(21,8,21,18,12,23,fill='#bdbdbd')
        line(3,9,13,14,12,23,fill='#a0a0a0')
        line(13,14,21,8,fill='#bdbdbd')
    elif kind=='texture':
        line(4,4,21,5,20,22,3,21,4,4)
        line(9,5,8,21);line(15,5,14,21);line(4,10,20,11);line(4,16,20,17)
        c.create_polygon(10,11,14,11,14,16,9,16,fill='#858585',outline='')
    elif kind=='name':
        line(4,20,6,14,17,3,21,7,10,18,4,20)
        line(7,14,11,18);line(15,6,18,9)
    return c


def field_label(parent,text,kind=None,size=16):
    row=tk.Frame(parent,bg='#2d2d2d')
    if kind:doodle(row,kind).pack(side='left',padx=(0,6))
    tk.Label(row,text=text,bg='#2d2d2d',fg='#eeeeee',font=('Ink Free',size,'bold'),anchor='w').pack(side='left')
    return row


def combobox_style(style,parent):
    """Replace only the arrow artwork, keeping ttk's native dropdown behavior."""
    from PIL import Image,ImageDraw,ImageTk
    root=parent
    while root.master is not None:root=root.master
    cache=getattr(root,'_converter_dropdown_art',None)
    if cache is None:cache={};root._converter_dropdown_art=cache
    theme=style.theme_use()
    if theme not in cache:
        images=[]
        for color in ('#bdbdbd','#eeeeee','#858585'):
            image=Image.new('RGBA',(36,36),'#202020');draw=ImageDraw.Draw(image)
            draw.line([(7,12),(17,23),(28,11)],fill=color,width=2)
            images.append(ImageTk.PhotoImage(image.resize((18,18),Image.Resampling.LANCZOS),master=root))
        element='ConverterSketch.Combobox.downarrow'
        style.element_create(element,'image',images[0],('disabled',images[2]),('active',images[1]),sticky='')
        # The native field paints a bevel in its pressed/focus states even
        # when the normal border is hidden. Use a plain field in every state.
        field='ConverterSketch.Combobox.field'
        images.append(ImageTk.PhotoImage(Image.new('RGBA',(1,1),'#202020'),master=root))
        style.element_create(field,'image',images[-1],border=0,sticky='nswe')
        def replace(layout):
            result=[]
            for name,options in layout:
                options=dict(options)
                if name.endswith('.downarrow'):
                    name=element
                    options['sticky']=''
                elif name.endswith('.field'):name=field
                if 'children' in options:options['children']=replace(options['children'])
                result.append((name,options))
            return result
        style.layout('Converter.TCombobox',replace(style.layout('TCombobox')))
        style.map('Converter.TCombobox',background=[('disabled','#202020'),('!disabled','#202020')])
        cache[theme]=images


def scrollbar_style(style,parent):
    """Draw ttk elements so native scrollbar dragging/keyboard behavior stays intact."""
    from PIL import Image,ImageDraw,ImageTk
    root=parent
    while root.master is not None:root=root.master
    cache=getattr(root,'_converter_scrollbar_art',None)
    if cache is None:cache={};root._converter_scrollbar_art=cache
    theme=style.theme_use()
    if theme not in cache:
        images={}
        def art(kind,active=False):
            size=(18,24) if kind=='thumb' else (12,12) if kind=='grip' else (18,18)
            image=Image.new('RGBA',(size[0]*2,size[1]*2),'#414141' if kind=='grip' else '#202020');draw=ImageDraw.Draw(image)
            stroke='#eeeeee' if active else '#858585'
            def line(points,fill=stroke):draw.line([(x*2,y*2) for x,y in points],fill=fill,width=2)
            if kind=='thumb':
                draw.polygon([(3*2,2*2),(15*2,3*2),(15*2,21*2),(3*2,22*2)],fill='#414141')
                # A plain center can tile at any length without repeating marks.
                line([(3,2),(15,3),(15,21),(3,22),(3,2)])
            elif kind=='grip':
                for y in (3,6,9):line([(3,y),(9,y-1)])
            elif kind=='trough':line([(9,0),(9,18)],'#414141')
            else:line([(4,11),(9,6),(14,12)])
            return image.resize(size,Image.Resampling.LANCZOS)
        for direction in ('Vertical','Horizontal'):
            prefix='ConverterSketch.'+direction+'.Scrollbar.'
            for part in ('trough','thumb','grip','uparrow','downarrow'):
                base='arrow' if part in ('uparrow','downarrow') else part
                normal=art(base);active=art(base,True)
                if part=='downarrow':normal=normal.rotate(180);active=active.rotate(180)
                if direction=='Horizontal':normal=normal.rotate(90,expand=True);active=active.rotate(90,expand=True)
                photo=ImageTk.PhotoImage(normal,master=root);hover=ImageTk.PhotoImage(active,master=root)
                images[direction+part]=(photo,hover)
                border=(4,7,4,7) if direction=='Vertical' and part=='thumb' else (7,4,7,4) if part=='thumb' else 3
                style.element_create(prefix+part,'image',photo,('active',hover),border=border,sticky='' if part=='grip' else 'nswe')
            style.layout('Converter.'+direction+'.TScrollbar',[(prefix+'trough',{'sticky':'nswe','children':[
                (prefix+'uparrow',{'side':'top' if direction=='Vertical' else 'left','sticky':'we' if direction=='Vertical' else 'ns'}),
                (prefix+'downarrow',{'side':'bottom' if direction=='Vertical' else 'right','sticky':'we' if direction=='Vertical' else 'ns'}),
                (prefix+'thumb',{'expand':1,'sticky':'nswe','children':[(prefix+'grip',{'sticky':''})]})]})])
        cache[theme]=images
