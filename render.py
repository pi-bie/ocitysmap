#!/usr/bin/env python3
# -*- coding: utf-8; mode: Python -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2009  David Decotigny
# Copyright (C) 2009  Frédéric Lehobey
# Copyright (C) 2009  David Mentré
# Copyright (C) 2009  Maxime Petazzoni
# Copyright (C) 2009  Thomas Petazzoni
# Copyright (C) 2009  Gaël Utard

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

__version__ = '0.22'

import logging
import optparse
import os
import sys
import re

import ocitysmap
import ocitysmap.layoutlib.renderers
from coords import BoundingBox

LOG = logging.getLogger('ocitysmap')

def main():
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    # Known renderer names
    KNOWN_RENDERERS_NAMES = \
        list(map(lambda r: "%s (%s)" % (r.name, r.description),
            ocitysmap.layoutlib.renderers.get_renderers()))

    # Known paper orientations
    KNOWN_PAPER_ORIENTATIONS = ['portrait', 'landscape']

    usage = '%prog [options] [-b <lat1,long1 lat2,long2>|--osmid <osmid>]'
    parser = optparse.OptionParser(usage=usage,
                                   version='%%prog %s' % __version__)
    parser.add_option('-C', '--config', dest='config_file', metavar='FILE',
                      help='specify the location of the config file.')
    parser.add_option('-p', '--prefix', dest='output_prefix', metavar='PREFIX',
                      help='set a prefix to the generated file names. '
                           'Defaults to "citymap".',
                      default='citymap')
    parser.add_option('-f', '--format', dest='output_formats', metavar='FMT',
                      help='specify the output formats. Supported file '
                           'formats: svg, svgz, pdf, ps, ps.gz, png, and csv. '
                           'Defaults to PDF. May be specified multiple times.',
                      action='append')
    parser.add_option('-t', '--title', dest='output_title', metavar='TITLE',
                      help='specify the title displayed in the output files.',
                      default="")
    parser.add_option('--osmid', dest='osmid', metavar='OSMID',
                      help='OSM ID representing the polygon of the city '
                      'to render.', type="int"),
    parser.add_option('-b', '--bounding-box', dest='bbox',  nargs=2,
                      metavar='LAT1,LON1 LAT2,LON2',
                      help='bounding box (EPSG: 4326).')
    parser.add_option('-L', '--language', dest='language',
                      metavar='LANGUAGE_CODE',
                      help='language to use when generating the index '
                           '(default=en_US.UTF-8). The map language is '
                           'driven by the system\' locale setting.',
                      default='en_US.UTF-8')
    parser.add_option('-s', '--stylesheet', dest='stylesheet',
                      metavar='NAME',
                      help='specify which stylesheet to use. Defaults to the '
                      'first specified in the configuration file.')
    parser.add_option('--overlay', dest='overlays',
                      metavar='NAME',
                      help='comma separated list of overlay stylesheets to use. '
                      'Defaults to none')
    parser.add_option('-l', '--layout', dest='layout',
                      metavar='NAME',
#                      default=KNOWN_RENDERERS_NAMES[0].split()[0],
#                      help=('specify which layout to use. Available layouts '
#                            'are: %s. Defaults to %s.' %
#                            (', '.join(KNOWN_RENDERERS_NAMES),
#                             KNOWN_RENDERERS_NAMES[0].split()[0]))
                     )
    parser.add_option('--paper-format', metavar='FMT',
                      help='set the output paper format. Either "default", '
                           '"Best fit", one of the paper size names '
                           'defined in the configuration file, '
                           'or a custom size in millimeters like e.g. 100x100',
                      default='default')
    parser.add_option('--orientation', metavar='ORIENTATION',
                      help='set the output paper orientation. Either '
                            '"portrait" or "landscape". Defaults to portrait.',
                      default='portrait')
    parser.add_option('--poi-file', metavar='FILE',
                      help='provide a file containing POI information to '
                           'create an index instead of auto-generating it.')
    parser.add_option('--gpx-file', metavar='FILE',
                      help='a GPX track to be put on top of the rendered map.')
    parser.add_option('--umap-file', metavar='FILE',
                      help='a Umap export file to be put on top of the rendered map.')

    (options, args) = parser.parse_args()
    if len(args):
        parser.print_help()
        return 1

    # Make sure either -b or -c is given
    optcnt = 0
    for var in options.bbox, options.osmid:
        if var:
            optcnt += 1

    if optcnt == 0:
        parser.error("One of --bounding-box "
                     "or --osmid is mandatory")

    if optcnt > 1:
        parser.error("Options --bounding-box "
                     "or --osmid are exclusive")

    # Parse config file and instanciate main object
    mapper = ocitysmap.OCitySMap(
        [options.config_file or os.path.join(os.environ["HOME"], '.ocitysmap.conf')])

    # Parse bounding box arguments when given
    bbox = None
    if options.bbox:
        try:
            bbox = BoundingBox.parse_latlon_strtuple(options.bbox)
        except ValueError:
            parser.error('Invalid bounding box!')
        # Check that latitude and langitude are different
        lat1, lon1 = bbox.get_top_left()
        lat2, lon2 = bbox.get_bottom_right()
        if lat1 == lat2:
            parser.error('Same latitude in bounding box corners')
        if lon1 == lon2:
            parser.error('Same longitude in bounding box corners')

    # Parse OSM id when given
    if options.osmid:
        try:
            bbox  = BoundingBox.parse_wkt(
                mapper.get_geographic_info(options.osmid)[0])
        except LookupError:
            parser.error('No such OSM id: %d' % options.osmid)

    # Parse stylesheet (defaults to 1st one)
    if options.stylesheet is None:
        stylesheet = mapper.get_all_style_configurations()[0]
    else:
        try:
            stylesheet = mapper.get_stylesheet_by_name(options.stylesheet)
        except LookupError as ex:
            parser.error("%s. Available stylesheets: %s."
                 % (ex, ', '.join(map(lambda s: s.name,
                      mapper.STYLESHEET_REGISTRY))))

    # Parse overlay stylesheet (defaults to none)
    overlays = []
    if options.overlays is not None:
        for overlay_name in options.overlays.split(","): 
            try:
                overlays.append(mapper.get_overlay_by_name(overlay_name))
            except LookupError as ex:
                parser.error("%s. Available overlay stylesheets: %s."
                     % (ex, ', '.join(map(lambda s: s.name,
                          mapper.OVERLAY_REGISTRY))))

    # Parse rendering layout
    if options.layout is None:
        cls_renderer = ocitysmap.layoutlib.renderers.get_renderers()[0]
    else:
        try:
            cls_renderer = ocitysmap.layoutlib.renderers.get_renderer_class_by_name(options.layout)
        except LookupError as ex:
            parser.error("%s\nAvailable layouts: %s."
                 % (ex, ', '.join(map(lambda lo: "%s (%s)"
                          % (lo.name, lo.description),
                          ocitysmap.layoutlib.renderers.get_renderers()))))

    # Output file formats
    if not options.output_formats:
        options.output_formats = ['pdf']
    options.output_formats = set(options.output_formats)

    # Reject output formats that are not supported by the renderer
    compatible_output_formats = cls_renderer.get_compatible_output_formats()
    for format in options.output_formats:
        if format not in compatible_output_formats:
            parser.error("Output format %s not supported by layout %s" %
                         (format, cls_renderer.name))

    # check paper-format option if given
    paper_width = None
    paper_height = None
    if options.paper_format and options.paper_format != 'default':
        matches = re.search('^(\d+)[x\*](\d+)$', options.paper_format)
        if bool(matches):
            paper_width  = int(matches.group(1))
            paper_height = int(matches.group(2))
        else:
            paper_format_names = mapper.get_all_paper_size_names()
            for format_name in paper_format_names:
                name1 = format_name.lower().replace(" ","")
                name2 = options.paper_format.lower().replace(" ","")
                if name1 == name2:
                    options.paper_format = format_name
                    break
            if not options.paper_format in paper_format_names:
                parser.error("Requested paper format %s not found. Compatible paper formats are:\n\t%s."
                             % ( options.paper_format,
                                 ', '.join(paper_format_names)))

    # Determine actual paper size

    if paper_width and paper_height:
        min_width, min_height = cls_renderer.get_minimal_paper_size(bbox)
        if paper_width < min_width or paper_height < min_height:
            parser.error("Given paper size %dmm x %dmm is too small, minimal required size is: %dmm x %dmm" %
                         (paper_width, paper_height, min_width, min_height))
    else:
        compat_papers = cls_renderer.get_compatible_paper_sizes(bbox, mapper)
        if not compat_papers:
            parser.error("No paper size compatible with this rendering.")

        paper_descr = None
        if options.paper_format == 'default':
            for paper in compat_papers:
                if paper['default']:
                    paper_descr = p
                    break
        else:
            # Make sure the requested paper size is in list
            for paper in compat_papers:
                if paper['name'] == options.paper_format:
                    paper_descr = paper
                    break
        if not paper_descr:
            parser.error("Requested paper format not compatible with rendering. Compatible paper formats are:\n\t%s."
                         % ',\n\t'.join(map(lambda p: "%s (%.1fx%.1fcm²)"
                                            % (p['name'], p['width']/10., p['height']/10.),
                                            compat_papers)))
        assert paper_descr['portrait_ok'] or paper_descr['landscape_ok']

        # Validate requested orientation
        if options.orientation not in KNOWN_PAPER_ORIENTATIONS:
            parser.error("Invalid paper orientation. Allowed orientations: %s"
                         % KNOWN_PAPER_ORIENTATIONS)

        if (options.orientation == 'portrait' and not paper_descr['portrait_ok']) or \
           (options.orientation == 'landscape' and not paper_descr['landscape_ok']):
            parser.error("Requested paper orientation %s not compatible with this rendering at this paper size." % options.orientation)

    # Prepare the rendering config
    rc              = ocitysmap.RenderingConfiguration()
    rc.title        = options.output_title
    rc.osmid        = options.osmid or None # Force to None if absent
    rc.bounding_box = bbox
    rc.language     = options.language
    rc.stylesheet   = stylesheet
    rc.overlays     = overlays
    if (options.poi_file):
        rc.poi_file     = os.path.realpath(options.poi_file)
    if (options.gpx_file):
        rc.gpx_file     = os.path.realpath(options.gpx_file)
    if (options.umap_file):
        rc.umap_file    = os.path.realpath(options.umap_file)
    # rc.import_files = options.import_file
    if paper_width and paper_height:
        rc.paper_width_mm  = paper_width
        rc.paper_height_mm = paper_height
    elif options.orientation == 'portrait':
        rc.paper_width_mm  = paper_descr['width']
        rc.paper_height_mm = paper_descr['height']
    else:
        rc.paper_width_mm  = paper_descr['height']
        rc.paper_height_mm = paper_descr['width']

    # Go !...
    mapper.render(rc, cls_renderer.name, options.output_formats,
                  options.output_prefix)

    return 0

if __name__ == '__main__':
    sys.exit(main())
