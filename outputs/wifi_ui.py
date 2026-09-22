"""Presentation layer for the Wi-Fi recovery desktop application."""
from datetime import datetime
import ctypes
from ctypes import wintypes
import os
import tkinter as tk
from tkinter import ttk
import rounded_theme
import system_theme
import startup_settings
from scroll_view import ScrollView
from icon_payload import ICON_PNG

BG='#edf2f9'
INK='#15283f'
MUTED='#6b7d91'
BLUE='#3565db'
GREEN='#087f64'
AMBER='#aa6908'
RED='#c33e4f'
LINE='#e4ebf2'


def build(app):
    root=app.root
    root.title('Wi-Fi 自动恢复')
    root._app_icon=tk.PhotoImage(master=root,data=ICON_PNG)
    root.iconphoto(True,root._app_icon)
    root.geometry('1000x850')
    root.minsize(900,800)
    root.configure(bg=BG)
    root.protocol('WM_DELETE_WINDOW',app.request_exit)
    style=ttk.Style(root)
    style.theme_use('clam')
    style.configure('.',font=('Microsoft YaHei UI',10),background=BG,foreground=INK)
    style.configure('TFrame',background=BG)
    style.configure('Card.TFrame',background='white')
    style.configure('TLabel',background=BG,foreground=INK)
    style.configure('Card.TLabel',background='white')
    style.configure('Muted.TLabel',foreground=MUTED)
    style.configure('CardMuted.TLabel',background='white',foreground=MUTED,font=('Microsoft YaHei UI',9))
    style.configure('Title.TLabel',font=('Microsoft YaHei UI',22,'bold'))
    style.configure('Section.TLabel',background='white',font=('Microsoft YaHei UI',11,'bold'))
    style.configure('Value.TLabel',background='white',font=('Segoe UI',24,'bold'),foreground=INK)
    style.configure('Hero.TLabel',background='white',font=('Microsoft YaHei UI',19,'bold'),foreground=GREEN)
    style.configure('TButton',padding=(14,8),background='white',bordercolor=LINE,lightcolor=LINE,darkcolor=LINE,relief='flat')
    style.map('TButton',background=[('active','#eaf0f8')])
    style.configure('Accent.TButton',background=BLUE,foreground='white',bordercolor=BLUE)
    style.map('Accent.TButton',background=[('disabled','#c6d3e8'),('active','#1d4ed8')],foreground=[('disabled','#f8fafc')])
    style.configure('TNotebook',background=BG,borderwidth=0,bordercolor='white',lightcolor='white',darkcolor='white')
    style.configure('TNotebook.Tab',padding=(23,10),background=BG,foreground=MUTED,borderwidth=0)
    style.map('TNotebook.Tab',background=[('selected','white')],foreground=[('selected',BLUE)])
    style.layout('TNotebook.Tab',[('Notebook.padding',{'sticky':'nswe','children':[('Notebook.label',{'sticky':'nswe'})]})])
    style.configure('Treeview',background='white',fieldbackground='white',foreground=INK,rowheight=39,borderwidth=0)
    style.configure('Treeview.Heading',background='#f7f9fc',foreground=MUTED,font=('Microsoft YaHei UI',9),padding=(10,8),relief='flat')
    style.map('Treeview',background=[('selected','#e8efff')],foreground=[('selected',INK)])
    style.configure('TEntry',padding=7,fieldbackground='white',bordercolor=LINE)
    style.configure('TSpinbox',padding=6,fieldbackground='white',bordercolor=LINE)
    style.configure('TCombobox',padding=6,fieldbackground='white',bordercolor=LINE)
    app.viewport=ScrollView(root,BG)
    outer=app.viewport.content
    header=ttk.Frame(outer)
    header.pack(fill='x',pady=(0,10))
    ttk.Label(header,text='Wi-Fi 自动恢复',style='Title.TLabel').pack(side='left')
    ttk.Label(header,text='网络监控与连接恢复',style='Muted.TLabel').pack(side='left',padx=16,pady=(8,0))
    ttk.Button(header,text='退出',style='Header.TButton',command=app.request_exit).pack(side='right')
    app.toggle_button=ttk.Button(header,text='暂停监控',style='HeaderAccent.TButton',command=app.toggle_monitor)
    app.toggle_button.pack(side='right',padx=(0,8))

    hero=ttk.Frame(outer,style='Surface.TFrame',padding=(18,12))
    hero.pack(fill='x')
    icon=tk.Canvas(hero,width=62,height=62,bg='white',highlightthickness=0)
    icon.pack(side='left',padx=(0,14))
    icon.create_oval(0,0,60,60,fill='#e5f5ef',outline='')
    for r in (25,18,11):
        icon.create_arc(31-r,43-r,31+r,43+r,start=40,extent=100,style='arc',width=3,outline=GREEN)
    icon.create_oval(28,39,34,45,fill=GREEN,outline='')
    copy=ttk.Frame(hero,style='Card.TFrame')
    copy.pack(side='left',fill='both',expand=True)
    app.banner=ttk.Label(copy,text='正在启动…',style='Hero.TLabel')
    app.banner.pack(anchor='w')
    app.detail=ttk.Label(copy,text='',style='CardMuted.TLabel')
    app.detail.pack(anchor='w',pady=(6,0))
    app.mode_badge=ttk.Label(hero,text='使用端',style='Badge.TLabel')
    app.mode_badge.pack(side='right',anchor='n')

    tabs=ttk.Notebook(outer)
    app.tabs=tabs
    tabs.pack(fill='both',expand=True,pady=(14,0))
    status=ttk.Frame(tabs,style='Surface.TFrame',padding=16)
    settings=ttk.Frame(tabs,style='Surface.TFrame',padding=18)
    logs=ttk.Frame(tabs,style='Surface.TFrame',padding=18)
    tabs.add(status,text='运行概览')
    tabs.add(settings,text='检测设置')
    tabs.add(logs,text='运行日志')
    # Kept for the existing controller; visible summaries are split into cards.
    app.metrics=ttk.Label(status)
    row=ttk.Frame(status,style='Card.TFrame')
    row.pack(fill='x',pady=(0,12))
    app.stat_values={}
    for i,(key,title) in enumerate([('checks','本次检测'),('failures','连续失败'),('recovery','恢复尝试'),('latency','平均响应 · ms')]):
        row.columnconfigure(i,weight=1,uniform='metric')
        box=ttk.Frame(row,style='Metric.TFrame',padding=(14,8,14,8))
        box.grid(row=0,column=i,sticky='nsew',padx=(0,8) if i<3 else 0)
        ttk.Label(box,text=title,style='CardMuted.TLabel',background='#f2f6fc').pack(anchor='w')
        value=ttk.Label(box,text='—',style='Value.TLabel',background='#f2f6fc')
        value.pack(anchor='w',pady=(3,0))
        app.stat_values[key]=value
    ttk.Separator(status).pack(fill='x')
    net=ttk.Frame(status,style='Card.TFrame')
    net.pack(fill='x',pady=10)
    app.network_line=ttk.Label(net,style='CardMuted.TLabel')
    app.network_line.pack(side='left')
    app.check_time=ttk.Label(net,style='CardMuted.TLabel')
    app.check_time.pack(side='right')
    tablebox=ttk.Frame(status,style='Inset.TFrame',padding=10)
    tablebox.pack(fill='x')
    app.table=ttk.Treeview(tablebox,columns=('url','result','time'),show='headings',height=3)
    for key,title,width in [('url','检测网站',435),('result','连接结果',235),('time','请求耗时',110)]:
        app.table.heading(key,text=title)
        app.table.column(key,width=width,minwidth=80,anchor='w')
    scroll=ttk.Scrollbar(tablebox,orient='vertical',command=app.table.yview)
    scroll.pack(side='right',fill='y')
    app.table.configure(yscrollcommand=scroll.set)
    app.table.pack(side='left',fill='x',expand=True)
    for key,fg,bg in [('success',GREEN,'#f2faf6'),('error',RED,'#fff4f5'),('waiting',MUTED,'#f8fafc')]:
        app.table.tag_configure(key,foreground=fg,background=bg)
    app.probe_note=ttk.Label(status,text='网站响应通过 HTTPS 和证书校验；部分网站失败不会触发网卡重启。',style='CardMuted.TLabel',wraplength=820)
    app.probe_note.pack(fill='x',pady=(7,12))
    charthead=ttk.Frame(status,style='Card.TFrame')
    charthead.pack(fill='x')
    ttk.Label(charthead,text='响应趋势',style='Section.TLabel').pack(side='left')
    ttk.Label(charthead,text='最近 120 轮 · 首个成功网站耗时',style='CardMuted.TLabel').pack(side='right')
    app.chart=tk.Canvas(status,width=1,height=122,bg='white',highlightthickness=0)
    app.chart.pack(fill='both',expand=True,pady=(5,0))
    app.chart.bind('<Configure>',lambda _: app.draw_chart())
    app.recovery_line=ttk.Label(status,text='自动恢复：网卡 → Wi-Fi 开关 → 原网络 → 共享端热点',style='CardMuted.TLabel')
    app.recovery_line.pack(fill='x',pady=(7,0))

    settings_header=ttk.Frame(settings,style='Card.TFrame')
    settings_header.pack(fill='x',pady=(0,10))
    ttk.Label(settings_header,text='设备与连接',style='Section.TLabel').pack(side='left')
    app.theme_choice=tk.StringVar(value='明亮')
    theme_controls=ttk.Frame(settings_header,style='Card.TFrame')
    theme_controls.pack(side='right')
    ttk.Label(theme_controls,text='外观',style='CardMuted.TLabel').pack(side='left',padx=(0,8))
    for theme_name in ('明亮','深色'):
        ttk.Radiobutton(theme_controls,text=theme_name,value=theme_name,variable=app.theme_choice,style='Mode.TRadiobutton',command=lambda: app.apply_system_theme(app.theme_choice.get()=='深色')).pack(side='left',padx=(0,6))
    mode_row=ttk.Frame(settings,style='Card.TFrame'); mode_row.pack(fill='x')
    ttk.Label(mode_row,text='设备模式',style='Card.TLabel').pack(side='left',padx=(0,14))
    app.mode=tk.StringVar(value='共享端' if app.config['mode']=='host' else '使用端')
    for mode_name in ('使用端','共享端'):
        ttk.Radiobutton(mode_row,text=mode_name,value=mode_name,variable=app.mode,style='Mode.TRadiobutton').pack(side='left',padx=(0,6))
    app.mode.trace_add('write',app.mark_dirty)
    ttk.Label(mode_row,text='共享端持续检查并自动开启移动热点',style='CardMuted.TLabel').pack(side='left',padx=14)
    profile=ttk.Frame(settings,style='Card.TFrame'); profile.pack(fill='x',pady=(7,8))
    ttk.Label(profile,text='重连网络',style='Card.TLabel').pack(side='left',padx=(0,14))
    app.wifi_profile=tk.StringVar(value=app.config['wifi_profile'])
    app.profile_entry=ttk.Entry(profile,textvariable=app.wifi_profile,width=24)
    app.profile_entry.pack(side='left',fill='x',expand=True)
    app.profile_hint=ttk.Label(app.profile_entry,text='自动：等待记录网络',foreground=MUTED,background='#f8faff')
    app.profile_hint.bind('<Button-1>',lambda _: app.profile_entry.focus_set())
    app.profile_entry.bind('<FocusIn>',lambda _: update_profile_hint(app))
    app.profile_entry.bind('<FocusOut>',lambda _: update_profile_hint(app))
    app.wifi_profile.trace_add('write',lambda *_: update_profile_hint(app))
    app.wifi_profile.trace_add('write',app.mark_dirty)
    ttk.Label(profile,text='留空时自动记住原网络',style='CardMuted.TLabel').pack(side='left',padx=14)
    startup_row=ttk.Frame(settings,style='Card.TFrame')
    startup_row.pack(fill='x',pady=(0,7))
    ttk.Label(startup_row,text='开机自启',style='Card.TLabel').pack(side='left',padx=(0,14))
    app.startup_choice=tk.StringVar(value='开启' if startup_settings.is_enabled() else '关闭')
    for startup_name in ('关闭','开启'):
        ttk.Radiobutton(startup_row,text=startup_name,value=startup_name,variable=app.startup_choice,style='Mode.TRadiobutton',command=app.change_startup).pack(side='left',padx=(0,6))
    app.startup_note=ttk.Label(startup_row,text='登录 Windows 后启动 · 切换立即保存',style='CardMuted.TLabel')
    app.startup_note.pack(side='left',padx=(10,0))
    ttk.Separator(settings).pack(fill='x')
    ttk.Label(settings,text='检测与恢复',style='Section.TLabel').pack(anchor='w',pady=(8,5))
    form=ttk.Frame(settings,style='Card.TFrame'); form.pack(fill='x')
    app.fields={}
    specs=[('interval','检测间隔 · 秒',5,3600),('threshold','连续失败阈值',1,100),('timeout','单站超时 · 秒',1,30),('cooldown','恢复冷却 · 秒',30,86400)]
    for i,(key,title,low,high) in enumerate(specs):
        form.columnconfigure(i,weight=1,uniform='setting')
        ttk.Label(form,text=title,style='CardMuted.TLabel').grid(row=0,column=i,sticky='w',pady=(0,5))
        v=tk.StringVar(value=str(app.config[key])); v.trace_add('write',app.mark_dirty); app.fields[key]=v
        ttk.Entry(form,textvariable=v,width=12).grid(row=1,column=i,sticky='ew',padx=(0,14) if i<3 else 0)
    ttk.Label(settings,text='检测网址',style='Section.TLabel').pack(anchor='w',pady=(9,5))
    urlbox=ttk.Frame(settings,style='Inset.TFrame',padding=9)
    urlbox.pack(fill='both',expand=True)
    app.url_list=tk.Listbox(urlbox,height=4,font=('Microsoft YaHei UI',10),exportselection=False,relief='flat',borderwidth=0,highlightthickness=0,bg='#f8faff',fg=INK,selectbackground='#e5edff',selectforeground=BLUE,activestyle='none')
    urlscroll=ttk.Scrollbar(urlbox,orient='vertical',command=app.url_list.yview)
    urlscroll.pack(side='right',fill='y',padx=(6,0))
    app.url_list.configure(yscrollcommand=urlscroll.set)
    app.url_list.pack(side='left',fill='both',expand=True)
    for url in app.config['urls']: app.url_list.insert('end',url)
    app.url_list.bind('<<ListboxSelect>>',app.select_url)
    app.url_entry=ttk.Entry(settings); app.url_entry.pack(fill='x',pady=8); app.url_entry.insert(0,'https://')
    actions=ttk.Frame(settings,style='Card.TFrame'); actions.pack(fill='x')
    for text,command in [('添加',app.add_url),('修改选中',app.edit_url),('删除选中',app.delete_url)]:
        ttk.Button(actions,text=text,command=command).pack(side='left',padx=(0,7))
    ttk.Button(actions,text='保存并应用',style='Accent.TButton',command=app.save_settings).pack(side='right')
    app.settings_note=ttk.Label(settings,text='配置已保存。修改后点击“保存并应用”，下一轮开始生效。',style='CardMuted.TLabel',wraplength=820)
    app.settings_note.pack(fill='x',pady=(10,0))

    loghead=ttk.Frame(logs,style='Card.TFrame'); loghead.pack(fill='x',pady=(0,12))
    ttk.Label(loghead,text='运行记录',style='Section.TLabel').pack(side='left')
    ttk.Button(loghead,text='打开日志目录',command=lambda: os.startfile(str(app.monitor.run_dir))).pack(side='right')
    ttk.Label(logs,text='保留最近 80 行。红色为错误，蓝色为恢复操作；正常检测结果显示在运行概览。',style='CardMuted.TLabel').pack(anchor='w',pady=(0,10))
    logbox=ttk.Frame(logs,style='Inset.TFrame',padding=10); logbox.pack(fill='both',expand=True)
    app.log_text=tk.Text(logbox,width=1,height=12,wrap='word',font=('Consolas',10),state='disabled',relief='flat',borderwidth=0,highlightthickness=0,bg='#f8faff',fg=INK,padx=12,pady=12)
    logscroll=ttk.Scrollbar(logbox,command=app.log_text.yview); logscroll.pack(side='right',fill='y')
    app.log_text.configure(yscrollcommand=logscroll.set); app.log_text.pack(side='left',fill='both',expand=True)
    app.log_text.tag_configure('error',foreground=RED)
    app.log_text.tag_configure('action',foreground=BLUE)
    app.log_text.tag_configure('timestamp',foreground=MUTED)
    foot=ttk.Frame(outer); foot.pack(fill='x',pady=(9,0))
    app.footer=ttk.Label(foot,text='本地监控 · 最小化继续运行 · 退出需确认',style='Muted.TLabel',font=('Microsoft YaHei UI',9))
    app.footer.pack(side='left')
    ttk.Label(foot,text='DESKTOP  /  3.3',style='Muted.TLabel',font=('Segoe UI',9)).pack(side='right')
    apply_dpi_layout(app,style)
    rounded_theme.install(root,style,app.ui_scale)
    app.viewport.enable_input(app.ui_scale)
    system_theme.start(app, __import__(__name__))


def apply_dpi_layout(app,style):
    """Scale pixel geometry alongside Tk's DPI-scaled point fonts, once at startup."""
    root=app.root
    scale=float(root.winfo_fpixels('1i'))/96
    app.ui_scale=scale
    def pixels(value):
        parts=value if isinstance(value,(tuple,list)) else root.tk.splitlist(str(value))
        values=tuple(round(float(str(part))*scale) for part in parts)
        return values[0] if len(values)==1 else values
    def walk(widget):
        options=widget.keys()
        names=['padding','padx','pady','wraplength','highlightthickness']
        if isinstance(widget,tk.Canvas): names+=['width','height']
        for name in names:
            if name in options and str(widget.cget(name)):
                widget.configure(**{name:pixels(widget.cget(name))})
        manager=widget.winfo_manager()
        if manager in ('pack','grid'):
            info=getattr(widget,manager+'_info')()
            for name in ('padx','pady','ipadx','ipady'):
                if name in info: getattr(widget,manager+'_configure')(**{name:pixels(info[name])})
        if isinstance(widget,tk.Canvas):
            widget.scale('all',0,0,scale,scale)
            for item in widget.find_all():
                if widget.type(item) in ('arc','line','oval'):
                    widget.itemconfigure(item,width=float(widget.itemcget(item,'width'))*scale)
        for child in widget.winfo_children(): walk(child)
    walk(root)
    for name in ('.','TButton','TNotebook.Tab','Treeview','Treeview.Heading','TEntry','TSpinbox','TCombobox'):
        for key in ('padding','rowheight'):
            value=style.configure(name,key)
            if value: style.configure(name,**{key:pixels(value)})
    for key in app.table['columns']:
        for option in ('width','minwidth'):
            app.table.column(key,**{option:round(app.table.column(key,option)*scale)})
    area=wintypes.RECT()
    if not ctypes.windll.user32.SystemParametersInfoW(48,0,ctypes.byref(area),0):
        area=wintypes.RECT(0,0,root.winfo_screenwidth(),root.winfo_screenheight())
    width=min(round(1000*scale),area.right-area.left-round(30*scale))
    height=min(round(850*scale),area.bottom-area.top-round(60*scale))
    x=area.left+(area.right-area.left-width)//2
    y=area.top+max(0,(area.bottom-area.top-height-round(40*scale))//2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    root.minsize(min(480,width),min(320,height))


def update_profile_hint(app):
    if app.wifi_profile.get() or app.root.focus_get() == app.profile_entry:
        app.profile_hint.place_forget()
    else:
        network=app.status_data.get('wifiProfile') or '等待记录网络'
        app.profile_hint.configure(text='自动：'+network)
        margin=round(8*getattr(app,'ui_scale',1))
        app.profile_hint.place(x=margin,rely=.5,anchor='w',relwidth=1,width=-2*margin)


def update(app,data,alive):
    update_profile_hint(app)
    phase=data.get('phase')
    color=GREEN if phase=='Online' else BLUE
    if phase in ('Degraded','Disconnected','Disabled'): color=AMBER
    if phase in ('Error','HotspotError','Offline'): color=RED
    if not alive or app.stopping or app.closing: color=MUTED
    app.banner.configure(foreground=color)
    app.mode_badge.configure(text='共享端' if data.get('mode',app.config['mode'])=='host' else '使用端')
    probes=data.get('probes',[])
    times=[p['latencyMs'] for p in probes if p.get('status')=='Success' and p.get('latencyMs') is not None]
    for key,value in {'checks':data.get('checks',0),'failures':f'{data.get("failures",0)} / {data.get("failureThreshold",app.config["threshold"])}','recovery':data.get('recoveryAttempts',0),'latency':round(sum(times)/len(times)) if times else '—'}.items():
        app.stat_values[key].configure(text=str(value))
    app.stat_values['failures'].configure(foreground=RED if data.get('failures',0) else INK)
    network=data.get('wifiProfile') or '尚未记住网络'
    if len(network)>28: network=network[:27]+'…'
    radio={'On':'Wi-Fi 已打开','Off':'Wi-Fi 已关闭'}.get(data.get('wifiRadio'),'Wi-Fi 状态待确认')
    network_text=f'{network}   ·   {radio}'
    if data.get('mode',app.config['mode'])=='host':
        hotspot={'On':'已开启','Off':'已关闭','Error':'恢复失败','InTransition':'切换中'}.get(data.get('hotspotState'),'待确认')
        network_text+=f'   ·   热点{hotspot}'
    app.network_line.configure(text=network_text)
    if not app.closing:
        adapter_status={'Up':'已连接','Disconnected':'未连接','Disabled':'已禁用'}.get(data.get('adapterStatus'),'等待检测')
        app.detail.configure(text=f'网卡 {data.get("adapter", "自动选择")} · {adapter_status} · 检测间隔 {data.get("intervalSeconds",app.config["interval"])} 秒 · 冷却剩余 {data.get("cooldownRemaining",0)} 秒')
    when=str(data.get('lastCheckAt') or '')
    app.check_time.configure(text='最近检测 '+(when[11:19] if when else '—'))
    steps={'Cycling':'1 / 4  正在重启无线网卡','EnablingRadio':'2 / 4  正在打开 Wi-Fi 开关','Reconnecting':'3 / 4  正在连接原网络','StartingHotspot':'4 / 4  正在恢复移动热点'}
    note=steps.get(phase,'自动恢复：网卡 → Wi-Fi 开关 → 原网络 → 共享端热点')
    error=data.get('hotspotError') or data.get('lastError')
    if error: note='恢复提示：'+str(error)[:105]
    app.recovery_line.configure(text=note,foreground=RED if error else MUTED,wraplength=round(860*app.ui_scale))
    success=sum(p.get('status')=='Success' for p in probes)
    app.probe_note.configure(text=f'最近一轮 {success} / {len(probes)} 个网站通过 HTTPS 检测 · 部分失败不会触发网卡重启。' if probes else '等待首轮 HTTPS 检测结果…')
    try:
        age=max(0,(datetime.now().astimezone()-datetime.fromisoformat(data['updatedAt'])).total_seconds())
        if alive and age>data.get('staleAfterSeconds',90) and not app.closing:
            app.banner.configure(text='监控心跳已过期 · 请查看日志',foreground=AMBER)
        app.footer.configure(text=f'状态更新 {int(age)} 秒前  ·  最小化继续运行  ·  退出需确认')
    except (ValueError,KeyError,TypeError): pass
    if getattr(app, '_styled_log', None) == app.last_log:
        return
    app._styled_log = app.last_log
    for number,line in enumerate((app.last_log or '').splitlines(),1):
        app.log_text.tag_add('timestamp',f'{number}.0',f'{number}.19')
        tag='error' if any(s in line.lower() for s in ('failed','error','denied','失败','异常')) else 'action' if any(s in line.lower() for s in ('cycling','enabled','restored','confirmed','configuration')) else None
        if tag: app.log_text.tag_add(tag,f'{number}.20',f'{number}.end')


def draw_chart(app):
    canvas=app.chart
    if app.root.state() == 'iconic':
        return
    key=(canvas.winfo_width(),canvas.winfo_height(),app.status_data.get('history',[])[-120:])
    if key == getattr(app,'_chart_key',None):
        return
    app._chart_key=key
    canvas.delete('all')
    scale=getattr(app,'ui_scale',1)
    width=max(canvas.winfo_width()/scale,200); height=max(canvas.winfo_height()/scale,110)
    points=app.status_data.get('history',[])[-120:]
    if not points:
        canvas.create_text(width/2,height/2,text='首轮完成后将在这里显示响应趋势',fill=MUTED,font=('Microsoft YaHei UI',10))
        canvas.scale('all',0,0,scale,scale)
        return
    maximum=max(100,max((p.get('latencyMs') or 0 for p in points),default=100))
    left,right,top,bottom=58,width-14,13,height-24
    for ratio in (0,.5,1):
        y=bottom-(bottom-top)*ratio
        canvas.create_line(left,y,right,y,fill=LINE,dash=(3,4))
        canvas.create_text(left-10,y,text=str(round(maximum*ratio)),anchor='e',fill=MUTED,font=('Segoe UI',8))
    previous=None
    for i,point in enumerate(points):
        x=left+i*(right-left)/max(1,len(points)-1)
        if not point.get('online'):
            canvas.create_oval(x-3,bottom-3,x+3,bottom+3,fill=RED,outline=''); previous=None; continue
        y=bottom-(point.get('latencyMs') or 0)/maximum*(bottom-top)
        if previous: canvas.create_line(*previous,x,y,fill=BLUE,width=2)
        if len(points)<25 or i==len(points)-1: canvas.create_oval(x-2,y-2,x+2,y+2,fill=BLUE,outline='')
        previous=(x,y)
    canvas.create_text(left,bottom+16,text='较早',anchor='w',fill=MUTED,font=('Microsoft YaHei UI',8))
    canvas.create_text(right,bottom+16,text='最近一轮',anchor='e',fill=MUTED,font=('Microsoft YaHei UI',8))
    canvas.scale('all',0,0,scale,scale)
    for item in canvas.find_all():
        if canvas.type(item)=='line': canvas.itemconfigure(item,width=float(canvas.itemcget(item,'width'))*scale)
