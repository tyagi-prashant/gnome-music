# Copyright (c) 2013 Vadim Rutkovsky <vrutkovs@redhat.com>
# Copyright (c) 2013 Arnel A. Borja <kyoushuu@yahoo.com>
# Copyright (c) 2013 Seif Lotfy <seif@lotfy.com>
# Copyright (c) 2013 Guillaume Quintard <guillaume.quintard@gmail.com>
# Copyright (c) 2013 Lubosz Sarnecki <lubosz@gmail.com>
# Copyright (c) 2013 Sai Suman Prayaga <suman.sai14@gmail.com>
#
# GNOME Music is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# GNOME Music is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with GNOME Music; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# The GNOME Music authors hereby grant permission for non-GPL compatible
# GStreamer plugins to be used and distributed together with GStreamer
# and GNOME Music.  This permission is above and beyond the permissions
# granted by the GPL license by which GNOME Music is covered.  If you
# modify this code, you may extend this exception to your version of the
# code, but you are not obligated to do so.  If you do not wish to do so,
# delete this exception statement from your version.

import gi
gi.require_version('MediaArt', '2.0')
from gi.repository import Gtk, GdkPixbuf, Gio, GLib, Gdk, MediaArt, GObject
from gettext import gettext as _
import cairo
from math import pi
import os
from gnomemusic import log
from gnomemusic.grilo import grilo
import logging
logger = logging.getLogger(__name__)



@log
def _make_icon_frame(pixbuf, path=None):
    border = 1.5
    degrees = pi / 180
    radius = 3

    w = pixbuf.get_width()
    h = pixbuf.get_height()
    new_pixbuf = pixbuf.scale_simple(w - border * 2,
                                     h - border * 2,
                                     0)

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surface)
    ctx.new_sub_path()
    ctx.arc(w - radius, radius, radius - 0.5, -90 * degrees, 0 * degrees)
    ctx.arc(w - radius, h - radius, radius - 0.5, 0 * degrees, 90 * degrees)
    ctx.arc(radius, h - radius, radius - 0.5, 90 * degrees, 180 * degrees)
    ctx.arc(radius, radius, radius - 0.5, 180 * degrees, 270 * degrees)
    ctx.close_path()
    ctx.set_line_width(0.6)
    ctx.set_source_rgb(0.2, 0.2, 0.2)
    ctx.stroke_preserve()
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill()
    border_pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, w, h)

    new_pixbuf.copy_area(border, border,
                         w - border * 4,
                         h - border * 4,
                         border_pixbuf,
                         border * 2, border * 2)
    return border_pixbuf


class AlbumArtCache(GObject.GObject):
    instance = None
    blacklist = {}
    default_icons_cache = {}

    default_icon_width = 256
    default_icon_height = 256

    def __repr__(self):
        return '<AlbumArt>'

    @classmethod
    def get_default(cls):
        if not cls.instance:
            cls.instance = AlbumArtCache()
        return cls.instance

    @staticmethod
    def get_media_title(media, escaped=False):
        title = media.get_title()
        if title:
            if escaped:
                return GLib.markup_escape_text(title)
            else:
                return title
        uri = media.get_url()
        if uri is None:
            return _("Untitled")

        uri_file = Gio.File.new_for_path(uri)
        basename = uri_file.get_basename()

        try:
            title = GLib.uri_unescape_string(basename, '')
        except:
            title = _("Untitled")
            pass
        if escaped:
            return GLib.markup_escape_text(title)

        return title

    @log
    def __init__(self):
        GObject.GObject.__init__(self)
        try:
            self.cacheDir = os.path.join(GLib.get_user_cache_dir(), 'media-art')
            if not os.path.exists(self.cacheDir):
                Gio.file_new_for_path(self.cacheDir).make_directory(None)
        except Exception as e:
            logger.warn("Error: %s", e)

        # Prepare default icons
        self.make_default_icon(is_loading=False)
        self.make_default_icon(is_loading=True)

    def make_default_icon(self, is_loading=False):
        width = self.default_icon_width
        height = self.default_icon_height
        # get a small pixbuf with the given path
        icon_name = 'folder-music-symbolic'
        if is_loading:
            icon_name = 'content-loading-symbolic'
        icon = Gtk.IconTheme.get_default().load_icon(icon_name, max(width, height) / 4, 0)

        # create an empty pixbuf with the requested size
        result = GdkPixbuf.Pixbuf.new(icon.get_colorspace(),
                                      True,
                                      icon.get_bits_per_sample(),
                                      icon.get_width() * 4,
                                      icon.get_height() * 4)
        result.fill(0xffffffff)
        icon.composite(result,
                       icon.get_width() * 3 / 2,
                       icon.get_height() * 3 / 2,
                       icon.get_width(),
                       icon.get_height(),
                       icon.get_width() * 3 / 2,
                       icon.get_height() * 3 / 2,
                       1, 1,
                       GdkPixbuf.InterpType.NEAREST, 0x33)
        final_icon = _make_icon_frame(result)
        if width not in self.default_icons_cache:
            self.default_icons_cache[width] = {}
        if height not in self.default_icons_cache[width]:
            self.default_icons_cache[width][height] = {}
        self.default_icons_cache[width][height][is_loading] = final_icon

    @log
    def get_default_icon(self, width, height, is_loading=False):
        # Try to fetch the icon from cache
        try:
            return self.default_icons_cache[width][height][is_loading]
        except:
            pass

        # Scale the image down
        orig_icon = self.default_icons_cache[self.default_icon_width][self.default_icon_height][is_loading]
        final_icon = orig_icon.scale_simple(width, height, GdkPixbuf.InterpType.NEAREST)

        # Create a cache reference
        if width not in self.default_icons_cache:
            self.default_icons_cache[width] = {}
        if height not in self.default_icons_cache[width]:
            self.default_icons_cache[width][height] = {}
        self.default_icons_cache[width][height][is_loading] = final_icon
        return final_icon

    @log
    def lookup(self, item, width, height, callback, itr, artist, album, first=True):
        if artist in self.blacklist and album in self.blacklist[artist]:
            self.finish(item, None, None, callback, itr, width, height)
            return

        try:
            [success, thumb_file] = MediaArt.get_file(artist, album, "album")

            if success == False:
                self.finish(item, None, None, callback, itr, width, height)
                return

            if not thumb_file.query_exists():
                if first:
                    self.cached_thumb_not_found(item, width, height, thumb_file.get_path(), callback, itr, artist, album)
                else:
                    self.finish(item, None, None, callback, itr, width, height)
                return

            stream = thumb_file.read_async(GLib.PRIORITY_LOW, None, self.stream_open,
                                           [item, width, height, thumb_file, callback, itr, artist, album])
        except Exception as e:
            logger.warn("Error: %s, %s", e.__class__, e)

    @log
    def stream_open(self, thumb_file, result, arguments):
        (item, width, height, thumb_file, callback, itr, artist, album) = arguments

        try:
            width = width or -1
            height = height or -1
            stream = thumb_file.read_finish (result)
            GdkPixbuf.Pixbuf.new_from_stream_at_scale_async(stream, width, height, True, None, self.pixbuf_loaded,
                                                            [item, width, height, thumb_file, callback, itr, artist, album])
        except Exception as e:
            logger.warn("Error: %s, %s", e.__class__, e)
            self.finish(item, None, None, callback, itr, width, height)

    @log
    def pixbuf_loaded(self, stream, result, arguments):
        (item, width, height, thumb_file, callback, itr, artist, album) = arguments

        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_stream_finish (result)
            self.finish(item, _make_icon_frame(pixbuf), thumb_file.get_path(), callback, itr, width, height, artist, album)
        except Exception as e:
            logger.warn("Error: %s, %s", e.__class__, e)
            self.finish(item, None, None, callback, itr, width, height)

    @log
    def finish(self, item, pixbuf, path, callback, itr, width=-1, height=-1, artist=None, album=None):
        if (pixbuf is None and artist is not None):
            # Blacklist artist-album combination
            if artist not in self.blacklist:
                self.blacklist[artist] = []
            self.blacklist[artist].append(album)

        if pixbuf is None:
            pixbuf = self.get_default_icon(width, height, False)

        try:
            if path:
                item.set_thumbnail(GLib.filename_to_uri(path, None))
            GLib.idle_add(callback, pixbuf, path, itr)
        except Exception as e:
            logger.warn("Error: %s", e)

    @log
    def cached_thumb_not_found(self, item, width, height, path, callback, itr, artist, album):
        try:
            uri = item.get_thumbnail()
            if uri is None:
                grilo.get_album_art_for_item(item, self.album_art_for_item_callback,
                                             (item, width, height, path, callback, itr, artist, album))
                return

            self.download_thumb(item, width, height, path, callback, itr, artist, album, uri)
        except Exception as e:
            logger.warn("Error: %s", e)
            self.finish(item, None, None, callback, itr, width, height, artist, album)

    @log
    def album_art_for_item_callback(self, source, param, item, count, data, error):
        old_item, width, height, path, callback, itr, artist, album = data
        try:
            if item is None:
                return

            uri = item.get_thumbnail()
            if uri is None:
                logger.warn("can't find artwork for album '%s' by %s", album, artist)
                self.finish(item, None, None, callback, itr, width, height, artist, album)
                return
            self.download_thumb(item, width, height, path, callback, itr, artist, album, uri)
        except Exception as e:
            logger.warn("Error: %s", e)
            self.finish(item, None, None, callback, itr, width, height, artist, album)

    @log
    def download_thumb(self, item, width, height, thumb_file, callback, itr, artist, album, uri):
        src = Gio.File.new_for_uri(uri)
        src.read_async(GLib.PRIORITY_LOW, None, self.open_remote_thumb,
                       [item, width, height, thumb_file, callback, itr, artist, album])

    @log
    def open_remote_thumb(self, src, result, arguments):
        (item, width, height, thumb_file, callback, itr, artist, album) = arguments
        dest = Gio.File.new_for_path(thumb_file)

        try:
            istream = src.read_finish(result)
            dest.replace_async(None, False, Gio.FileCreateFlags.REPLACE_DESTINATION,
                               GLib.PRIORITY_LOW, None, self.open_local_thumb,
                               [item, width, height, thumb_file, callback, itr, artist, album, istream])
        except Exception as e:
            logger.warn("Error: %s", e)
            self.finish(item, None, None, callback, itr, width, height, artist, album)

    @log
    def open_local_thumb(self, dest, result, arguments):
        (item, width, height, thumb_file, callback, itr, artist, album, istream) = arguments

        try:
            ostream = dest.replace_finish(result)
            ostream.splice_async(istream,
                                 Gio.OutputStreamSpliceFlags.CLOSE_SOURCE |
                                 Gio.OutputStreamSpliceFlags.CLOSE_TARGET,
                                 GLib.PRIORITY_LOW, None,
                                 self.copy_finished,
                                 [item, width, height, thumb_file, callback, itr, artist, album])
        except Exception as e:
            logger.warn("Error: %s", e)
            self.finish(item, None, None, callback, itr, width, height, artist, album)

    @log
    def copy_finished(self, ostream, result, arguments):
        (item, width, height, thumb_file, callback, itr, artist, album) = arguments

        try:
            ostream.splice_finish(result)
            self.lookup(item, width, height, callback, itr, artist, album, False)
        except Exception as e:
            logger.warn("Error: %s", e)
            self.finish(item, None, None, callback, itr, width, height, artist, album)
