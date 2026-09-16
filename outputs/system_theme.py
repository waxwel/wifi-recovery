"""Follow the Windows application colour preference without changing settings."""
import ctypes
import winreg
import tkinter as tk
from tkinter import ttk

DARK={
 'black':'#e5edf8','#000000':'#e5edf8',
 'white':'#202938','#ffffff':'#202938','#edf2f9':'#141b26','#f1f5f9':'#141b26',
 '#15283f':'#e5edf8','#6b7d91':'#a6b5cb','#3565db':'#86aaff','#2563eb':'#86aaff',
 '#087f64':'#63d6b0','#aa6908':'#efbd6e','#c33e4f':'#ff8c9b','#e4ebf2':'#354257',
 '#e4eaf4':'#354257','#f2f6fc':'#29364a','#edf2fb':'#2c3e60','#e5f5ef':'#24483f',
 '#f8faff':'#192330','#dbe3f0':'#42536d','#6689e8':'#94b4ff','#f1f4f8':'#242c39',
 '#e3e8f0':'#394759','#eef3fb':'#30415a','#e1eafb':'#3b5274','#d3e0f7':'#445f86',
 '#f3f5f9':'#293241','#294463':'#dce8fa','#2855c5':'#4672d7','#2048ac':'#3962bd',
 '#cbd6eb':'#3d4c64','#8391a9':'#99a7be','#91acf1':'#b0c6ff','#e4ecfa':'#2d3f58',
 '#d3dfef':'#485b76','#c1cee2':'#566b89','#96acd0':'#7e9dc8','#e3ecff':'#304970',
 '#9bb5ef':'#718fc1','#eaf0fc':'#31445f','#596e88':'#b2c3dc','#2455bd':'#b2cdff',
 '#f7f9fc':'#263246','#e8efff':'#354f78','#f2faf6':'#213d35','#fff4f5':'#472d36',
 '#f8fafc':'#233043','#e5edff':'#354f78','#eaf0f8':'#354966','#f8fafc':'#233043',
}

def prefers_dark():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            return winreg.QueryValueEx(key,'AppsUseLightTheme')[0]==0
    except OSError:
        return False

def start(app, ui):
    root=app.root; style=ttk.Style(root)
    names=['.','TFrame','Card.TFrame','TLabel','Card.TLabel','Muted.TLabel','CardMuted.TLabel',
           'Title.TLabel','Section.TLabel','Value.TLabel','Hero.TLabel','TButton','Accent.TButton',
           'Header.TButton','HeaderAccent.TButton','TNotebook','TNotebook.Tab','Treeview','Treeview.Heading',
           'TEntry','TSpinbox','TCombobox','Surface.TFrame','Metric.TFrame','Badge.TLabel',
           'Mode.TRadiobutton','Vertical.TScrollbar']
    styles={n:(style.configure(n) or {},style.map(n) or {}) for n in names}
    widgets=[]; canvases=[]
    def walk(w):
        opts={}
        for key in ('background','foreground','selectbackground','selectforeground','insertbackground','highlightbackground'):
            if key in w.keys():
                value=w.cget(key)
                if str(value):opts[key]=value
        widgets.append((w,opts))
        if isinstance(w,tk.Canvas) and w is not app.chart:
            for item in w.find_all():
                colors={k:w.itemcget(item,k) for k in ('fill','outline') if k in w.itemconfigure(item) and w.itemcget(item,k)}
                canvases.append((w,item,colors))
        for child in w.winfo_children():walk(child)
    walk(root)
    tags={tag:{k:v for k,v in app.table.tag_configure(tag).items() if k in ('background','foreground')} for tag in ('success','error','waiting')}
    globals_light={key:getattr(ui,key) for key in ('BG','INK','MUTED','BLUE','GREEN','AMBER','RED','LINE')}
    app._dark_theme=None
    def apply(dark):
        if app._dark_theme==dark:return
        app._dark_theme=dark
        app.theme_choice.set('深色' if dark else '明亮')
        def color(v):return DARK.get(str(v).lower(),v) if dark else v
        for name,(config,maps) in styles.items():
            style.configure(name,**{k:color(v) for k,v in config.items()})
            style.map(name,**{k:[(*row[:-1],color(row[-1])) for row in rows] for k,rows in maps.items()})
        # Primary buttons keep a saturated fill and white text in both themes.
        if dark:
            for name in ('Accent.TButton','HeaderAccent.TButton'):style.configure(name,foreground='#ffffff')
        for w,opts in widgets:w.configure(**{k:color(v) for k,v in opts.items()})
        for w,item,opts in canvases:w.itemconfigure(item,**{k:color(v) for k,v in opts.items()})
        for tag,opts in tags.items():app.table.tag_configure(tag,**{k:color(v) for k,v in opts.items()})
        for key,value in globals_light.items():setattr(ui,key,color(value))
        for photo,paint in root._rounded_painters:photo.paste(paint(color))
        for tag,c in [('error',ui.RED),('action',ui.BLUE),('timestamp',ui.MUTED)]:app.log_text.tag_configure(tag,foreground=c)
        app._chart_key=None
        app.draw_chart()
        def titlebar():
            try:
                value=ctypes.c_int(int(dark))
                user=ctypes.windll.user32
                user.GetParent.argtypes=[ctypes.c_void_p];user.GetParent.restype=ctypes.c_void_p
                hwnd=user.GetParent(root.winfo_id())
                setter=ctypes.windll.dwmapi.DwmSetWindowAttribute
                setter.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint]
                setter(hwnd,20,ctypes.byref(value),ctypes.sizeof(value))
            except OSError:pass
        root.after(100,titlebar)
    app.apply_system_theme=apply
    apply(prefers_dark())
