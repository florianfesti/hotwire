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

import inkex
import cubicsuperpath, bezmisc, cspsubdiv

def distances(points):
    lastpt = points[0]
    dists = []
    for pt in points[1:]:
        dists.append(bezmisc.pointdistance(lastpt, pt))
        lastpt = pt
    return dists

def intermediatePoint(pt1, pt2, relDist=0.5):
    q = relDist
    r = 1 - relDist 
    return [pt1[0]*r + pt2[0]*q, pt1[1]*r + pt2[1]*q]

def alignLinePaths(points1, points2):
    """Takes two arrays of (x, y) points
       returns two arrays of point swith the same number of points"""

    dists1 = distances(points1)
    dists1.append(0.0)
    lenght1 = sum(dists1)
    dists2 = distances(points2)
    dists2.append(0.0)
    lenght2 = sum(dists2)
    f = lenght1/lenght2 # XXX factor that points2 moves faster that points1

    new1 = [points1[0]]
    new2 = [points2[0]]
    idx1 = 1
    idx2 = 1
    l1 = 0.0
    l2 = 0.0
    ln1 = dists1[0]
    ln2 = f * dists2[0]
    while idx1 < (len(points1)) and idx2 < (len(points2)):
        if abs(ln1-ln2) < 0.5: # both point match
            # Add Point1
            l1 = ln1
            new1.append(points1[idx1])
            ln1 = l1 + dists1[idx1]
            idx1 += 1
            # Add Point2
            l2 = ln2
            new2.append(points2[idx2])
            ln2 = l2 + f * dists2[idx2]
            idx2 += 1
        elif ln1 < ln2:            
            # Add Point1
            l1 = ln1
            new1.append(points1[idx1])
            ln1 = l1 + dists1[idx1]
            idx1 += 1

            # add intermediate point to 2
            reldist = (l1-l2)/(ln2-l2)
            new2.append(intermediatePoint(new2[-1], points2[idx2], reldist))
            l2 = l1
        else:
            # Add Point2
            l2 = ln2
            new2.append(points2[idx2])
            ln2 = l2 + f * dists2[idx2]
            idx2 += 1

            # add intermediate point to 1
            reldist = (l2-l1)/(ln1-l1)
            new1.append(intermediatePoint(new1[-1], points1[idx1], reldist))
            l1 = l2
    # check for remaining points
    if idx1 < len(points1) or idx2 < len(points2):
        new1.append(points1[-1])
        new2.append(points2[-1])
    return new1, new2
                    

def getPath(layer,flat=1.0):
    points = []
    for item in layer.getchildren():
        if item.tag == inkex.addNS('path','svg'):
            p = cubicsuperpath.parsePath(item.get('d'))
            cspsubdiv.cspsubdiv(p, flat)
                
            for sp in p:
                points += [c2 for (c0, c1, c2) in sp]
    return points

def getConnectors(layer):
    result = []
    for item in layer.getchildren():
        if item.tag == inkex.addNS('path','svg'):
            p = cubicsuperpath.parsePath(item.get('d'))
            for sp in p:
                result.append([ sp[0][1],sp[-1][1] ])
    return result


def splitPath(path, connectors):
    result = []
    for n, pt in enumerate(path):
        for m, (pt1, pt2) in enumerate(connectors):
            if ((bezmisc.pointdistance(pt, pt1)<0.1) or
                (bezmisc.pointdistance(pt, pt2)<0.1)):
                result.append((n, m))
    result.append((len(path)-1, -1))
    return result

def splitPaths(path1, path2, connectors):
    if not connectors:
        return [path1, ], [path2, ]

    cuts1 = splitPath(path1, connectors)
    cuts2 = splitPath(path2, connectors)
                      
    # XXX checks
    if len(cuts1) != len(cuts2):
        sys.stderr.write("Error: XY split %i times while UV split %i times.\n\t Check connection paths!\n" %
                         (len(cuts1), len(cuts2)))
        return None, None
    for (npt1, nc1), (npt2, nc2) in zip(cuts1, cuts2):
        if nc1 != nc2:
            sys.stderr.write("Error: Connections are not in the same order for both paths")
            return None, None

    paths1 = []
    last = 0
    for cut in cuts1:
        paths1.append(path1[last:cut[0]+1])
        last = cut[0]

    paths2 = []
    last = 0
    for cut in cuts2:
        paths2.append(path2[last:cut[0]+1])
        last = cut[0]

    return paths1, paths2

class HotWire(inkex.Effect):
    def __init__(self):
        inkex.Effect.__init__(self)
        self.OptionParser.add_option("--flatness",
                        action="store", type="float", 
                        dest="flat", default='1.0',
                        help="How strong are bends allowed when converting splines to lines")
        self.OptionParser.add_option("-d", "--directory",
                                     action="store", type="string",
                                     dest="directory", default="$HOME/Desktop",
                                     help="Directory for gcode file")
        self.OptionParser.add_option("-f", "--filename",
                                     action="store", type="string",
                                     dest="file", default="hotwire.txt",
                                     help="File name")			
        self.OptionParser.add_option("",   "--add-numeric-suffix-to-filename",
                                     action="store", type="inkbool",
                                     dest="add_numeric_suffix_to_filename",
                                     default=True,help="Add numeric suffix to filename")		

    def effect(self):

        root = self.document.getroot()
        layers = []
        for item in root.getchildren():
            if item.tag == inkex.addNS("g",'svg') and item.get(inkex.addNS('groupmode','inkscape')) == 'layer':
                layers.append(item)

        if len(layers) == 0:
            # XX error message
            return
        
        path1 = getPath(layers[0], self.options.flat)

        if len(layers) >= 2:
            path2 = getPath(layers[1], self.options.flat)
        if len(layers) >= 3:
            connectors = getConnectors(layers[2])
        else:
            connectors = []

        if not path2:
            path1 = [path1]
            path2 = path1
        else:
            path1, path2 = splitPaths(path1, path2, connectors)

        if path1 is None: # error in splitPaths
            return

        directory = self.options.directory
        if directory.startswith("$HOME"):
            directory = "/home/" + os.getenv('USERNAME') + directory[5:]
        i = 0
        
        outfile_orig = outfile = os.path.join(directory, self.options.file)
        while os.path.exists(outfile):
            i += 1
            outfile = outfile_orig + (".%i" % i)

        f = open(outfile, "w")

        for p1, p2 in zip(path1, path2):
            p1, p2 = alignLinePaths(p1, p2)
            # XXX projection to outer planes
            for i in xrange(len(p1)):
                x, y = p1[i]
                u, v = p2[i]
                # reverse Y and V axis to go from svg to inkscape coordinates
                f.write("G01 X%7.2f Y%7.2f U%7.2f V%7.2f\n" % (x, 1052.3622-y, u, 1052.3622-v))
        f.close()

if __name__ == '__main__':
    e = HotWire()
    e.affect()


# vim: expandtab shiftwidth=4 tabstop=8 softtabstop=4 encoding=utf-8 textwidth=99
