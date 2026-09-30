from test_desktop_app import module, FakeMonitor
from unittest.mock import patch
import tempfile
import time
import tkinter as tk

with tempfile.TemporaryDirectory() as tmp:
    root=tk.Tk()
    monitor=FakeMonitor(tmp)
    app=module.App(root,monitor)
    root.update()
    try:
        app.minimize_button.invoke()
        deadline=time.monotonic()+8
        while not app.tray.hidden and time.monotonic()<deadline:
            root.update(); time.sleep(.03)
        assert app.tray.ready and app.tray.icon.visible
        assert app.tray.hidden and root.state()=='withdrawn'
        assert monitor.alive and not monitor.stop_requested
        app.tray.events.put('show')
        deadline=time.monotonic()+2
        while app.tray.hidden and time.monotonic()<deadline:
            root.update(); time.sleep(.03)
        assert root.state()=='normal' and not app.tray.hidden
        root.iconify(); root.update()
        assert app.tray.hidden and root.state()=='withdrawn'
        with patch.object(module.messagebox,'askyesno',return_value=False):
            app.tray.events.put('exit')
            deadline=time.monotonic()+2
            while app.tray.hidden and time.monotonic()<deadline:
                root.update(); time.sleep(.03)
        assert not app.closing and monitor.alive and root.state()=='normal'
    finally:
        root.destroy()
    assert app.tray.closed and not app.tray.icon.visible
print('PASS: actual Windows tray creation, hide/restore, titlebar minimize, monitoring continuity, cancel exit and tray cleanup')
