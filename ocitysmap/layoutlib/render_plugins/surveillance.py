import cairo
import rsvg
import math
import os
import psycopg2

def _camera_view(renderer, ctx, surveillance, camera_type, lat, lon, height, direction, angle):
    if camera_type == 'dome':
        symbol = 'dome-camera.svg'
        direction = '0'
        angle = '360'
    else:
        symbol = 'camera.svg'

    if surveillance != 'public' and surveillance != 'outdoor' and surveillance != 'indoor':
        surveillance = 'public'

    if direction and direction.isdigit():
        direction = float(direction)

    if angle and angle.isdigit():
        angle = float(angle)
    else:
        angle=60

    symbol_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'images', surveillance, symbol))

    fp = open(symbol_path,'rb')
    data = fp.read()
    fp.close()

    svg = rsvg.Handle(data=data)

    ctx.save()

    x,y = renderer._latlon2xy(lat, lon, renderer.dpi)

    scale = renderer.dpi / (4 * svg.props.height);
    sx = x - svg.props.width  * scale/2
    sy = y - svg.props.height * scale/2

    if type(direction) == float:
        if angle == 360:
            ctx.arc(x, y, renderer.dpi, 0, 6.28)
        else:
            a1 = (direction - angle/2 - 90) * 3.14 / 180
            a2 = (direction + angle/2 - 90) * 3.14 / 180

            ctx.arc(x, y, renderer.dpi, a1, a2)
            ctx.line_to(x, y)

        ctx.close_path()
        ctx.set_line_width(renderer.dpi/72.0)
        ctx.set_source_rgba(1, 0, 0, 0.5)
        ctx.stroke_preserve()
        ctx.set_source_rgba(1, 0.5, 0.5, 0.5)
        ctx.fill()

    ctx.translate(sx, sy)
    ctx.scale(scale, scale)
    svg.render_cairo(ctx)

    ctx.restore()



def render(renderer, ctx):
    query = """SELECT ST_Y(ST_TRANSFORM(way, 4002)) AS lat
                    , ST_X(ST_TRANSFORM(way, 4002)) AS lon
                    , tags->'surveillance'     AS surveillance
                    , tags->'camera:direction' AS direction
                    , tags->'camera:angle' AS angle
                    , tags->'camera:type'  AS type
                 FROM planet_osm_point
                WHERE tags->'man_made' = 'surveillance'
                  AND ST_CONTAINS(ST_TRANSFORM(ST_GeomFromText('%s', 4002), 3857), way)""" % renderer.rc.polygon_wkt

    cursor = renderer.db.cursor()
    cursor.execute(query)

    for lat, lon, surveillance, direction, angle, camera_type in cursor.fetchall():
        _camera_view(renderer, ctx, surveillance, camera_type, lat, lon, 10, direction, angle)

