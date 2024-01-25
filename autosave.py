# Copyright © 2016-2023 Fern Zapata
# This program is subject to the terms of the GNU GPL, version 3
# or, at your option, any later version. If a copy of it was not
# included with this file, see https://www.gnu.org/licenses/.

import datetime
from pathlib import Path

from gi.repository import Gedit, Gio, GObject

# You can change here the default folder for unsaved files.
SAVEDIR = Path("~/.gedit_unsaved/").expanduser()
ACTIONS = (
    "save",
    "save-as",
    "save-all",
    "close",
    "close-all",
    "open",
    "quickopen",
    "config-spell",
    "check-spell",
    "inline-spell-checker",
    "print",
    "docinfo",
    "replace",
    "quran",
)


class ASWindowActivatable(GObject.Object, Gedit.WindowActivatable):
    window = GObject.Property(type=Gedit.Window)
    other_action: bool

    def __init__(self):
        super().__init__()
        self.other_action = False

    def do_activate(self):
        self.actions = {}
        for action in ACTIONS:
            if action in self.window.list_actions():
                ac = self.window.lookup_action(action)
                self.actions[ac] = ac.connect("activate", self.on_other_action)

        self.id_unfocus = self.window.connect(
            "focus-out-event", self.on_unfocused
        )

    def do_deactivate(self):
        self.window.disconnect(self.id_unfocus)
        for action, id in self.actions.items():
            action.disconnect(id)

    def on_other_action(self, *_):
        file = self.window.get_active_document().get_file()
        if file.get_location() is None:
            self.other_action = True

    def on_unfocused(self, *_):
        if self.other_action:
            # Don't auto-save when the save dialog's open.
            self.other_action = False
            return

        for n, doc in enumerate(self.window.get_unsaved_documents()):
            file = doc.get_file()

            if doc.is_untouched():
                # Nothing to do
                continue
            if file.is_readonly():
                # Skip read-only files
                continue

            if file.get_location() is None:
                # Provide a default filename
                now = datetime.datetime.now()
                SAVEDIR.mkdir(parents=True, exist_ok=True)
                filename = str(
                    SAVEDIR / now.strftime(f"%Y%m%d-%H%M%S-{n+1}.txt")
                )
                file.set_location(Gio.file_parse_name(filename))

            Gedit.commands_save_document(self.window, doc)


class ASViewActivatable(GObject.Object, Gedit.ViewActivatable):
    view = GObject.Property(type=Gedit.View)
    timer = 2000

    def __init__(self):
        super().__init__()
        self.timeout = None

    def do_activate(self):
        self.window = self.view.get_toplevel()
        self.doc = self.view.get_buffer()
        self.conn = self.doc.connect("changed", self.on_changed)

    def do_deactivate(self):
        self.doc.disconnect(self.conn)
        self.remove_timeout()

    def remove_timeout(self):
        if self.timeout is not None:
            GObject.source_remove(self.timeout)
            self.timeout = None

    def on_changed(self, *_):
        f = self.doc.get_file()
        if f.is_readonly() or f.get_location() is None:
            return
        self.remove_timeout()
        self.timeout = GObject.timeout_add(
            self.timer,
            self.save,
            priority=GObject.PRIORITY_LOW,
        )

    def save(self):
        if self.doc.get_modified():
            Gedit.commands_save_document(self.window, self.doc)
        self.timeout = None
        return False
