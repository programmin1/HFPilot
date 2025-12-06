#!/usr/bin/python3
"""
HFPilot
(C) 2025 Luke Bryan.
OSMGPSMap examples are (C) Hadley Rich 2008 <hads@nice.net.nz>

This is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License
as published by the Free Software Foundation; version 2.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, see <http://www.gnu.org/licenses/>.
"""
from PIL import Image, ImageDraw, ImageFont
import sys
import os
os.environ['LD_LIBRARY_PATH'] = 'HFlib/'
import os.path
import random
import subprocess
import json
import pathlib

localedir = pathlib.Path(__file__).resolve().parent / 'lang'
#gettext.textdomain('hfprops')
#espanol = gettext.translation('hfprops', localedir=localedir, languages=['es'])
#gettext.bindtextdomain('hfprops', localedir)
#if os.environ['LANG'][:2]=='es':
#    espanol.install()
#    __ = espanol.gettext
#else:
#    __ = gettext.gettext

import gi
gi.require_version("Gtk", "3.0")
gi.require_version('OsmGpsMap', '1.0')
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GdkPixbuf
from gi.repository import GObject
from gi.repository import Pango
from gi.repository.Gdk import Color
import time
import random
import re
import datetime
#from gi.repository import cairo
import math
import shutil
import urllib.request
import urllib.parse
from math import pi, sin, cos, sqrt, atan2, radians
from MaidenheadLocator import locatorToLatLng, latLongToLocator
from lib import openlocationcode #Plus code. https://github.com/google/open-location-code

from threading import Thread
from gi.repository import OsmGpsMap as osmgpsmap
from zipfile import ZipFile
from hfcommon import userFile

assert osmgpsmap._version == "1.0"

class RTLSDRRun(Thread):
    def __init__(self, cmd):
        Thread.__init__(self)
        self.cmd = cmd
        
    def run(self):
        #TODO test commands more
        #cmd = 'rtl_fm -M fm -f '+self.freq+'M -l 202 | play -r 24k -t raw -e s -b 16 -c 1 -V1 -'
        cmds = self.cmd.split('|')
        self.proc = subprocess.Popen(cmds[0].split(),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
        subprocess.check_output(cmds[1].split(),stdin=self.proc.stdout)
        for line in iter(self.proc.stdout.readline, b''):
            line = line.decode('utf-8')

class BackgroundDownload(Thread):
    def __init__(self, url, filename):
        #Thread init, as this is a thread:
        Thread.__init__(self)
        self.url = url
        self.filename = filename
        self.finished = False
        self.success = False
    def run(self):
        try:
            tmpfile = '/tmp/output'+str(int(time.time()))+str(random.random())
            urllib.request.urlretrieve(self.url, tmpfile)
            shutil.move( tmpfile, self.filename )
            self.finished = True
            self.success = True
        except urllib.error.URLError:
            print("offline?")
            self.finished = True
        except urllib.error.HTTPError:
            print("Failed to fetch.")
            self.finished = True

class BackgroundDownloadZip(BackgroundDownload):
    def run(self):
        super().run()
        if os.path.exists(self.filename):
            with ZipFile(self.filename, 'r') as prozip:
                prozip.extractall(path=userFile('.hidden'))
            os.remove(self.filename)
        else:
            print('Unable to update')

class UI:
    def __init__(self):
        #Gtk.Window.__init__(self, type=Gtk.WindowType.TOPLEVEL)
        self.version = '0.1'
        self.mode = ''

        self.builder = Gtk.Builder()
        self.builder.add_from_file('Main.glade')
        self.builder.connect_signals(self)
        self.dialog = self.builder.get_object('Main')
        self.imageShow = self.builder.get_object('image')
        #self.dialog.set_redraw_on_allocate(True)

        self.txWattEntry = self.builder.get_object('TxWattEntry')

        self.txAntenna = 'ISOTROPIC'
        self.rxAntenna = 'ISOTROPIC'
        self.noiseValue = 'RESIDENTIAL';
        self.noiseComboBox = self.builder.get_object('noiseComboBox')
        self.noiseListStore = self.builder.get_object('noiseListStore')
        for item in [
            ['RESIDENTIAL','Residential'],
            ['RURAL', 'Rural'],
            ['QUIETRURAL', 'Quiet Rural area'],
            ['QUITE', 'Quiet'],
            ['NOISY', 'Noisy RF']]:
            self.noiseListStore.append(item)

        self.txComboBox = self.builder.get_object('antennaTxComboBox')
        self.rxComboBox = self.builder.get_object('antennaRxComboBox')
        self.antennaListStore = self.builder.get_object('antennaListStore')
        for ant in self.antennas():
            self.antennaListStore.append(ant)

        self.dialog.set_title('HFPilot')
        self.dialog.connect('destroy', self.cleanup)

        self.dialog.show_all()
        self.dialog.set_default_size(600, 600)

        self.mainScreen = Gdk.Screen.get_default()
        privatetilesapi='https://api.mapbox.com/styles/v1/programmin/ck7jtie300p7e1iqi1ow2yvi3/tiles/256/#Z/#X/#Y?access_token=pk.eyJ1IjoicHJvZ3JhbW1pbiIsImEiOiJjazdpaXVpMTEwbHJ1M2VwYXRoZmU3bmw4In0.3UpUBsTCOL5zvvJ1xVdJdg'

        self.osm = osmgpsmap.Map(
            repo_uri=privatetilesapi,
            image_format='jpg',
        )
        if os.path.exists(userFile('lastPosition.json')):
            with open(userFile('lastPosition.json')) as lastone:
                lastposition = json.loads(lastone.read())
                self.osm.set_center_and_zoom(lastposition['lat'],
                    lastposition['lon'],
                    lastposition['zoom']
                )
        #Now map-source required or it gets some mysterious null pointers and render issue:
        self.osm.set_property("map-source", osmgpsmap.MapSource_t.LAST)
        self.osm.set_property("repo-uri", privatetilesapi)

        self.rxmark = False #osm marker
        self.txmark = False
        self.iconsize = 64

        osd = osmgpsmap.MapOsd(
                show_dpad=False,
                show_zoom=True,
                show_crosshair=False)
        
        icon_app_path = '/usr/share/icons/hicolor/scalable/apps/HFProps.svg'
        if os.path.exists(icon_app_path):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(icon_app_path)
            surface=Gdk.cairo_surface_create_from_pixbuf(pixbuf, 0, None)
        self.osm.layer_add(osd)
        self.osm.connect('button_press_event', self.on_button_press)
        self.osm.connect('button_release_event', self.on_button_release)
        #self.osm.connect('changed', self.on_map_change)

        #connect keyboard shortcuts
        self.osm.set_keyboard_shortcut(osmgpsmap.MapKey_t.FULLSCREEN, Gdk.keyval_from_name("F11"))
        self.osm.set_keyboard_shortcut(osmgpsmap.MapKey_t.UP, Gdk.keyval_from_name("Up"))
        self.osm.set_keyboard_shortcut(osmgpsmap.MapKey_t.DOWN, Gdk.keyval_from_name("Down"))
        self.osm.set_keyboard_shortcut(osmgpsmap.MapKey_t.LEFT, Gdk.keyval_from_name("Left"))
        self.osm.set_keyboard_shortcut(osmgpsmap.MapKey_t.RIGHT, Gdk.keyval_from_name("Right"))

        self.osm.show()

        self.mapOverlay = self.builder.get_object('MapOverlay')
        self.mapOverlay.set_size_request(150,150)
        self.mapOverlay.add(self.osm)
        top_container = Gtk.VBox()
        leftright_container = Gtk.HBox()
        mapboxlogo = Gtk.Image.new_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale('mapbox.svg',width=80,height=25,preserve_aspect_ratio=True))
        leftright_container.pack_start(mapboxlogo, False, False, 0)
        leftright_container.pack_end(self.linkLabel(' Improve this map', self.improvement_link), False, False, 0)
        leftright_container.pack_end(self.linkLabel(' (c) openstreetmap ', self.credit_osm), False, False, 0)
        leftright_container.pack_end(self.linkLabel(' (c) mapbox ', self.credit_mapbox), False, False, 0)
        top_container.pack_end(leftright_container, False, False, 0)
        self.mapOverlay.add_overlay(top_container)
        self.mapOverlay.set_overlay_pass_through(top_container,True)
        self.mapOverlay.show_all()
        self.latlon_entry = Gtk.Entry()

        #Adding image in the render code causes infinite loop.
        icon_app_path = '/usr/share/icons/hicolor/scalable/apps/repeaterSTART.svg'
        if os.path.exists(icon_app_path):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(icon_app_path)
            self.dialog.set_icon(pixbuf)
        #add ability to test custom map URIs
        #ex = Gtk.Expander(label="<b>Display Options</b>")
        #ex.props.use_markup = True
        vb = Gtk.VBox()
        self.repouri_entry = Gtk.Entry()
        self.image_format_entry = Gtk.Entry()
        self.image_format_entry.set_text(self.osm.props.image_format)
        #GLib.timeout_add(500, self.print_tiles)
        #GLib.timeout_add(1000, self.downloadBackground)
        self.bgdl = None
        
    def antennas(self):
        """
        Return the [values, display string]
        for the antennas.
        """
        values = [["ISOTROPIC","Isotropic"]]
        #absdir = os.path.abspath('HFlib/Data/Antenna/NEC Files')
        absdir = os.path.abspath('HFlib/Data/Antenna/T13 Files')
        for file in os.listdir(absdir):
            fullfile = os.path.join(absdir, file)
            with open(fullfile) as infile:
                for line in infile:
                    name = line.strip()
                    name = name[name.find("(")+1:]
                    name = name[:name.find(')')]
                    break;
            #name = file[file.find('(')+1:]
            #name = name[:name.find(')')]
            #values.append([fullfile,name])
            values.append([fullfile, name])
        return values

    def credit_mapbox(self, obj, obj2):
        os.system('xdg-open https://www.mapbox.com/about/maps/')
    def credit_osm(self, obj, obj2):
        os.system('xdg-open http://www.openstreetmap.org/about/')
    def improvement_link(self, obj, obj2):
        os.system('xdg-open https://www.mapbox.com/map-feedback/')

    def noiseComboChanged(self, widget, data=None):
        model = widget.get_model()
        active = widget.get_active()
        if active >= 0:
            code = model[active][0]
            self.noiseValue = code
            self.runPrediction()
    
    def txComboChanged(self,widget, data=None):
        model = widget.get_model()
        active = widget.get_active()
        if active >=0:
            code = model[active][0]
            self.txAntenna=code
            self.runPrediction()
    
    def rxComboChanged(self,widget, data=None):
        model = widget.get_model()
        active = widget.get_active()
        if active >=0:
            code = model[active][0]
            self.rxAntenna=code
            self.runPrediction()
    

    def numericChanged(self,widget,data=None):
        try:
            float(widget.get_text()) # or show error red..
            widget.modify_bg(Gtk.StateFlags.NORMAL, None)
            self.runPrediction()
        except ValueError:
            COLOR_INVALID = Color(50000, 0, 0)
            widget.modify_bg(Gtk.StateFlags.NORMAL, COLOR_INVALID)


    def linkLabel(self, lbltext, connectfunction):
        """ Like a label, clickable. https://stackoverflow.com/questions/5822191/ """
        lbl = Gtk.Label(lbltext, xalign=1);
        lbl.set_has_window(True)
        lbl.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        lbl.override_color(Gtk.StateFlags.NORMAL,  Gdk.RGBA(0.0, 0.0, 0.8, 1.0))
        lbl.connect("button-press-event", connectfunction)
        return lbl
    
    def setTX(self,lat,lon):
        if self.txmark:
            self.osm.image_remove(self.txmark)
        icon = GdkPixbuf.Pixbuf.new_from_file_at_size ("TX.svg", self.iconsize,self.iconsize)
        self.txmark = self.osm.image_add(lat,lon,icon)
        self.runPrediction()

    def setRX(self,lat,lon):
        if self.rxmark:
            self.osm.image_remove(self.rxmark)
        icon = GdkPixbuf.Pixbuf.new_from_file_at_size ("RX.svg", self.iconsize,self.iconsize)
        self.rxmark = self.osm.image_add(lat,lon,icon)
        self.runPrediction()

    def switchClicked(self,widget):
        print(widget)
    
    def search_call(self, srctext, finishfunction):
        try:
            pluscode = openlocationcode.decode(srctext)
            self.osm.set_center(pluscode.latitudeCenter, pluscode.longitudeCenter)
        except:
            try:
                gridsquare = locatorToLatLng(srctext)
                if gridsquare:
                    self.osm.set_center(gridsquare['lat'], gridsquare['lng'])
                #Search for number - internet node no. or frequency
                elif re.match(r"(\d)*\.?(\d)*$", srctext):
                    number = float(srctext)
                    self.clearRows()
                    lat, lon = self.osm.props.latitude, self.osm.props.longitude
                    noneFound = True;
                 
                    
                #What3Words address has 2 . in it:
                elif re.match( r".*\..*\..*", srctext):
                    req = urllib.request.Request(
                        'https://hearham.com/api/whatthreewords/v1?words=%s' % (urllib.parse.quote(srctext),), 
                        data=None,
                        headers={
                            'User-Agent': 'HFProps/'+self.version
                        }
                    )
                    f = urllib.request.urlopen(req)
                    objs = json.loads(f.read().decode('utf-8'))
                    if not objs:
                        self.latlon_entry.set_text('Invalid what3words.com address.')
                    else:
                        finishfunction(objs['coordinates']['lat'], objs['coordinates']['lng'])
                else:
                    # Use new query format https://github.com/osm-search/Nominatim/issues/2121 
                    req = urllib.request.Request(
                        'https://nominatim.openstreetmap.org/search?q=%s&format=json&limit=50' % (urllib.parse.quote(srctext),), 
                        data=None,
                        headers={
                            'User-Agent': 'HFProps/'+self.version
                        }
                    )
                    f = urllib.request.urlopen(req)
                    objs = json.loads(f.read().decode('utf-8'))
                    for item in objs:
                        finishfunction(float(item['lat']), float(item['lon']))
                        break
                    if len(objs)==0:
                        req = urllib.request.Request(
                            'https://hamcall.dev/'+srctext+'.json', 
                            data=None,
                            headers={
                                'User-Agent': 'HFProps/'+self.version
                            }
                        )
                        f=urllib.request.urlopen(req)
                        calllookup = json.loads(f.read().decode('utf-8'))
                        finishfunction(float(calllookup['location']['lat']), float(calllookup['location']['lon']))
            except urllib.error.URLError:
                self.latlon_entry.set_text('Network error')
                
    def zoom_in_clicked(self, button):
        self.osm.set_zoom(self.osm.props.zoom + 1)

    def zoom_out_clicked(self, button):
        self.osm.set_zoom(self.osm.props.zoom - 1)

    def home_clicked(self, button):
        #self.getlocation() #Freezes up, odd.
        GLib.timeout_add(1, self.getlocation)
        
    def back_clicked(self, button):
        self.osm.set_center_and_zoom(self.lastLat, self.lastLon, 12)

    def TXActivate(self, widget):
        self.search_call(widget.get_text(), self.setTX)

    def RXActivate(self, widget):
        self.search_call(widget.get_text(), self.setRX)
        
    def searchToggle_clicked(self,button):
        if self.mode == 'search':
            self.mode = ''
        else:
            self.mode = 'search'
            self.search_text.grab_focus()
        self.setViews()
        
    
    def privacySettingsOpen(self):
        Gdk.threads_enter()
        dlg = Gtk.MessageDialog(self, 
            0,Gtk.MessageType.WARNING,
            Gtk.ButtonsType.OK,
            __('Please allow geolocation to use this feature.'))
        response = dlg.run()
        dlg.destroy()
        subprocess.Popen(['gnome-control-center','privacy'])
        Gdk.threads_leave()

    def refreshListing(self):
        # cursor lat,lon = self.osm.get_event_location(event).get_degrees()
        lat, lon = self.osm.props.latitude, self.osm.props.longitude
        
    
    def playpause(self, btn):
        if btn.selFrequency != self.playingfreq:
            self.playRTLSDR(btn.selFrequency)
            self.playingfreq = btn.selFrequency
            for b in self.playBtns:
                b.set_image(Gtk.Image(icon_name='media-playback-start',
                      icon_size=self.PLAYSIZE))
            #All others are stopped.
            btn.set_image(Gtk.Image(icon_name='media-playback-stop',
                      icon_size=self.PLAYSIZE))
        else:
            if self.rtllistener:
                self.rtllistener.proc.kill()
            self.playingfreq = None
            btn.set_image(Gtk.Image(icon_name='media-playback-start',
                      icon_size=self.PLAYSIZE))

    def on_button_release(self, osm, event):
        pass # Not the right lat/lon props here.
        
    def on_button_press(self, osm, event):
        state = event.get_state()
        lat,lon = self.osm.get_event_location(event).get_degrees()
        print('clicked %s,%s' % (lat,lon))
        

        left    = event.button == 1 and state == 0
        middle  = event.button == 2 or (event.button == 1 and state & Gdk.ModifierType.SHIFT_MASK)
        right   = event.button == 3 or (event.button == 1 and state & Gdk.ModifierType.CONTROL_MASK)

        #work around binding bug with invalid variable name
        GDK_2BUTTON_PRESS = getattr(Gdk.EventType, "2BUTTON_PRESS")
        GDK_3BUTTON_PRESS = getattr(Gdk.EventType, "3BUTTON_PRESS")



    def playRTLSDR(self, mhz):
        if self.rtllistener:
            self.rtllistener.proc.kill()
        # -l 450 is higher squelch.
        cmd = 'rtl_fm -M fm -f '+mhz+'M -l 450 | play -r 24k -t raw -e s -b 16 -c 1 -V1 -'
        print(cmd)
        self.rtllistener = RTLSDRRun( cmd )
        self.rtllistener.start()

    def runPrediction(self):
        txpower = math.log(float(self.txWattEntry.get_text()))*4.342-30
        values = """PathName "point2point"
Path.L_tx.lat !!TXLAT!!
Path.L_tx.lng !!TXLON!!
TXAntFilePath "!!TXANT!!"
TXGOS 2.15
Path.L_rx.lat !!RXLAT!!
Path.L_rx.lng !!RXLON!!
RXAntFilePath "!!RXANT!!"
RXGOS 2.15
Path.year 2025
Path.month  11
Path.hour 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24
Path.SSN 110
Path.frequency 2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30
Path.txpower !!TXPOWER!!
Path.BW 2500.0
Path.SNRr -29.0
Path.SNRXXp 90
Path.ManMadeNoise "!!NOISE!!"
Path.Modulation "ANALOG"
Path.SorL "SHORTPATH"
RptFileFormat "RPT_OPMUF | RPT_BCR | RPT_PR | RPT_SNR | RPT_LONG | RPT_ELE"
LL.lat !!RXLAT!!
LL.lng !!RXLON!!
LR.lat !!RXLAT!!
LR.lng !!RXLON!!
UL.lat !!RXLAT!!
UL.lng !!RXLON!!
UR.lat !!RXLAT!!
UR.lng !!RXLON!!
DataFilePath "!!CWD!!/HFlib/Data/"
"""
        with open('HFlib/input.txt','w') as outfile:
            tx = self.txmark.get_point().get_degrees()
            rx = self.rxmark.get_point().get_degrees()
            outfile.write(values.replace('!!TXANT!!',self.txAntenna).replace('!!RXANT!!',self.rxAntenna).replace('!!TXPOWER!!',str(txpower)).replace('!!RXLAT!!',str(rx.lat)).replace('!!RXLON!!',str(rx.lon)).replace('!!TXLAT!!',str(tx.lat)).replace('!!TXLON!!',str(tx.lon)).replace('!!CWD!!',os.getcwd()).replace('!!NOISE!!',self.noiseValue) )
        if os.name == 'nt':
            hflib_path = os.path.abspath('HFlib\\')
            #os.environ['PATH'] = hflib_path + os.pathsep + os.environ['PATH']
            original_dir = os.getcwd()
            # Change to the directory containing the executable
            os.chdir(os.path.abspath('HFlib'))
            returnval = os.system('ITURHFProp.exe input.txt output.txt')
            os.chdir(original_dir)
        else:
            returnval = os.system('HFlib/ITURHFProp HFlib/input.txt HFlib/output.txt')
        if returnval:
            print('fail :()')
        else:
            #Load the data...
            ignoreline = True
            with open('HFlib/output.txt') as infile:
                self.BCRs = [[0 for c in range(24)] for row in range(29)]
                for line in infile:
                    if ignoreline and line.find('Calculated Parameters')==-1:
                        ignoreline = False #Read bottom of file, grid:
                    elif not ignoreline:
                        values = [item.strip() for item in  line.split(',')]
                        if len(values) == 19:
                            values = [float(item) for item in values]
                            m,hr,freq,ele,OMUF,Pr,SNR,BCR,FSMW,distdB,lossdB,upperFreq,lowerFreq,corrT,corrR,gain_tl,gain_rw,gyrofreq,scalef = values
                            hr = int(hr)-1
                            freq = int(freq)-2
                            #print('hr %s fre q %s ' % (hr, freq))
                            color = (0,0,0)
                            BCR=BCR/100
                            if(BCR>.9):
                                color=(0, 240,0)
                            elif BCR>.8:
                                color=(0,200,0)
                            elif BCR>.7:
                                color=(0,180,0)
                            elif BCR>.6:
                                color=(0,140,0)
                            elif BCR>.5:
                                color=(0,100,0)
                            elif BCR>.4:
                                color=(80,0,0)
                            elif BCR>.3:
                                color=(60,0,0)
                            elif BCR>.2:
                                color=(40,0,0)
                            elif BCR>.1:
                                color=(20,0,0)
                            self.BCRs[freq][hr] = {'value': "%.2f" % ( BCR, ) ,'color':color}
                #print(self.BCRs)
                self.create_colored_grid(self.BCRs, 30)
                self.imageShow.set_from_file('grid_output.png')
            

    def create_colored_grid(self, grid_data, cell_size=100, output_file="grid_output.png"):
        """
        Create a colored grid image with numbers 0-9 in each cell.
        
        Args:
            grid_data: 2D list where each element is a dict like {'value': 5, 'color': (255, 0, 0)}
            cell_size: Size of each cell in pixels
            output_file: Output filename
        """
        rows = len(grid_data)
        cols = len(grid_data[0]) if rows > 0 else 0

        leftmargin = 30
        topmargin = 50
        
        # Create image
        img_width = cols * cell_size + leftmargin
        img_height = rows * cell_size + topmargin
        img = Image.new('RGB', (img_width, img_height), 'white')
        draw = ImageDraw.Draw(img)
        
        # Try to load a font, fall back to default if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", cell_size // 3)
        except:
            try:
                font = ImageFont.truetype("arial.ttf", cell_size // 3)
            except:
                font = ImageFont.load_default()
        draw.text((10,1), 'Propagation HF Estimate', fill='black', font=font)
        draw.text((20,16), 'Time UTC →', fill='black', font=font)
        draw.text((2,165), "M\nH\nZ", fill='black', font=font)
        for i in range(29): #freq
            draw.text((13, topmargin+6 +i*cell_size), str(i+1), fill="black", font=font)

        for i in range(24): #HR:
            draw.text( (leftmargin + 9 + i * cell_size, topmargin-12), str(i+1), fill="black", font=font)

        # Draw grid
        for row in range(rows): #HR
            for col in range(cols): #FREQ
                cell = grid_data[row][col]
                value = cell['value']
                color = cell['color']
                
                # Calculate cell position
                x1 = col * cell_size
                y1 = row * cell_size
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                
                # Draw cell background
                draw.rectangle([leftmargin+x1, topmargin+y1, leftmargin+x2, topmargin+y2], fill=color, outline='black', width=2)
                
                # Draw text centered in cell
                text = str(value)
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                text_x = leftmargin + x1 + (cell_size - text_width) // 2
                text_y = topmargin  + y1 + (cell_size - text_height) // 2
                
                # Choose text color based on background brightness
                brightness = sum(color) / 3
                text_color = 'white' if brightness < 128 else 'black'
                
                draw.text((text_x, text_y), text, fill=text_color, font=font)
            
        # Save image
        img.save(output_file)
        return img

    
    def cleanup(self, obj):
        # stateObj = {
        #     'lat': self.renderedLat, 
        #     'lon': self.renderedLon,
        #     'zoom': self.osm.props.zoom
        # }
        # with open(userFile('lastPosition.json'), 'w') as outfile:
        #     outfile.write(json.dumps(stateObj))
        # if self.rtllistener:
        #     self.rtllistener.proc.kill()
        Gtk.main_quit()
    

if __name__ == "__main__":
    u = UI()
    Gtk.main()
