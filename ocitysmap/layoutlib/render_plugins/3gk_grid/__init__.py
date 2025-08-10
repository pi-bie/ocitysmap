# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2019  Hartmut Holzgraefe

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import cairo
import math
import os
import logging
import mapnik
import utm
from pyproj import Transformer

from shapely.geometry import Point
from shapely.ops import transform
from functools import partial

from ocitysmap.draw_utils import draw_simpletext_center, draw_halotext_center, draw_simpletext_left, draw_simpletext_right
from ocitysmap.layoutlib.commons import convert_pt_to_dots
from ocitysmap.layoutlib.abstract_renderer import Renderer

LOG = logging.getLogger('ocitysmap')

# draw a blue UTM grid with 1km grid size on top of the map

def render(renderer, ctx):
    def pt2px(dot):
        # convert dots into screen pixels
        return dot * renderer.dpi / 72.0

    def superscript(i):
        # return the unicode superscript form of a single digit
        if i == 0:
            return '\N{SUPERSCRIPT ZERO}'
        if i == 1:
            return '\N{SUPERSCRIPT ONE}'
        elif i == 2:
            return '\N{SUPERSCRIPT TWO}'
        elif i == 3:
            return '\N{SUPERSCRIPT THREE}'
        elif i == 4:
            return '\N{SUPERSCRIPT FOUR}'
        elif i == 5:
            return '\N{SUPERSCRIPT FIVE}'
        elif i == 6:
            return '\N{SUPERSCRIPT SIX}'
        elif i == 7:
            return '\N{SUPERSCRIPT SEVEN}'
        elif i == 8:
            return '\N{SUPERSCRIPT EIGHT}'
        elif i == 9:
            return '\N{SUPERSCRIPT NINE}'
        else:
            return i

    def beautify_km(km):
        # show a kilometer value in 'beautified' form with the last two digits
        # in larger size, as these change value more often
        txt = ''

        t1 = int(km/100)
        t2 = int(km)%100

        t11 =int(t1/10)
        t12 =int(t1)%10

        if t11 > 0:
            txt = txt + superscript(t11)
        txt = txt + superscript(t12)

        txt = txt + ("%02d" % t2)

        return txt

    def utm_zonefield2epsg(number, letter):
        # return EPSG spatial reference ID for UTM zone
        # northern hemisphere zones (>= 'M') use 32600 + zone number
        # southern hemisphere zones (<= 'N') use 32700 + zone number
        if letter.upper() >= 'N':
            return 'epsg:326%02d' % number
        else:
            return 'epsg:327%02d' % number

    def utm_zonefield2proj(number, letter):
        # return proj4 / pyproj projection string for UTM zone 
        if letter.upper() <= 'M':
            south = '+south '
        else:
            south = ''

        return '+proj=utm +zone=%d %s +ellps=WGS84 +datum=WGS84 +units=m +no_defs' % (number, south)

    # ~ def gk2latlon(X,Y):
        # ~ return transformer_fromgk.transform(X,Y)
        
    # ~ def latlon2gk(lat, lon):
        # ~ return transformer_fromlatlon.transform(lat, lon)
            
    def gk_zone(lon):
        if (lon<0):
            lon = lon + 360
        return round(lon/3)

    def grid_line(lat1, lon1, lat2, lon2):
        # draw a gray grid line between two coordinates
        (x1, y1) = renderer._latlon2xy(lat1, lon1)
        (x2, y2) = renderer._latlon2xy(lat2, lon2)

        ctx.save()
        ctx.set_source_rgba(0.2, 0.2, 0.2, 0.5)
        ctx.set_line_width(pt2px(0.5))
        ctx.move_to(x1, y1)
        ctx.line_to(x2, y2)
        ctx.stroke()
        ctx.restore()
        
    def show_grid(lat1, lon1, lat2, lon2, zone = 3, clip = None):
        # draw grid over given bounding box
        
        epsg_code = 31464 + zone

        LOG.info('Try creating Gauß Krüger grid for zone %d using EPSG:%d' % (zone,epsg_code))
        
        def gk2latlon(X,Y):
            try:
                transformer_fromgk = Transformer.from_crs("EPSG:%d" % epsg_code, "EPSG:4326")
            except Exception as e:    
                LOG.warning('Error while assigning GK transformation %s \n Probably no support yet 3GK zone %d' % (e, zone))
            return transformer_fromgk.transform(X,Y)
        
        def latlon2gk(lat, lon):
            try:
                transformer_fromlatlon = Transformer.from_crs("EPSG:4326", "EPSG:%d" % epsg_code)
            except Exception as e:    
                LOG.warning('Error while assigning GK transformation %s \n Probably no support yet 3GK zone %d' % (e, zone))
            return transformer_fromlatlon.transform(lat, lon)

        if (lat1 > 0 and lat2 < 0):
            # split into two grids when bbox crosses the equator
            # TODO: should be handled by vertical zone boundary detection
            #       see also other TODO below
            show_grid(lat1, lon1, 0.000001, lon2)
            show_grid(-0.000001, lon1, lat2, lon2)
            return

        # determine default UTM coordinates for bounding box corners
        (west, north, zone1_number, zone1_letter) = utm.from_latlon(lat1, lon1)
        (east, south, zone2_number, zone2_letter) = utm.from_latlon(lat2, lon2)
        (east2, north2, zone3_number, zone3_letter) = utm.from_latlon(lat1, lon2)
        (west2, south2, zone4_number, zone4_letter) = utm.from_latlon(lat2, lon1)
        
        # determinde GK coordinatesfor bounding box corners
        (hoch, links) = latlon2gk(lat1, lon1)
        (tief, rechts) = latlon2gk(lat2, lon2)
        (hoch2, rechts2) = latlon2gk(lat1, lon2)
        (tief2, links2) = latlon2gk(lat2, lon1)
        stripe1_number = gk_zone(lon1)
        stripe2_number = gk_zone(lon2)

        west  = min(west, west2)
        east  = max(east, east2)
        north = max(north, north2)
        south = min(south, south2)
        
        hoch = max(hoch, hoch2)
        tief = min(tief,tief2)
        rechts = max(rechts, rechts2)
        links = min(links, links2)

        # exclude the polar zones for now
        # TODO: add support for polar zones
        polar_zones = ['A','B','Y','Z']
        if zone1_letter in polar_zones or zone2_letter in polar_zones:
            LOG.warning('No support for UTM polar zones yet')
            return

        # split into two grids when bbox crosses a zone border
        # TODO this need to be four zones, not just two
        #      zones are changing by latitude, too
        if stripe1_number != stripe2_number:
            # TODO: handle special cases for Sweden/Norway and Spitzbergen
            #       zone fileds 32N-V, 32N-X to 37N-X
            split_lon = round(lon2/3) * 3 - 1.5
            LOG.info('The current bounding box covers more than two 3GK zones, the leftmost is %d, while the rightmost is %d' % (stripe1_number, stripe2_number))
            
            clip1 = "right"
            clip2 = "left"

            if (clip == "both"):
                clip1 = "both"
                clip2 = "both"
            elif (clip == "left"):
                clip1 = "both"
            elif (clip == "right"):
                clip2 = "both"
            show_grid(lat1, lon1,               lat2, split_lon - 0.000001, stripe1_number, clip1)            
            show_grid(lat1, split_lon+0.000001, lat2, lon2                , stripe2_number, clip2)
            return

        # determine grid bounding box pixel coordinates
        (X1, Y1) = renderer._latlon2xy(lat1, lon1)
        (X2, Y2) = renderer._latlon2xy(lat2, lon2)
        Width  = abs(X2 - X1)
        Height = abs(Y2 - Y1)

        # clip to longitude strip
        ctx.save()
        (zonex1, zoney1) = renderer._latlon2xy(lat1,round(lon1/3) * 3 - 1.5)
        (zonex2, zoney2) = renderer._latlon2xy(lat2,round(lon2/3) * 3 + 1.5)
        zonex1 = zonex1 - 100
        zonex2 = zonex2 + 100
        if (clip == "left" or clip == "both"):
            zonex1 = zonex1 + 100
        if (clip == "right" or clip == "both"):
            zonex2 = zonex2 - 100
        width  = abs(zonex2 - zonex1)
        height = abs(zoney2 - zoney1)    
        ctx.rectangle(zonex1, zoney1-100, width, 2*height)
        ctx.clip()

        # we only need one line every kilometer, so we can round things up or down
        w_km = math.floor(west/1000)
        e_km = math.ceil(east/1000)
        n_km = math.ceil(north/1000)
        s_km = math.floor(south/1000)
        l_km = math.floor(links/1000)
        r_km = math.ceil(rechts/1000)
        h_km = math.ceil(hoch/1000)
        t_km = math.floor(tief/1000)

        dv_km = abs(h_km - t_km)
        dh_km = abs(r_km - l_km)        

        # even one line per kilometer can be too much for large maps
        # so when things get too tight we only do every 10th line,
        # or every 100th etc.
        # TODO: this is hacky, as originally this was written for
        #       single kilometer resolution only, it should actually
        #       calculate a good grid line distance up front instead
        #       of doing it iteratively ... which would also have
        #       the advantage of allowing for sub-kilometer grid sizes
        factor = 1000
        while (height / dv_km) < 10:
            w_km = math.floor(w_km / 10)
            e_km = math.ceil(e_km / 10)
            n_km = math.ceil(n_km / 10)
            s_km = math.floor(s_km / 10)
            l_km = math.floor(l_km/10)
            r_km = math.ceil(r_km/10)
            h_km = math.ceil(h_km/10)
            t_km = math.floor(t_km/10)
            dv_km = abs(h_km - t_km)
            dh_km = abs(r_km - l_km)
            factor = factor * 10

        # draw the vertical grid lines
        for v in range(l_km, r_km):
            # calc line endings and draw line
            # TODO: the vertical lines are not really straight?
            (lat1, lon1) = gk2latlon(h_km * factor, v * factor)
            (lat2, lon2) = gk2latlon(t_km * factor, v * factor)
            grid_line(lat1, lon1, lat2, lon2)
            
            # draw Y value above and below the map, to the right of the vertical lines
            (x1, y1) = renderer._latlon2xy(lat1, lon1)
            (x2, y2) = renderer._latlon2xy(lat2, lon2)
            ctx.save()
            ctx.set_font_size(pt2px(2.5))
            ctx.set_source_rgba(0, 0, 0, 1)
            if (x1 > X1 and x1 < X2-30):
                draw_simpletext_left(ctx, beautify_km(v*factor/1000), x1 + 1, -8-pt2px(1.5))
            if (x2 > X1 and x2 < X2-30):
                draw_simpletext_left(ctx, beautify_km(v*factor/1000), x2 + 1, Y2+pt2px(1.5))
            ctx.restore()

        # draw the horizontal grid lines
        for h in range(t_km, h_km):
            # calc line endings and draw line
            # TODO: the horizontal lines are not really straight?
            (lat1, lon1) = gk2latlon(h * factor, l_km * factor)
            (lat2, lon2) = gk2latlon(h * factor, r_km * factor)
            grid_line(lat1, lon1, lat2, lon2)
            
            # draw X value to the left and right of the map, above the horizontal lines
            (x1, y1) = renderer._latlon2xy(lat1, lon1)
            (x2, y2) = renderer._latlon2xy(lat2, lon2)
            ctx.save()
            ctx.set_font_size(pt2px(2.5))
            ctx.set_source_rgba(0, 0, 0, 1)
            if (y1-pt2px(1.5) < Y2 and y1-pt2px(1.5) > Y1):
                draw_simpletext_right(ctx, beautify_km(h*factor/1000), -1, y1-pt2px(1.5))
            if (y2-pt2px(1.5) > Y1 and y2-pt2px(1.5) < Y2):
                draw_simpletext_left(ctx, beautify_km(h*factor/1000), X2 + 1, y2-pt2px(1.5))
            ctx.restore()

        # draw zone field info in upper left map corner
        # TODO avoid overlap with northing/easting values
        # ~ ctx.set_source_rgba(0, 0, 0.5, 0.5)
        # ~ ctx.set_font_size(pt2px(12))
        # ~ draw_halotext_center(ctx, ("%d%s" % (zone1_number, zone1_letter)), pt2px(12 + renderer.PRINT_SAFE_MARGIN_PT), pt2px(5 + renderer.PRINT_SAFE_MARGIN_PT))

        ctx.restore()
        
    # determine drawing area bounding box coordinates
    bbox = renderer._map_canvas.get_actual_bounding_box()
    (lat1, lon1) = bbox.get_top_left()
    (lat2, lon2) = bbox.get_bottom_right()
    
    zone = gk_zone(bbox.get_center()[1])   

    # perform the actual work
    show_grid(lat1, lon1, lat2, lon2, zone)

