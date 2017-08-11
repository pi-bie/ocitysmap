import cairo
import rsvg
import math
import os
import psycopg2

def _camera_view(renderer, ctx, surveillance, surveillance_type, lat, lon, camera_type, direction, angle, height):
    if surveillance_type == 'camera':
        if camera_type == 'dome':
            symbol = 'dome-camera.svg'
            direction = '0'
        elif camera_type == 'fixed':
            symbol = 'camera-fixed.svg'
        elif camera_type == 'panning':
            symbol = 'camera-panning.svg'
        elif camera_type == 'guard':
            symbol = 'guard-shield.svg'
        elif camera_type == 'ALPR':
            symbol = 'speed-camera.svg'
        else:
            symbol = 'camera.svg'
    elif surveillance_type == 'guard':
        symbol = 'guard-shield.svg'
    elif surveillance_type == 'ALPR':
        symbol = 'speed-camera.svg'
    else:
        return


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


    if type(direction) == float and surveillance != 'indoor':
        if type(height) != float:
           height = 5
        elif height < 3:
           height = 3
        elif height > 12:
           height = 12

        if type(angle) != float:
            angle = 1
        else:
            if angle < 0:
               angle = - angle
            if angle <= 15:
               angle = 1
            else:
               angle = math.cos(((angle - 15) * 207986.0) / 11916720)

        radius = 0.1 * renderer.dpi * height * angle

        if camera_type == 'dome':
            ctx.arc(x, y, radius, 0, 6.28)
        else:
            a1 = direction - 120
            a2 = direction -  60

            if a1 < 0:
              a1 += 360
              a2 += 360

            ctx.arc(x, y, radius, a1*3.14/180, a2*3.14/180)
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
                    , tags->'surveillance'      AS surveillance
                    , tags->'surveillance:type' AS type
                    , tags->'camera:direction'  AS camera_direction
                    , tags->'camera:angle'      AS camera_angle
                    , tags->'camera:type'       AS camera_type
                    , tags->'height'            AS camera_height
                 FROM planet_osm_point
                WHERE tags->'man_made' = 'surveillance'
                  AND ST_CONTAINS(ST_TRANSFORM(ST_GeomFromText('%s', 4002), 3857), way)""" % renderer.rc.polygon_wkt

    cursor = renderer.db.cursor()
    cursor.execute(query)

    for lat, lon, surveillance, surveillance_type, direction, angle, camera_type, height in cursor.fetchall():
        _camera_view(renderer, ctx, surveillance, surveillance_type, lat, lon, camera_type, direction, angle, height)

