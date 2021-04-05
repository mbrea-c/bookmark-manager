#!/usr/bin/env python3

from functools import reduce
import subprocess
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, GObject

class Bookmark(GObject.GObject):

    __gsignals__ = {
            'modified': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, lines):
        GObject.GObject.__init__(self)
        self.title = lines[0].split(sep=':', maxsplit=1)[1][1:]
        self.level = int(lines[1].split(sep=':', maxsplit=1)[1])
        self.page = int(lines[2].split(sep=':', maxsplit=1)[1])

    def set_title(self, new_title):
        self.title = new_title
        self.emit('modified')

    def set_level(self, new_level):
        self.level = new_level
        self.emit('modified')

    def set_page(self, new_page):
        self.page = new_page
        self.emit('modified')

    def to_string(self):
        return f"BookmarkBegin\nBookmarkTitle: {self.title}\nBookmarkLevel: {self.level}\nBookmarkPageNumber: {self.page}"

class BookmarkListRow(Gtk.ListBoxRow):
    def __init__(self, bookmark: Bookmark):
        Gtk.ListBoxRow.__init__(self)
        self.bookmark = bookmark
        self.label = Gtk.Label(label=bookmark.title)
        self.add(self.label)
        self.bookmark.connect("modified", self.on_bookmark_modified)

    def on_bookmark_modified(self, bookmark):
        self.label.set_label(self.bookmark.title)
        

class BookmarkEditBox(Gtk.Box):
    def __init__(self, bookmark: Bookmark):
        Gtk.Box.__init__(self, orientation = Gtk.Orientation.VERTICAL)
        self.bookmark = bookmark

        self.empty_label = Gtk.Label(label="No bookmark selected")

        self.title_box = Gtk.Box()
        self.title_entry = Gtk.Entry()
        self.title_entry.connect("activate", self.on_activate_title)
        self.title_box.pack_start(Gtk.Label(label="Title:"), True, True, 0) 
        self.title_box.pack_start(self.title_entry, True, True, 0)

        self.level_box = Gtk.Box()
        self.level_entry = Gtk.Entry()
        self.level_entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        self.level_entry.connect("activate", self.on_activate_level)
        self.level_box.pack_start(Gtk.Label(label="Level:"), True, True, 0) 
        self.level_box.pack_start(self.level_entry, True, True, 0)

        self.page_box = Gtk.Box()
        self.page_entry = Gtk.Entry()
        self.page_entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        self.page_entry.connect("activate", self.on_activate_page)
        self.page_box.pack_start(Gtk.Label(label="Page number:"), True, True, 0) 
        self.page_box.pack_start(self.page_entry, True, True, 0)

        self.on_change_bookmark()

        self.show_all()

    def clear_children(self):
        for child in self.get_children():
            self.remove(child)
    
    def on_change_bookmark(self):
        self.clear_children()
        if self.bookmark is None:
            self.pack_start(self.empty_label, True, True, 0)
        else:
            self.pack_start(self.title_box, False, False, 0)
            self.pack_start(self.level_box, False, False, 0)
            self.pack_start(self.page_box, False, False, 0)

            self.title_entry.set_text(self.bookmark.title)
            self.page_entry.set_text(str(self.bookmark.page))
            self.level_entry.set_text(str(self.bookmark.level))

        self.show_all()

    def change_bookmark(self, new_bookmark):
        self.bookmark = new_bookmark
        self.on_change_bookmark()

    def on_activate_title(self, entry):
        self.bookmark.set_title(self.title_entry.get_text())

    def on_activate_level(self, entry):
        self.bookmark.set_level(self.level_entry.get_text())

    def on_activate_page(self, entry):
        self.bookmark.set_page(self.page_entry.get_text())


class PdfTk:
    def __init__(self, filename):
        self.filename = filename
        self.metadata_pre = []
        self.metadata_post = []
        self.bookmarks = []
        temp_data = enumerate(subprocess.check_output(["pdftk", filename, "dump_data"], \
                stderr=subprocess.STDOUT).splitlines())
        found_number_of_pages = False

        for _, line_bytes in temp_data:
            line = line_bytes.decode('UTF-8')
            if line == "BookmarkBegin":
                bookmark = [ temp_data.__next__()[1].decode('UTF-8') ]
                bookmark.append(temp_data.__next__()[1].decode('UTF-8'))
                bookmark.append(temp_data.__next__()[1].decode('UTF-8'))
                self.bookmarks.append(Bookmark(bookmark))
            else:
                if found_number_of_pages:
                    self.metadata_pre.append(line)
                else:
                    self.metadata_post.append(line)
            if line.find("NumberOfPages:") != -1:
                found_number_of_pages = True

    def save_as(self, new_filename):
        process = subprocess.Popen(["pdftk", self.filename, "update_info_utf8", "-", "output", new_filename],\
                stdin=subprocess.PIPE)
        add_str = lambda a,b: a + "\n" + b
        full_metadata = reduce(add_str, self.metadata_pre, "") + \
                reduce(add_str, map(lambda bk: bk.to_string(), self.bookmarks), "") + \
                reduce(add_str, self.metadata_post, "")
        process.communicate(input=full_metadata.encode('UTF-8'))

        

class ButtonWithIcon(Gtk.Button):
    def __init__(self, label_text, icon_name):
        Gtk.Button.__init__(self)
        button_box = Gtk.Box(spacing=5)
        icon = Gio.ThemedIcon(name=icon_name)
        icon_img = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        button_box.pack_start(icon_img, False, False, 0)
        button_box.pack_end(Gtk.Label(label=label_text), False, False, 0)
        self.add(button_box)


class MainWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Bookmark Editor")

        self.pdftk = None
        self.pdf_loaded = False

        self.header_bar = Gtk.HeaderBar()
        self.set_titlebar(self.header_bar)

        self.button_open = ButtonWithIcon("Choose PDF", "document-open")
        self.button_open.connect("clicked", self.on_open_clicked)
        self.header_bar.pack_end(self.button_open)

        self.button_save_as = ButtonWithIcon("Save As", "document-save-as")
        self.button_save_as.connect("clicked", self.on_save_as_clicked)

        self.button_save = ButtonWithIcon("Save", "document-save")
        self.button_save.connect("clicked", self.on_save_clicked)

        self.paned = Gtk.Paned()
        self.paned.set_orientation(Gtk.Orientation.HORIZONTAL)

        self.bookmark_list: Gtk.ListBox = Gtk.ListBox()
        self.bookmark_list.connect("row-selected", self.on_select_row)
        self.paned.add1(self.bookmark_list)
        
        self.bookmark_edit_box = BookmarkEditBox(None)
        self.paned.add2(self.bookmark_edit_box)

        self.empty_label = Gtk.Label(label="No PDF file loaded")
        self.add(self.empty_label)

        self.update_bookmark_list()
        self.show_all()
    
    def on_pdf_first_loaded(self):
        self.remove(self.empty_label)
        self.add(self.paned)
        self.header_bar.pack_start(self.button_save)
        self.header_bar.pack_start(self.button_save_as)
        self.show_all()
        self.pdf_loaded = True

    def on_open_clicked(self, widget):
        dialog = Gtk.FileChooserDialog(
            title="Please choose a PDF file", parent=self, action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN,
            Gtk.ResponseType.OK,
        )

        self.add_filters(dialog)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.pdftk = PdfTk(dialog.get_filename())

        if not self.pdf_loaded:
            self.on_pdf_first_loaded()
        self.update_bookmark_list()
        dialog.destroy()

    def on_save_as_clicked(self, widget):
        dialog = Gtk.FileChooserDialog(
            title="Please choose a PDF file", parent=self, action=Gtk.FileChooserAction.SAVE
        )
        dialog.set_filename(self.pdftk.filename)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN,
            Gtk.ResponseType.OK,
        )

        self.add_filters(dialog)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.pdftk.save_as(dialog.get_filename())
        dialog.destroy()

    def on_save_clicked(self, widget):
        self.pdftk.save_as(self.pdftk.get_filename())
        dialog.destroy()

    def update_bookmark_list(self):
        for child in self.bookmark_list.get_children():
            self.bookmark_list.remove(child)
        if self.pdftk is not None:
            for bookmark in self.pdftk.bookmarks:
                row = BookmarkListRow(bookmark)
                self.bookmark_list.add(row)

        self.bookmark_edit_box.change_bookmark(None)
        self.bookmark_list.show_all()

    def on_select_row(self, box, row):
        self.bookmark_edit_box.change_bookmark(row.bookmark)
             
    def add_filters(self, dialog):
        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name("PDF files")
        filter_pdf.add_mime_type("application/pdf")
        dialog.add_filter(filter_pdf)

win = MainWindow()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
