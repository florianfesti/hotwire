#!/usr/bin/env python 
'''
Copyright (C) 2012, Florian Festi

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''
import sys
sys.path.append("/usr/share/inkscape/extensions")
import os

import inkex, simplestyle
import naca

class Naca(inkex.Effect):
    def __init__(self):
        inkex.Effect.__init__(self)
        self.OptionParser.add_option("--flatness",
                        action="store", type="float", 
                        dest="flat", default='1.0',
                        help="How strong are bends allowed when converting splines to lines")
        self.OptionParser.add_option("-n", "--naca",
                                     action="store", type="string",
                                     dest="naca", default="0012",
                                     help="Naca number (4 or 5 digits)")
        self.OptionParser.add_option("-s", "--size",
                                     action="store", type="float",
                                     dest="size", default=150.0,
                                     help="Size")			
        self.OptionParser.add_option("-p",   "--points",
                                     action="store", type="int",
                                     dest="points",
                                     default=100,help="Points used for each side")		

    def effect(self):

        f = self.options.size
        naca_num = self.options.naca.strip()
        l = len(naca_num)
        if l == 4:
            pts = naca.naca4(naca_num, self.options.points, False, True)
        elif l == 5:
            pts = naca.naca5(naca_num, self.options.points, False, True)
        else:
            #sys.stderr.write("Naca number must be 4 or 5 digits\n")
            return

        path = ["M %.3f %.3f L" % (f, 0)]

        for x, y in pts:
            path.append("%.3f %.3f" % (f*x, -f*y))

        # Embed in group
        #  Translate group, Rotate path.
        t = 'translate(' + str( self.view_center[0] ) + ',' + str( self.view_center[1] ) + ')'
        g_attribs = {inkex.addNS('label','inkscape'):'Naca foil ' + naca_num,
                     'transform':t }
        g = inkex.etree.SubElement(self.current_layer, 'g', g_attribs)

        # Create SVG Path
        style = { 'stroke': '#000000', 'fill': 'none' }
        foil_attribs = {'style':simplestyle.formatStyle(style), 'd':" ".join(path)}
        foil = inkex.etree.SubElement(g, inkex.addNS('path','svg'), foil_attribs )

if __name__ == '__main__':
    e = Naca()
    e.affect()


# vim: expandtab shiftwidth=4 tabstop=8 softtabstop=4 encoding=utf-8 textwidth=99
