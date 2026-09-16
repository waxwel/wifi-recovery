"""Antialiased, DPI-sized nine-slice surfaces for native ttk widgets."""
from PIL import Image, ImageDraw, ImageTk


def install(root, style, scale):
    images=[]
    painters=[]
    def surface(name,fill,border=None,radius=12):
        # ttk tiles the centre instead of stretching it. Large opaque surfaces
        # avoid thousands of tiny alpha-blended blits on every tab exposure.
        size=round((256 if name in ('card','inset','metric') else 64)*scale)
        background='#edf2f9' if name in ('card','tab','selected','active') or 'Header' in name else '#ffffff'
        def paint(color):
            image=Image.new('RGBA',(size*3,size*3),color(background))
            draw=ImageDraw.Draw(image)
            primary=name.startswith(('Round.Accent.TButton','Round.HeaderAccent.TButton'))
            draw.rounded_rectangle((2,2,size*3-3,size*3-3),radius=radius*scale*3,
                                   fill=fill if primary else color(fill),outline=color(border) if border else None,width=max(1,round(scale*3)))
            return image.resize((size,size),Image.Resampling.LANCZOS).convert('RGB')
        photo=ImageTk.PhotoImage(paint(lambda c:c),master=root)
        painters.append((photo,paint))
        images.append(photo)
        return photo
    def element(name,normal,states=(),radius=12):
        style.element_create(name,'image',normal,*states,border=round((radius+2)*scale),padding=0,width=1,height=1,sticky='nsew')
    card=surface('card','#ffffff','#e4eaf4',18)
    element('Round.surface',card,radius=18)
    style.layout('Surface.TFrame',[('Round.surface',{'sticky':'nswe'})])
    style.configure('Surface.TFrame',background='#edf2f9')
    element('Round.inset',surface('inset','#f8faff','#e4eaf4',12))
    style.layout('Inset.TFrame',[('Round.inset',{'sticky':'nswe'})])
    element('Round.badge',surface('badge','#edf2fb',radius=12))
    style.layout('Badge.TLabel',[('Round.badge',{'sticky':'nswe','children':[('Label.padding',{'sticky':'nswe','children':[('Label.label',{'sticky':'nswe'})]})]})])
    style.configure('Badge.TLabel',padding=(round(14*scale),round(7*scale)),foreground='#3565db',font=('Microsoft YaHei UI',10,'bold'))
    # Omit the clam client/field elements that paint rectangular outer borders.
    style.layout('TNotebook',[])
    style.layout('Treeview',[('Treeview.treearea',{'sticky':'nswe'})])
    metric=surface('metric','#f2f6fc',radius=12)
    element('Round.metric',metric)
    style.layout('Metric.TFrame',[('Round.metric',{'sticky':'nswe'})])
    for key,normal,hover,pressed,disabled,fg in (
        ('TButton','#eef3fb','#e1eafb','#d3e0f7','#f3f5f9','#294463'),
        ('Accent.TButton','#3565db','#2855c5','#2048ac','#cbd6eb','#ffffff'),
        ('Header.TButton','#ffffff','#e1eafb','#d3e0f7','#f3f5f9','#294463'),
        ('HeaderAccent.TButton','#3565db','#2855c5','#2048ac','#cbd6eb','#ffffff')):
        name='Round.'+key
        element(name,surface(name,normal),[
            ('disabled',surface(name+'disabled',disabled)),
            ('pressed',surface(name+'pressed',pressed)),
            ('active',surface(name+'hover',hover)),
            ('focus',surface(name+'focus',normal,'#91acf1'))])
        style.layout(key,[(name,{'sticky':'nswe','children':[('Button.padding',{'sticky':'nswe','children':[('Button.label',{'sticky':'nswe'})]})]})])
        style.configure(key,foreground=fg)
        style.map(key,foreground=[('disabled','#8391a9')])
    field=surface('field','#f8faff','#dbe3f0',9)
    focused=surface('focused','#ffffff','#6689e8',9)
    disabled=surface('disabled','#f1f4f8','#e3e8f0',9)
    element('Round.field',field,[('disabled',disabled),('focus',focused)],radius=9)
    def replace(layout):
        result=[]
        for name,options in layout:
            options=dict(options)
            if name.endswith('.field'): name='Round.field'
            if 'children' in options: options['children']=replace(options['children'])
            result.append((name,options))
        return result
    for name in ('TEntry','TCombobox','TSpinbox'):
        style.layout(name,replace(style.layout(name)))
        style.configure(name,fieldbackground='#f8faff',background='#f8faff',bordercolor='#f8faff',lightcolor='#f8faff',darkcolor='#f8faff',arrowcolor='#6b7d91',arrowsize=round(14*scale))
        style.map(name,fieldbackground=[('readonly','#f8faff'),('focus','#ffffff')],
                  selectbackground=[('readonly','#f8faff'),('!focus','#f8faff')],selectforeground=[('readonly','#294463'),('!focus','#294463')])
    element('Round.tab',surface('tab','#edf2f9'),[('selected',surface('selected','#ffffff')),('active',surface('active','#e4ecfa'))])
    style.layout('TNotebook.Tab',[('Round.tab',{'sticky':'nswe','children':[('Notebook.padding',{'sticky':'nswe','children':[('Notebook.label',{'sticky':'nswe'})]})]})])
    style.configure('TNotebook',tabmargins=(0,0,0,round(9*scale)))
    style.map('TNotebook.Tab',expand=[('selected',(0,0,0,0)),('!selected',(0,0,0,0))],padding=[('selected',(round(23*scale),round(10*scale))),('!selected',(round(23*scale),round(10*scale)))])
    element('Round.mode',surface('mode','#f2f6fc'),[('selected',surface('modechosen','#e3ecff','#9bb5ef')),('active',surface('modehover','#eaf0fc')),('focus',surface('modefocus','#f2f6fc','#6689e8'))])
    style.layout('Mode.TRadiobutton',[('Round.mode',{'sticky':'nswe','children':[('Radiobutton.padding',{'sticky':'nswe','children':[('Radiobutton.label',{'sticky':'nswe'})]})]})])
    style.configure('Mode.TRadiobutton',padding=(round(13*scale),round(7*scale)),foreground='#596e88')
    style.map('Mode.TRadiobutton',foreground=[('selected','#2455bd'),('!selected','#596e88')])
    style.configure('Vertical.TScrollbar',background='#d3dfef',troughcolor='#f8faff',borderwidth=0,arrowsize=round(11*scale))
    thumb=surface('thumb','#c1cee2',radius=12)
    element('Round.thumb',thumb,[('active',surface('thumbactive','#96acd0',radius=12))])
    style.layout('Vertical.TScrollbar',[('Vertical.Scrollbar.trough',{'sticky':'ns','children':[('Round.thumb',{'sticky':'nswe'})]})])
    style.configure('Vertical.TScrollbar',width=round(9*scale),gripcount=0,relief='flat')
    root._rounded_images=images
    root._rounded_painters=painters
