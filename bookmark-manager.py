#!/usr/bin/env python3

from functools import reduce
import subprocess
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, GObject

class Bookmark:
    def __init__(self, lines):
        self.title = lines[0].split(sep=':', maxsplit=1)[1][1:]
        self.level = int(lines[1].split(sep=':', maxsplit=1)[1])
        self.page = int(lines[2].split(sep=':', maxsplit=1)[1])

    def set_title(self, new_title):
        self.title = new_title

    def set_level(self, new_level):
        self.level = new_level

    def set_page(self, new_page):
        self.page = new_page

class BookmarkStore(Gtk.TreeStore):
    def __init__(self, bookmark_list: list[Bookmark]):
        Gtk.TreeStore.__init__(self, str, int)
        prev_of_level = dict()
        for bookmark in bookmark_list:
            found = False
            for lvl in range(bookmark.level - 1, 0, -1):
                if lvl in prev_of_level:
                    treeiter = self.append(prev_of_level[lvl],\
                            (bookmark.title, bookmark.page))
                    prev_of_level[bookmark.level] = treeiter
                    found = True
                    break
            if not found:
                treeiter = self.append(None,\
                        (bookmark.title, bookmark.page))
                prev_of_level[bookmark.level] = treeiter

    def __row_to_string(self, accumulator, store, treepath, treeiter):
        row = store[treeiter]
        level = treepath.get_depth()
        accumulator.append(f"BookmarkBegin\nBookmarkTitle: {row[0]}\nBookmarkLevel: {level}\nBookmarkPageNumber: {row[1]}")

    def to_string(self):
        bookmark_strings = []
        self.foreach(lambda store, treepath, treeiter: self.__row_to_string(bookmark_strings, store, treepath, treeiter))
        return reduce(lambda a,b: a + '\n' + b, bookmark_strings, "")

class PdfTk:
    def __init__(self, filename):
        self.filename = filename
        self.metadata_pre = []
        self.metadata_post = []
        self.bookmark_store = None

        bookmarks = []
        temp_data = enumerate(subprocess.check_output(["pdftk", filename, "dump_data"], \
                stderr=subprocess.STDOUT).splitlines())
        found_number_of_pages = False

        for _, line_bytes in temp_data:
            line = line_bytes.decode('UTF-8')
            if line == "BookmarkBegin":
                bookmark = [ temp_data.__next__()[1].decode('UTF-8') ]
                bookmark.append(temp_data.__next__()[1].decode('UTF-8'))
                bookmark.append(temp_data.__next__()[1].decode('UTF-8'))
                bookmarks.append(Bookmark(bookmark))
            else:
                if found_number_of_pages:
                    self.metadata_post.append(line)
                else:
                    self.metadata_pre.append(line)
            if line.find("NumberOfPages:") != -1:
                found_number_of_pages = True
        self.bookmark_store = BookmarkStore(bookmarks)

    def save_as(self, new_filename):
        process = subprocess.Popen(["pdftk", self.filename, "update_info_utf8", "-", "output", new_filename],\
                stdin=subprocess.PIPE)
        add_str = lambda a,b: a + "\n" + b
        full_metadata = reduce(add_str, self.metadata_pre, "") + \
                self.bookmark_store.to_string() + \
                reduce(add_str, self.metadata_post, "")
        process.communicate(input=full_metadata.encode('UTF-8'))




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
    def __init__(self, bookmark_store: BookmarkStore, store_view: Gtk.TreeView):
        Gtk.Box.__init__(self, orientation = Gtk.Orientation.VERTICAL)
        self.bookmark_store = bookmark_store
        self.store_view = store_view
        self.selection = store_view.get_selection()
        self.selection.connect("changed", self.on_change_bookmark)

        self.empty_label = Gtk.Label(label="No bookmark selected")

        self.title_box = Gtk.Box()
        self.title_entry = Gtk.Entry()
        self.title_entry.connect("activate", self.on_activate_title)
        self.title_box.pack_start(Gtk.Label(label="Title:"), True, True, 0) 
        self.title_box.pack_start(self.title_entry, True, True, 0)

        self.page_box = Gtk.Box()
        self.page_entry = Gtk.Entry()
        self.page_entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        self.page_entry.connect("activate", self.on_activate_page)
        self.page_box.pack_start(Gtk.Label(label="Page number:"), True, True, 0) 
        self.page_box.pack_start(self.page_entry, True, True, 0)

        self.add(self.empty_label)

        self.show_all()

    def clear_children(self):
        for child in self.get_children():
            self.remove(child)

    def set_store(self, new_store):
        self.bookmark_store = new_store
    
    def on_change_bookmark(self, selection):
        self.clear_children()
        model, treeiter = self.selection.get_selected()
        if self.bookmark_store is None or self.selection is None:
            self.pack_start(self.empty_label, True, True, 0)
        else:
            self.pack_start(self.title_box, False, False, 0)
            self.pack_start(self.page_box, False, False, 0)

            self.title_entry.set_text(self.bookmark_store[treeiter][0])
            self.page_entry.set_text(str(self.bookmark_store[treeiter][1]))

        self.show_all()

    def on_activate_title(self, entry):
        model, treeiter = self.selection.get_selected()
        self.bookmark_store[treeiter][0] = self.title_entry.get_text()

    def on_activate_page(self, entry):
        model, treeiter = self.selection.get_selected()
        self.bookmark_store[treeiter][1] = self.page_entry.get_text()

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

        self.button_add = ButtonWithIcon("New bookmark", "list-add")
        self.button_add.connect("clicked", self.on_add_clicked)

        self.button_remove = ButtonWithIcon("Remove bookmark", "list-remove")
        self.button_remove.connect("clicked", self.on_remove_clicked)

        self.paned = Gtk.Paned()
        self.paned.set_orientation(Gtk.Orientation.HORIZONTAL)

        self.bookmark_view: Gtk.TreeView = Gtk.TreeView()
        self.bookmark_view.set_reorderable(True)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Title", renderer, text=0)
        self.bookmark_view.append_column(column)

        self.paned.add1(self.bookmark_view)
        
        self.bookmark_edit_box = BookmarkEditBox(None, self.bookmark_view)
        self.paned.add2(self.bookmark_edit_box)

        self.empty_label = Gtk.Label(label="No PDF file loaded")
        self.add(self.empty_label)

        self.show_all()
    
    def on_pdf_first_loaded(self):
        self.remove(self.empty_label)
        self.add(self.paned)
        self.header_bar.pack_start(self.button_add)
        self.header_bar.pack_start(self.button_remove)
        self.header_bar.pack_start(self.button_save)
        self.header_bar.pack_start(self.button_save_as)
        self.pdf_loaded = True
    
    def on_pdf_loaded(self):
        self.bookmark_view.set_model(self.pdftk.bookmark_store)
        self.bookmark_edit_box.set_store(self.pdftk.bookmark_store)
        self.bookmark_view.show_all()
        self.show_all()


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
        self.on_pdf_loaded()
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
        self.pdftk.save_as(self.pdftk.filename)

    def on_add_clicked(self, widget):
        self.pdftk.bookmark_store.append(None, ("<NEW_BOOKMARK>", 1))
        self.bookmark_view.show_all()

    def on_remove_clicked(self, widget):
        model, treeiter = self.bookmark_view.get_selection().get_selected()
        self.pdftk.bookmark_store.remove(treeiter)
        self.bookmark_view.show_all()
             
    def add_filters(self, dialog):
        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name("PDF files")
        filter_pdf.add_mime_type("application/pdf")
        dialog.add_filter(filter_pdf)

win = MainWindow()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
