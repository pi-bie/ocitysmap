import cairo
import rsvg
import math
import os
import psycopg2
import logging
import mapnik
from ocitysmap.draw_utils import draw_simpletext_center
from ocitysmap.layoutlib.commons import convert_pt_to_dots
from ocitysmap.layoutlib.abstract_renderer import Renderer
from math import floor, log10

LOG = logging.getLogger('ocitysmap')

#    x,y = renderer._latlon2xy(lat, lon, renderer.dpi)
#    map_scale = renderer._map_canvas.get_actual_scale()


def render(renderer, ctx):
    m = renderer._map_canvas.get_rendered_map()

    # get the m per pixel on the map
    mPerPx = m.scale()

    # get the desired width of the scalebar in m
    meter = renderer.grid.grid_size_m
    oom   = 10 ** floor(log10(meter))

    # get the desired width of the scalebar in dots
    map_coords_dots = map(lambda l: convert_pt_to_dots(l, renderer.dpi),
                          renderer._map_coords)

    dots = map_coords_dots[2]

    step_horiz = dots / renderer.grid.horiz_count


    # make some text for the scalebar (sort units)
    if oom >= 1000:
        scaleText = str(int(meter/1000)) + "km"
    else:
        scaleText = str(int(meter)) + "m"

    pxScaleBar = dots / renderer.grid.horiz_count

    LOG.warning("plugin scale: %s" % scaleText )

    barBuffer  = 20	# distance from scale bar to edge of image
    lBuffer    = 5      # distance from the line to the end of the background
    tickHeight = 20	# height of the tick marks

    x = barBuffer
    x+= Renderer.PRINT_SAFE_MARGIN_PT * renderer.dpi / 72.0
    y = m.height-barBuffer-lBuffer-lBuffer-tickHeight
    y+= (Renderer.PRINT_SAFE_MARGIN_PT + renderer._title_margin_pt) * renderer.dpi / 72.0
    w = pxScaleBar+lBuffer+lBuffer
    h = lBuffer+lBuffer+tickHeight

    LOG.warning("plugin box %d %d %d %d" % (x,y,w,h)) 
    LOG.warning("plugin img %d %d" % (m.width, m.height)) 

    ctx.save()

    ctx.rectangle(x,y,w,h)
    ctx.set_source_rgb(0, 0, 0)
    ctx.set_line_width(1)
    ctx.stroke_preserve()
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill()

    ctx.move_to(x + lBuffer, y + lBuffer)
    ctx.rel_line_to(0, tickHeight)
    ctx.rel_line_to(w-lBuffer-lBuffer, 0)
    ctx.rel_line_to(0, -tickHeight)
    ctx.set_source_rgb(0, 0, 0)
    ctx.stroke()

    draw_simpletext_center(ctx, scaleText, x+w/2, y+h/2)
    
    ctx.restore()
