"""Windows tray lifecycle; callbacks communicate with Tk through a queue."""
import base64
import io
import queue
import threading
from tkinter import messagebox
from PIL import Image
import pystray
from icon_payload import ICON_PNG


class TrayController:
    def __init__(self, app):
        self.app, self.root = app, app.root
        self.events = queue.Queue()
        self.icon = None
        self.ready = False
        self.hidden = False
        self.requested = False
        self.closed = False
        self.thread = None
        self.previous_state = 'normal'
        self.timer = self.root.after(150, self.poll)
        self.root.bind('<Unmap>', self.on_unmap, add='+')
        self.root.bind('<Destroy>', self.on_destroy, add='+')

    def minimize(self):
        if self.closed or self.app.closing:
            return
        state = self.root.state()
        if state in ('normal', 'zoomed'):
            self.previous_state = state
        self.requested = True
        if self.ready:
            self.hidden = True
            self.root.withdraw()
            return
        if self.icon is not None:
            return
        try:
            self.icon = pystray.Icon('WifiRecovery',
                Image.open(io.BytesIO(base64.b64decode(ICON_PNG))), 'Wi-Fi 自动恢复',
                menu=pystray.Menu(
                    pystray.MenuItem('显示窗口', lambda *_: self.events.put('show'), default=True),
                    pystray.MenuItem('退出', lambda *_: self.events.put('exit'))))
            self.thread = threading.Thread(target=self.run, daemon=True, name='WifiRecoveryTray')
            self.thread.start()
        except Exception as exc:
            self.events.put(('error', str(exc)))

    def run(self):
        def setup(icon):
            try:
                icon.visible = True
                self.events.put('ready')
            except Exception as exc:
                self.events.put(('error', str(exc)))
        try:
            self.icon.run(setup=setup)
        except Exception as exc:
            self.events.put(('error', str(exc)))

    def restore(self):
        self.requested = self.hidden = False
        self.root.deiconify()
        self.root.state(self.previous_state)
        self.root.lift()
        self.root.focus_force()

    def on_unmap(self, event):
        if event.widget is self.root and self.root.state() == 'iconic':
            self.minimize()

    def poll(self):
        if self.closed:
            return
        while not self.events.empty():
            event = self.events.get_nowait()
            if event == 'ready':
                self.ready = True
                if self.requested:
                    self.minimize()
            elif event == 'show':
                self.restore()
            elif event == 'exit':
                self.restore()
                self.app.request_exit()
            elif isinstance(event, tuple) and event[0] == 'error':
                self.restore()
                self.ready = False
                if self.icon:
                    self.icon.stop()
                self.icon = None
                messagebox.showerror('无法创建托盘图标', '窗口已保留，可重试最小化。\n' + event[1], parent=self.root)
        self.timer = self.root.after(150, self.poll)

    def on_destroy(self, event):
        if event.widget is self.root:
            self.closed = True
            self.root.after_cancel(self.timer)
            if self.icon:
                if self.ready:
                    self.icon.visible = False
                self.icon.stop()
                if self.thread:
                    self.thread.join(timeout=2)
