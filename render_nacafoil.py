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

import inkex, simplestyle, simpletransform
import naca
import bisect, math, re

f = 3.5433071 # mm to svg units


class Naca(inkex.Effect):

    style = {
        'stroke': "#000000",
        'fill': 'none',
        "stroke-width" : "0.5",
        "marker-start" : "url(#NacaArrowStart)",
        "marker-end": "url(#NacaArrowEnd)",
              }
    constyle = {
        'stroke': "#000000",
        'fill': 'none',
        "stroke-width" : "0.5",
        "marker-start" : "url(#NacaDot)",
        "marker-end": "url(#NacaDot)",
        "marker-mid": "url(#NacaDot)",
        }

    def __init__(self):
        inkex.Effect.__init__(self)
        self.OptionParser.add_option("--flatness",
                        action="store", type="float", 
                        dest="flat", default='1.0',
                        help="How strong are bends allowed when converting splines to lines")
        self.OptionParser.add_option("-m",   "--main",
                                     action="store", type="string",
                                     dest="tab",
                                     default="foil")

        self.OptionParser.add_option("-n", "--naca",
                                     action="store", type="string",
                                     dest="naca", default="0012",
                                     help="Naca number (4 or 5 digits)")
        self.OptionParser.add_option("-s", "--size",
                                     action="store", type="float",
                                     dest="size", default=150.0,
                                     help="Size")
        self.OptionParser.add_option("--approach", action="store", type="int",
                                     dest="approach", default=1)
        self.OptionParser.add_option("--approachwidth", action="store",
                                     type="float",
                                     dest="approachwidth", default=50.0)
        self.OptionParser.add_option("-p",   "--points",
                                     action="store", type="int",
                                     dest="points",
                                     default=100,help="Points used for each side")		

        self.OptionParser.add_option("-b",   "--beamtype",
                                     action="store", type="int",
                                     dest="beamtype",
                                     default=1)
        self.OptionParser.add_option("--beampos",
                                     action="store", type="float",
                                     dest="beampos",
                                     default=30.0)
        self.OptionParser.add_option("--beamwidth",
                                     action="store", type="float",
                                     dest="beamwidth",
                                     default=8.0)
        self.OptionParser.add_option("--beamheight",
                                     action="store", type="float",
                                     dest="beamheight",
                                     default=8.0)

        self.OptionParser.add_option("--other",
                                     action="store", type="inkbool",
                                     dest="other",
                                     default=False)
        self.OptionParser.add_option("--naca2",
                                     action="store", type="string",
                                     dest="naca2",
                                     default="As XY side")
        self.OptionParser.add_option("--size2",
                                     action="store", type="float",
                                     dest="size2",
                                     default=8.0)
        self.OptionParser.add_option("--twist",
                                     action="store", type="float",
                                     dest="twist",
                                     default=0.0)
        self.OptionParser.add_option("--xoffset",
                                     action="store", type="float",
                                     dest="xoffset",
                                     default=8.0)
        self.OptionParser.add_option("--yoffset",
                                     action="store", type="float",
                                     dest="yoffset",
                                     default=8.0)

    def addMarker(self, name, path, transform=None):

        defs = self.xpathSingle('/svg:svg//svg:defs')

        if defs == None:
            defs = inkex.etree.SubElement(self.document.getroot(),inkex.addNS('defs','svg'))
        for item in defs.getchildren():
            if item.get("id") == name:
                return

        marker = inkex.etree.SubElement(defs ,inkex.addNS('marker','svg'))
        marker.set('id', name)
        marker.set('orient', 'auto')
        marker.set('refX', '0.0')
        marker.set('refY', '0.0')
        marker.set('style', 'overflow:visible')
        marker.set(inkex.addNS('stockid','inkscape'), name)

        arrow = inkex.etree.Element("path")
        arrow.set('d', path)

        if transform:
            arrow.set('transform', transform)
        arrow.set('style', 'fill-rule:evenodd;stroke:#000000;stroke-width:1.0pt;marker-start:none')

        marker.append(arrow)

    def addLayer(self, name):
        attribs = {inkex.addNS('label','inkscape') : name,
                   inkex.addNS('groupmode','inkscape') : "layer",
                   'style' : simplestyle.formatStyle({"display":"inline"}),
                   }
        return inkex.etree.SubElement(self.document.getroot(), "g", attribs)

    def pointAt(self, pts, posx):

        # bisect
        reversed_ = pts[0][0]>pts[-1][0]

        lo = 0
        hi = len(pts)
        while lo < hi:
            mid = (lo+hi)//2
            if reversed_:
                if pts[mid][0] > posx:
                    lo = mid+1
                else:
                    hi = mid
            else:
                if pts[mid][0] < posx:
                    lo = mid+1
                else:
                    hi = mid
        pos = lo - 1

        d1 = posx - pts[pos][0]
        d2 = pts[pos+1][0] - posx
        dx = pts[pos+1][0] - pts[pos][0]
        pt = [posx, (pts[pos][1]*d2+pts[pos+1][1]*d1)/dx]

        return pos+1, pt

    def circle(self, diameter, npts=36):
        return [ [diameter*math.sin(2*math.pi*i/npts),
                  diameter*math.cos(2*math.pi*i/npts)] for i in xrange(npts+1)]

    def rectangle(self, dx, dy):
        x = dx/2.0
        y = dy/2.0
        return [ [0.0,  y],
                 [ -x,  y],
                 [ -x, -y],
                 [  x, -y],
                 [  x,  y],
                 [0.0,  y]]

    def renderFoil(self, naca_num, size, twist=0.0):
        l = len(naca_num)
        if l == 4:
            pts = naca.naca4(naca_num, self.options.points, False, True)
        elif l == 5:
            pts = naca.naca5(naca_num, self.options.points, False, True)
        else:
            #sys.stderr.write("Naca number must be 4 or 5 digits\n")
            return None, None

        for i, pt in enumerate(pts):
            pts[i] = list(pt)

        upper = pts[0:self.options.points]
        lower = pts[self.options.points:]

        conns_upper = []
        conns_lower = []

        beam_x = self.options.beampos/100.0

        n_up, pt_up = self.pointAt(upper, beam_x)
        n_low, pt_low = self.pointAt(lower, beam_x)
        beam_y = (pt_up[1] + pt_low[1]) / 2.0

        trans = simpletransform.composeTransform(
            simpletransform.parseTransform("rotate(%f)" % (-1*twist)),
            [[size,0.0,-beam_x*size],
             [0.0,size,-beam_y*size]])

        for pt in pts:
            simpletransform.applyTransformToPoint(trans, pt)
        for pt in pt_up, pt_low:
            simpletransform.applyTransformToPoint(trans, pt)

        if self.options.beamtype in [1,2,3,4]: # center beam
            if self.options.beamtype in [1,2]: # round
                beam = self.circle(self.options.beamwidth)
            else: # rectangular
                beam = self.rectangle(self.options.beamwidth,
                                      self.options.beamheight)

            if self.options.beamtype in [1, 3]: # from above
                bl = len(beam)
                upper = upper[:n_up] + [ pt_up ] + beam + \
                    [ pt_up ] + upper[n_up :]
                conns_upper = [n_up, n_up+1, n_up+bl, n_up+bl+1]
            else: # from below
                for pt in beam: # mirror vertically
                    pt[1] = -pt[1]
                bl = len(beam)
                lower = lower[:n_low] + [ pt_low ] + beam + \
                    [ pt_low ] + lower[n_low:]
                conns_lower = [n_low, n_low+1, n_low+bl, n_low+bl+1]

        else: # Surface beam(s)
            if self.options.beamtype in [5, 7]: # Top beam
                pass
            if self.options.beamtype in [6, 7]: # Bottom beam
                pass

        if self.options.approach <= 2: # Start with left/leading eadge
            pts = lower + upper + [lower[0]]
            conns = [0] + conns_lower + [len(lower)] + \
                [n+len(lower) for n in conns_upper] + [len(pts)-1]
        else:
            pts = upper + lower + [upper[0]]
            conns = [0] + conns_upper + [len(upper)] + \
                [n+len(upper) for n in conns_lower] + [len(pts)-1]

        return pts, conns

    def addApproach(self, pts, conns, bbox):
        xmin, ymin, xmax, ymax = bbox
        awidth = self.options.approachwidth

        direct = min(10, awidth)

        approach1 = []
        approach2 = []
        if self.options.approach <= 2: # Start with left/leading eadge
            xdirect = pts[0][0] - direct
            x = xmin - awidth
        else: # Start with right/trailing edge
            xdirect = pts[0][0] + direct
            x = xmax + awidth

        if self.options.approach in [1, 4]: # upwards
            approach1 = [[x, ymin], [xdirect, pts[0][1]]]
            approach2 = [[xdirect, pts[-1][1]], [x, ymax]]
        elif self.options.approach in [2, 5] : # downwards
            approach1 = [[x, ymax], [xdirect, pts[0][1]]]
            approach2 = [[xdirect, pts[-1][1]], [x, ymin]]

        pts = approach1 + pts + approach2
        l = len(pts)
        la1 = len(approach1)
        la2 = len(approach2)
        conns = range(la1+1) + [n+la1 for n in conns] + range(l-la2-1, l)

        return pts, conns

    def foilToSVG(self, name, pts, layer,
                  offset_x=0, offset_y=0,
                  color="#000000"):

        path = ["M"]

        for x, y in pts:
            path.append("%.3f %.3f" % (self.view_center[0]+f*(x+offset_x),
                                       self.view_center[1]-f*(y+offset_y)))

        # Embed in group
        g_attribs = {inkex.addNS('label','inkscape'):
                         'Naca foil ' + name }
        g = inkex.etree.SubElement(layer, 'g', g_attribs)

        # Create SVG Path
        style = self.style.copy()
        style["stroke"] = color
        foil_attribs = {'style':simplestyle.formatStyle(style), 'd':" ".join(path)}
        foil = inkex.etree.SubElement(g, inkex.addNS('path','svg'), foil_attribs )

    def connectionsToSVG(self, pts1, conn1, pts2, conn2, layer,
                         offset_x=0, offset_y=0):
        lines = []

        for c1, c2 in zip(conn1, conn2):
            if 1: # connection line
                x0 = self.view_center[0]
                y0 = self.view_center[1]
                x1, y1, x2, y2 = pts1[c1] + pts2[c2]
                #sys.stderr.write(repr(args))
                lines.append("M %.3f %.3f L %.3f %.3f" % (
                        x0+f*x1,
                        y0-f*y1,
                        x0+f*(offset_x+x2),
                        y0-f*(offset_y+y2)))
            else: # generate loop
                pass

        # Embed in group
        g_attribs = {inkex.addNS('label','inkscape'):
                         'Naca Foil Connections' }
        g = inkex.etree.SubElement(layer, 'g', g_attribs)

        # Create SVG Path
        style = self.constyle.copy()
        style['stroke'] = '#FF0000'
        foil_attribs = {'style':simplestyle.formatStyle(style), 'd':" ".join(lines)}
        foil = inkex.etree.SubElement(g, inkex.addNS('path','svg'), foil_attribs )

    def bbox(self, pts):
        xmin = xmax = pts[0][0]
        ymin = ymax = pts[0][1]

        for pt in pts:
            xmin = min(xmin, pt[0])
            xmax = max(xmax, pt[0])
            ymin = min(ymin, pt[1])
            ymax = max(ymax, pt[1])
        return xmin, ymin, xmax, ymax

    def effect(self):
        naca_num = self.options.naca.strip()


        foil1, connections1 = self.renderFoil(
            naca_num, self.options.size)

        if not foil1: # error
            return

        bbox = self.bbox(foil1)

        if self.options.other:
            naca_num2 = self.options.naca2.strip()
            if not re.match(r"^\d{4,5}$", naca_num2):
                naca_num2 = naca_num
            foil2, connections2 = self.renderFoil(
                naca_num2, self.options.size2,
                self.options.twist)
            if not foil2: # error
                return
            bbox2 = self.bbox(foil2)
            bbox = [min(bbox[0],bbox2[0]),
                    min(bbox[1],bbox2[1]),
                    max(bbox[2],bbox2[2]),
                    max(bbox[3],bbox2[3])]


        layers = []
        for item in self.document.getroot().getchildren():
            if (item.tag == inkex.addNS("g",'svg') and
                item.get(inkex.addNS('groupmode','inkscape')) == 'layer'):
                layers.append(item)

        if len(layers) < 1:
            layers.append(self.addLayer("XY"))
        if self.options.other and len(layers) < 2:
            layers.append(self.addLayer("UV"))
        if self.options.other and len(layers) < 3:
            layers.append(self.addLayer("Connections"))

        foil1, connections1 = self.addApproach(foil1, connections1, bbox)

        self.foilToSVG(naca_num, foil1, layers[0])

        if self.options.other:
            foil2, connections2 = self.addApproach(foil2, connections2, bbox)
            self.foilToSVG(naca_num2, foil2, layers[1],
                           color="#0000FF")
            self.connectionsToSVG(foil1, connections1,
                                  foil2, connections2, layers[2])

        self.addMarker(
            'NacaArrowStart',
            'M 0.0,0.0 L 5.0,-5.0 L -12.5,0.0 L 5.0,5.0 L 0.0,0.0 z ',
            'scale(0.8) rotate(180) translate(12.5,0)')
        self.addMarker(
            'NacaArrowEnd',
            'M 0.0,0.0 L 5.0,-5.0 L -12.5,0.0 L 5.0,5.0 L 0.0,0.0 z ',
            'scale(0.8) rotate(180) translate(12.5,0)')
        self.addMarker(
            'NacaDot',
            'M 5.0,0.0 L 0.0,5.0 L -5.0,0.0 L 0.0,-5.0 z ')

if __name__ == '__main__':
    e = Naca()
    e.affect()


# vim: expandtab shiftwidth=4 tabstop=8 softtabstop=4 encoding=utf-8 textwidth=99
