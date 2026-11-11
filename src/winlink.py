import json
import math
import os
import tempfile
import threading
import time
import urllib.request

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GdkPixbuf

from MaidenheadLocator import locatorToLatLng
from hfcommon import userFile

URL = 'https://hearham.com/rmslist.json'
MAX_AGE = 12 * 3600  # refresh if cache older than 12hrs.
MAX_MARKERS = 300 # cap markers drawn at once
MIN_ZOOM = 4    # don't draw markers when zoomed out further than this
MAX_ROWS = 2500


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def parse(data):
    """rmslist.json bytes -> list of station dicts. Raises ValueError if unusable."""
    root = json.loads(data.decode('utf-8-sig'))
    gateways = root['Gateways']
    seen, out = set(), []
    for gw in gateways:
        call = (gw.get('Callsign') or '').strip().upper()
        if not call or call in seen:
            continue
        channels, seen_ch = [], set()
        for c in gw.get('GatewayChannels') or []:
            try:
                hz = float(c.get('Frequency'))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(hz) or hz <= 0:
                continue
            ch = {'modes': (c.get('SupportedModes') or '').strip(),
                  'grid': (c.get('Gridsquare') or '').strip().upper(),
                  'hz': hz,
                  'hours': c.get('OperatingHours') or ''}
            key = (ch['modes'], ch['grid'], hz)
            if key not in seen_ch:
                seen_ch.add(key)
                channels.append(ch)
        if not channels:
            continue
        channels.sort(key=lambda c: (c['hz'], c['modes']))
        lat, lon = gw.get('Latitude'), gw.get('Longitude')
        ok = (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
              and -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0))
        if not ok:
            lat = lon = None
            for c in channels:
                try:
                    g = locatorToLatLng(c['grid'])
                except Exception:
                    g = None
                if g:
                    lat, lon = g['lat'], g['lng']
                    break
            if lat is None:
                continue
        seen.add(call)
        out.append({'call': call, 'grid': channels[0]['grid'], 'lat': float(lat),
                    'lon': float(lon), 'channels': channels})
    if not out:
        raise ValueError('no usable gateways')
    out.sort(key=lambda s: s['call'])
    return out


class WinlinkStore:
    def __init__(self, ssl_context, version, on_change):
        self.ssl_context = ssl_context
        self.version = version
        self.on_change = on_change   # called on the GTK main thread
        self.path = userFile('winlink-rmslist.json')
        self.stations = []
        self.updated = None
        self.busy = False
        self.error = None
        try:
            with open(self.path, 'rb') as f:
                self.stations = parse(f.read())
            self.updated = os.path.getmtime(self.path)
        except Exception:
            self.stations = []

    def refresh_if_stale(self):
        if self.stations and self.updated and time.time() - self.updated < MAX_AGE:
            return
        self.refresh()

    def refresh(self):
        if self.busy:
            return
        self.busy = True
        self.error = None
        GLib.idle_add(self.on_change)
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            req = urllib.request.Request(URL, headers={'User-Agent': 'HFPilot/' + self.version})
            with urllib.request.urlopen(req, context=self.ssl_context, timeout=60) as f:
                data = f.read()
            stations = parse(data)
            directory = os.path.dirname(self.path) or '.'
            fd, tmp = tempfile.mkstemp(dir=directory)
            with os.fdopen(fd, 'wb') as out:
                out.write(data)
            os.replace(tmp, self.path)
            GLib.idle_add(self._done, stations, None)
        except Exception as e:
            GLib.idle_add(self._done, None, str(e))

    def _done(self, stations, error):
        self.busy = False
        if stations is not None:
            self.stations = stations
            self.updated = time.time()
            self.error = None
        else:
            self.error = 'Could not update Winlink stations: %s.%s' % (
                error, ' Using saved copy.' if self.stations else '')
        self.on_change()
        return False


class WinlinkController:
    def __init__(self, ui, ssl_context):
        self.ui = ui
        self.osm = ui.osm
        cfg = ui.config
        if 'Winlink' not in cfg:
            cfg['Winlink'] = {}
        self.enabled = cfg['Winlink'].get('enabled', 'False') == 'True'
        self.store = WinlinkStore(ssl_context, ui.version, self.on_store_change)
        self.markers = []        # [(image handle, station)]
        self.selected = None
        self._update_id = 0
        self._loading_ui = False

        icon = GdkPixbuf.Pixbuf.new_from_file_at_size ("globe.svg", 16, 16)
        self.icon = icon

        # Dialog from glade
        self.builder = Gtk.Builder()
        self.builder.add_from_file('Winlink.glade')
        self.builder.connect_signals(self)
        self.dialog = self.builder.get_object('WinlinkDialog')
        self.dialog.set_transient_for(ui.dialog)
        self.liststore = self.builder.get_object('winlinkStore')
        self.tree = self.builder.get_object('winlinkTree')
        self.search = self.builder.get_object('winlinkSearch')
        self.status = self.builder.get_object('winlinkStatus')
        self.detail = self.builder.get_object('winlinkDetail')
        self.txbtn = self.builder.get_object('winlinkTxBtn')
        self.rxbtn = self.builder.get_object('winlinkRxBtn')
        self.check = self.builder.get_object('winlinkShowCheck')
        self.check.set_active(self.enabled)

        self.osm.connect('changed', lambda *a: self.schedule_markers())
        self.store.refresh_if_stale()
        self.schedule_markers()

    # ---- store / markers -------------------------------------------------
    def on_store_change(self):
        self.update_status()
        self.populate()
        self.schedule_markers()

    def schedule_markers(self):
        if self._update_id:
            GLib.source_remove(self._update_id)
        self._update_id = GLib.timeout_add(300, self.update_markers)

    def _view_extent(self):
        zoom = self.osm.props.zoom
        dpp = 360.0 / (256 * 2 ** zoom)      # degrees of longitude per pixel
        lat, lon = self.osm.props.latitude, self.osm.props.longitude
        w = max(self.osm.get_allocated_width(), 1)
        h = max(self.osm.get_allocated_height(), 1)
        half_lon = w / 2 * dpp * 1.1
        half_lat = h / 2 * dpp * max(math.cos(math.radians(lat)), 0.05) * 1.1
        return lat, lon, half_lat, half_lon

    def update_markers(self):
        self._update_id = 0
        for handle, _ in self.markers:
            try:
                self.osm.image_remove(handle)
            except Exception:
                pass
        self.markers = []
        if not self.enabled or self.osm.props.zoom < MIN_ZOOM:
            return False
        lat, lon, hlat, hlon = self._view_extent()
        visible = []
        for s in self.store.stations:
            dlon = (s['lon'] - lon + 180) % 360 - 180   # handles antimeridian
            if abs(s['lat'] - lat) <= hlat and abs(dlon) <= hlon:
                visible.append((dlon * dlon + (s['lat'] - lat) ** 2, s))
        visible.sort(key=lambda t: t[0])
        for _, s in visible[:MAX_MARKERS]:
            handle = self.osm.image_add(s['lat'], s['lon'], self.icon)
            self.markers.append((handle, s))
        return False

    def handle_click(self, lat, lon):
        """Return True if the click hit a station marker (and open its details)."""
        if not self.enabled or not self.markers:
            return False
        dpp = 360.0 / (256 * 2 ** self.osm.props.zoom)
        radius = 12 * dpp
        best, best_d = None, None
        for _, s in self.markers:
            dlon = (s['lon'] - lon + 180) % 360 - 180
            dlat = (s['lat'] - lat) / max(math.cos(math.radians(lat)), 0.05)
            d = math.hypot(dlon, dlat)
            if d <= radius and (best_d is None or d < best_d):
                best, best_d = s, d
        if best is None:
            return False
        self.open(select=best['call'])
        return True

    # ---- dialog ----------------------------------------------------------
    def origin(self):
        try:
            return float(self.ui.txLatEntry.get_text()), float(self.ui.txLonEntry.get_text())
        except ValueError:
            return self.osm.props.latitude, self.osm.props.longitude

    def open(self, select=None):
        self.store.refresh_if_stale()
        self.update_status()
        if select:
            self.search.set_text('')
        self.populate(select)
        self.dialog.show_all()
        self.dialog.present()

    def update_status(self):
        if self.store.busy:
            text = 'Updating…'
        elif self.store.updated:
            text = 'Updated %s · %d stations' % (
                time.strftime('%Y-%m-%d %H:%M', time.localtime(self.store.updated)),
                len(self.store.stations))
        else:
            text = 'No stations yet. They download automatically when a connection is available.'
        if self.store.error:
            text += '\n' + self.store.error
        self.status.set_text(text)

    def populate(self, select=None):
        keep = select or (self.selected['call'] if self.selected else None)
        q = self.search.get_text().strip().lower()
        lat0, lon0 = self.origin()
        rows = []
        for s in self.store.stations:
            if q:
                hay = '%s %s ' % (s['call'], s['grid']) + ' '.join(
                    '%s %.4f' % (c['modes'], c['hz'] / 1e6) for c in s['channels'])
                if q not in hay.lower():
                    continue
            rows.append((haversine_km(lat0, lon0, s['lat'], s['lon']), s))
        rows.sort(key=lambda t: t[0])
        self._loading_ui = True
        self.liststore.clear()
        select_iter = None
        for dist, s in rows[:MAX_ROWS]:
            it = self.liststore.append([s['call'], s['grid'], str(len(s['channels'])),
                                        '%.1f km' % dist, s['call']])
            if s['call'] == keep:
                select_iter = it
        self._loading_ui = False
        sel = self.tree.get_selection()
        if select_iter is not None:
            sel.select_iter(select_iter)
            self.tree.scroll_to_cell(self.liststore.get_path(select_iter), None, False, 0, 0)
        else:
            sel.unselect_all()
            self.set_selected(None)

    def set_selected(self, station):
        self.selected = station
        self.txbtn.set_sensitive(station is not None)
        self.rxbtn.set_sensitive(station is not None)
        if not station:
            self.detail.set_text('')
            return
        lines = ['%s · %s' % (station['call'], station['grid']),
                 'Location: %.5f, %.5f' % (station['lat'], station['lon']), '']
        for c in station['channels']:
            line = '%s   %.4f MHz' % (c['modes'], c['hz'] / 1e6)
            if c['hours']:
                line += '   Hours: %s' % c['hours']
            lines.append(line)
        self.detail.set_text('\n'.join(lines))

    # ---- glade signal handlers ------------------------------------------
    def on_dialog_delete(self, dlg, event):
        return dlg.hide_on_delete()

    def on_dialog_response(self, dlg, response):
        dlg.hide()

    def on_show_toggled(self, widget):
        self.enabled = widget.get_active()
        self.ui.config['Winlink']['enabled'] = str(self.enabled)
        self.ui.saveSettings()
        self.schedule_markers()

    def on_search_changed(self, widget):
        self.populate()

    def on_selection_changed(self, selection):
        if self._loading_ui:
            return
        model, it = selection.get_selected()
        if it is None:
            self.set_selected(None)
            return
        call = model[it][4]
        station = next((s for s in self.store.stations if s['call'] == call), None)
        self.set_selected(station)

    def on_use_tx(self, widget):
        if self.selected:
            self.ui.setTX(self.selected['lat'], self.selected['lon'])
            self.dialog.hide()

    def on_use_rx(self, widget):
        if self.selected:
            self.ui.setRX(self.selected['lat'], self.selected['lon'])
            self.dialog.hide()
