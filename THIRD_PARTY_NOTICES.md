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
| pystray (added in 3.5) | 0.19.5 | [LGPL-3.0](licenses/pystray-LGPL.txt) and [GPL-3.0 text](licenses/pystray.txt) |
| six (added in 3.5) | 1.17.0 | [MIT license](licenses/six.txt) |

PyInstaller's bootloader exception permits distributing bundled applications
under their own license, subject to their dependencies' licenses. See the
[upstream explanation](https://pyinstaller.org/en/stable/license.html).

These files document the listed dependencies, not a complete audit of every
transitive native library selected from a build machine. Rebuilders and binary
redistributors must also preserve applicable notices for additional libraries
and runtimes included by their environment. Windows and its system components
are not licensed by this project.

pystray is used unmodified under LGPL-3.0. Its corresponding source is provided
in `licenses/pystray-0.19.5.tar.gz`. You may modify or replace that library and
rebuild the executable using the application source and `build.py`; install
your modified pystray package before building. This project imposes no
restriction on reverse engineering for debugging modifications to that library.
The application's original source remains MIT licensed.
