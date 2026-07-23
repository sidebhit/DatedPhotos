"""Set Tcl/Tk library paths before tkinter initializes in a frozen build."""

import os
import sys


def _configure_tk_paths() -> None:
    if not getattr(sys, "frozen", False):
        return

    base = getattr(sys, "_MEIPASS", "")
    if not base:
        return

    candidates = (
        (os.path.join(base, "tcl", "tcl8.6"), os.path.join(base, "tcl", "tk8.6")),
        (os.path.join(base, "_tcl_data", "tcl8.6"), os.path.join(base, "_tcl_data", "tk8.6")),
    )
    for tcl_dir, tk_dir in candidates:
        if os.path.isdir(tcl_dir) and os.path.isdir(tk_dir):
            os.environ["TCL_LIBRARY"] = tcl_dir
            os.environ["TK_LIBRARY"] = tk_dir
            return


_configure_tk_paths()
