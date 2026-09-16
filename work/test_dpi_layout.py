import ctypes
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'outputs'))
import WifiRecoveryApp as app
import tkinter as tk

ctypes.windll.user32.SetProcessDPIAware()
for factor in (float(sys.argv[1]),) if len(sys.argv)>1 else (1,1.5,2,2.5):
    with tempfile.TemporaryDirectory() as tmp:
        root=tk.Tk()
        root.withdraw()
        root.tk.call('tk','scaling',factor*96/72)
        ui=app.App(root,app.Monitor(tmp),autostart=False)
        root.update_idletasks()
        assert abs(ui.ui_scale-factor)<.02
        assert root.winfo_reqwidth()<=1000*factor, (factor,root.winfo_reqwidth())
        assert root.winfo_reqheight()<=850*factor, (factor,root.winfo_reqheight())
        assert abs(int(ui.table.column('url','width'))-435*factor)<3
        print(f'{factor*100:g}%: layout fits; fonts and table geometry scaled')
        root.destroy()
