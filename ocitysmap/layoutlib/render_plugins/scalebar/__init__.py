import cairo
import rsvg
import math
import os
import psycopg2
import logging
import mapnik
from ocitysmap.layoutlib.abstract_renderer import Renderer
from math import floor, log10

LOG = logging.getLogger('ocitysmap')

#    x,y = renderer._latlon2xy(lat, lon, renderer.dpi)
#    map_scale = renderer._map_canvas.get_actual_scale()


def render(renderer, ctx):
    m = renderer._map_canvas.get_rendered_map()

 
    # get the m per pixel on the map
    mPerPx = m.scale()

    # how many metres is 20% of the width of the map?
    twentyPc = m.width * 0.2 * mPerPx

    # get the order of magnitude
    oom = 10 ** floor(log10(twentyPc))

    # get the desired width of the scalebar in m
    mScaleBar = round(twentyPc / oom) * oom

    # get the desired width of the scalebar in px
    pxScaleBar = round(mScaleBar/mPerPx)

    # make some text for the scalebar (sort units)
    if oom >= 1000:
        scaleText = str(int(mScaleBar/1000)) + "km"
    else:
        scaleText = str(int(mScaleBar)) + "m"

    LOG.warning("plugin scale: %s" % scaleText )

    barBuffer  = 5	# distance from scale bar to edge of image
    lBuffer    = 5	# distance from the line to the end of the background
    tickHeight = 12	# height of the tick marks

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

    ctx.set_source_rgb(0, 0, 0)
    ctx.select_font_face("Georgia", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(1.2)
    ctx.move_to(x + 3*lBuffer, y)
    ctx.show_text(scaleText)

    
    ctx.restore()
