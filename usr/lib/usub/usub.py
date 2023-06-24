#!/usr/bin/python3
import gi
import sys
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, Gdk, GLib
import urllib.parse as urlparse
import requests
import threading
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi as yt_api
from youtube_transcript_api.formatters import WebVTTFormatter

class USub(Gtk.Application):
    DATA_DIR = '/usr/share/usub/'
    APP_ID = 'cu.axel.USub'

    def __init__(self, *args, **kargs):
        super().__init__(*args, application_id=self.APP_ID, **kargs)

        icon_theme = Gtk.IconTheme.get_default()
        icon_theme.append_search_path(self.DATA_DIR + 'icons')

        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(self.DATA_DIR + 'style.css')
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.builder = Gtk.Builder.new_from_file(self.DATA_DIR + 'window.ui')
        self.window = None

        self.main_stack = self.builder.get_object('main_stack')
        self.error_label = self.builder.get_object('error_label')

        self.url_entry = self.builder.get_object('url_entry')
        self.subs_listbox = self.builder.get_object('subs_listbox')
        self.title_label = self.builder.get_object('title_label')

        self.builder.connect_signals(self)

    def do_activate(self):
        if not self.window:
            self.window = self.builder.get_object('main_window')
            self.window.set_application(self)

        self.window.show_all()

    def parse_url(self, widget):
        video_id = self.get_video_id(self.url_entry.get_text())
        if video_id:
            self.main_stack.set_visible_child_name('loading_page')
            url = self.url_entry.get_text()
            thread = threading.Thread(target=self.get_subs, args=(url, video_id))
            thread.daemon = True
            thread.start()
        else:
            pass

    def get_subs(self, url, video_id):
        try:
            sub_list = yt_api.list_transcripts(video_id)
            request = requests.get(url)
            soup = BeautifulSoup(request.text, 'html.parser')
            title = soup.find('meta', attrs={'name': 'title'}).attrs['content']
            GLib.idle_add(self.update_sub_list, title, sub_list)
        except Exception as e:
            GLib.idle_add(self.show_error, e)

    def show_error(self, e: Exception):
        self.main_stack.set_visible_child_name('error_page')
        self.error_label.set_text(repr(e))

    def update_sub_list(self,title, sub_list):

        self.title_label.set_text(title)

        # Clear the listbox
        for child in self.subs_listbox.get_children():
            self.subs_listbox.remove(child)

        for sub in sub_list:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            icon = Gtk.Image().new_from_icon_name('subtitle-symbolic', Gtk.IconSize.LARGE_TOOLBAR)
            icon.set_valign(Gtk.Align.CENTER)
            row.pack_start(icon, False, False, 0)
            row.set_spacing(6)
            row.set_margin_top(3)
            row.set_margin_bottom(3)
            row.set_margin_start(6)
            row.set_margin_end(6)
            row.pack_start(Gtk.Label(label=sub.language), False, False, 0)
            sub_download_btn = Gtk.Button().new_from_icon_name(
                'download-symbolic', Gtk.IconSize.BUTTON)
            sub_download_btn.get_style_context().add_class('flat')
            sub_download_btn.get_style_context().add_class('tinted-button')
            sub_download_btn.connect('clicked', self.download_sub, sub)
            sub_translate_btn = Gtk.Button().new_from_icon_name(
                'translate-symbolic', Gtk.IconSize.BUTTON)
            sub_translate_btn.connect('clicked', self.translate_sub, sub)
            sub_translate_btn.get_style_context().add_class('flat')

            row.pack_end(sub_download_btn, False, False, 0)
            row.pack_end(sub_translate_btn, False, False, 0)
            self.subs_listbox.add(row)
            self.subs_listbox.show_all()

            self.main_stack.set_visible_child_name('main_page')

    def download_sub(self, button, sub):
        sub_content = sub.fetch()
        self.save_sub('subtitle_' + sub.language_code + '.srt', sub_content)

    def save_sub(self, name, sub_content):
        dialog = Gtk.FileChooserDialog(parent=self.window,
                                       title='Save subtitle',
                                       action=Gtk.FileChooserAction.SAVE)
        dialog.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Save",
                           Gtk.ResponseType.ACCEPT)
        dialog.set_current_name(name)

        response = dialog.run()

        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()

            formatter = WebVTTFormatter()
            sub = formatter.format_transcript(sub_content)

            with open(file_path, 'w') as file:
                file.write(sub)

        dialog.destroy()
        print('Subtitle saved')

    def translate_sub(self, button, sub):
        dialog = Gtk.Dialog(title='Translate subtitle')
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK
        )
        dialog.get_content_area().pack_start(Gtk.Label(label='Language code to translate to'), True, True,
                                             6)
        lang_entry = Gtk.Entry()
        lang_entry.set_margin_start(6)
        lang_entry.set_margin_end(6)
        dialog.get_content_area().pack_start(lang_entry, True, True, 6)
        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            if len((lang_code := lang_entry.get_text())) > 1:
                sub_content = sub.translate(lang_code).fetch()
                self.save_sub('subtitle_' + lang_code + '.srt', sub_content)


        dialog.destroy()

    def get_video_id(self, url):
        url_data = urlparse.urlparse(url)
        if url_data.hostname == 'youtu.be':
            return url_data.path[1:]
        if url_data.hostname in ('www.youtube.com', 'youtube.com',
                                 'm.youtube.com'):
            if url_data.path == '/watch':
                query = urlparse.parse_qs(url_data.query)
                return query['v'][0]
            if url_data.path[:7] == '/embed/':
                return url_data.path.split('/')[2]
            if url_data.path[:3] == '/v/':
                return url_data.path.split('/')[2]
        return None

    def show_about_dialog(self, button):
        dialog = Gtk.AboutDialog()
        dialog.props.program_name = 'USub'
        dialog.props.version = "0.1.0"
        dialog.props.authors = ['Axel358']
        dialog.props.copyright = 'GPL-3'
        dialog.props.logo_icon_name = self.APP_ID
        dialog.props.comments = 'Download subs for youtube vids'
        dialog.props.website = 'https://github.com/axel358/usub'
        dialog.set_transient_for(self.window)
        dialog.show()

if __name__ == "__main__":
    app = USub()
    app.run(sys.argv)
