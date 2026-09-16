# Third-party notices

Wi-Fi Recovery's original code and documentation are licensed under MIT,
Copyright (c) 2026 waxwel. Third-party components retain their own copyrights
and licenses; the project license does not replace them.

The following notices were collected from the local build dependencies for 3.0:

| Component | Version | License text |
| --- | --- | --- |
| CPython | 3.12.7 | [Python license and historical notices](licenses/Python.txt) |
| Pillow | 12.3.0 | [Pillow license and bundled component notices](licenses/Pillow.txt) |
| Tcl | 8.6.14 | [Tcl license](licenses/Tcl.txt) |
| Tk | 8.6.14 | [Tk license](licenses/Tk.txt) |
| PyInstaller (build tool and bootloader) | 6.15.0 | [License and bootloader exception](licenses/PyInstaller.txt) |

PyInstaller's bootloader exception permits distributing bundled applications
under their own license, subject to their dependencies' licenses. See the
[upstream explanation](https://pyinstaller.org/en/stable/license.html).

These files document the listed dependencies, not a complete audit of every
transitive native library selected from a build machine. Rebuilders and binary
redistributors must also preserve applicable notices for additional libraries
and runtimes included by their environment. Windows and its system components
are not licensed by this project.
