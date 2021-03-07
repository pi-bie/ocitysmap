# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2010  David Decotigny
# Copyright (C) 2010  Frédéric Lehobey
# Copyright (C) 2010  Pierre Mauduit
# Copyright (C) 2010  David Mentré
# Copyright (C) 2010  Maxime Petazzoni
# Copyright (C) 2010  Thomas Petazzoni
# Copyright (C) 2010  Gaël Utard

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

from . import Stylesheet

import os
import tempfile
from string import Template
import gpxpy
import gpxpy.gpx
import codecs
import logging

LOG = logging.getLogger('ocitysmap')

class GpxStylesheet(Stylesheet):
    def __init__(self, gpx_file, tmpdir, track_color = '#7f7f7f'):
        super().__init__()

        gpx_fp = codecs.open(gpx_file, 'r', 'utf-8-sig')
        gpx = gpxpy.parse(gpx_fp)
        gpx_fp.close()

        if gpx.copyright_year or gpx.copyright_author or gpx.copyright_license:
            self.annotation = "GPX track © %s %s %s" % (gpx.copyright_year, gpx.copyright_author, gpx.copyright_license)

        template_dir = os.path.realpath(
            os.path.join(
                os.path.dirname(__file__),
                '../../templates/gpx'))

        style_template_file = os.path.join(template_dir, 'style-template.xml')
        layer_template_file = os.path.join(template_dir, 'layer-template.xml')

        GPX_filename = tempfile.mktemp(suffix='.xml', dir=tmpdir)
        tmpfile = open(GPX_filename, 'w')

        layer_text = ""

        with open(layer_template_file, 'r') as layer_template:
            tmplayer = Template(layer_template.read())

        if  len(gpx.tracks):
            layer_text += tmplayer.substitute(
                gpxfile = gpx_file,
                layername = "tracks"
            )

        if  len(gpx.routes):
            layer_text += tmplayer.substitute(
                gpxfile = gpx_file,
                layername = "routes"
            )

        if  len(gpx.waypoints):
            layer_text += tmplayer.substitute(
                gpxfile = gpx_file,
                layername = "waypoints"
            )

        with open(style_template_file, 'r') as style_template:
            tmpstyle = Template(style_template.read())
            tmpfile.write(
                tmpstyle.substitute(
                    gpxfile = gpx_file,
                    svgdir = template_dir,
                    color  = track_color,
                    layers = layer_text
                ))

        tmpfile.close()

        self.name = "GPX overlay"
        self.path = GPX_filename
