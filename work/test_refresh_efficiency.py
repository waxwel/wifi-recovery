import sys
import tempfile
import tkinter as tk
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'outputs'))
import WifiRecoveryApp as module

class Fixture(module.Monitor):
    @property
    def alive(self): return True
    def state(self):
        return {'phase':'Online','checks':1,'probes':[{'target':'https://github.com/','status':'Success','latencyMs':100}],
                'history':[{'online':True,'latencyMs':100}],'targets':['https://github.com/']}
    def log(self): return '2026-09-14 12:00:00 Connectivity restored.'

with tempfile.TemporaryDirectory() as tmp:
    root=tk.Tk()
    root.withdraw()
    monitor=Fixture(tmp)
    app=module.App(root,monitor,autostart=False)
    root.update_idletasks()
    app.draw_chart()
    rows=app.table.get_children()
    points=app.chart.find_all()
    with patch.object(app.table,'delete',wraps=app.table.delete) as delete, patch.object(app.chart,'delete',wraps=app.chart.delete) as clear, patch.object(app.log_text,'tag_add',wraps=app.log_text.tag_add) as tag:
        for _ in range(20): app.refresh()
        assert delete.call_count==clear.call_count==tag.call_count==0
        assert rows==app.table.get_children() and points==app.chart.find_all()
        with patch.object(root,'state',return_value='iconic'),patch.object(monitor,'state',wraps=monitor.state) as read:
            for _ in range(20): app.refresh()
            assert read.call_count==0
        changed=monitor.state()
        changed['probes'][0]['latencyMs']=250
        changed['history'].append({'online':True,'latencyMs':250})
        with patch.object(monitor,'state',return_value=changed): app.refresh()
        assert delete.call_count==1 and clear.call_count==1
        assert '250 ms' in str(app.table.item(app.table.get_children()[0],'values'))
    root.destroy()
print('PASS: 20 unchanged refreshes cause zero table/chart rebuilds or log retags; minimized refreshes skip reads; restore renders new data once.')
