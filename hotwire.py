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

from pprint import pprint

def distances(points):
    """Calculate the distances for a list of points
    :param points:	iterable of float pairs
    :return:		list of distance
    """
    if not points:
        return [0]
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
       returns two arrays of points with the same number of points"""

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

    points1[:] = new1
    points2[:] = new2

def _removePath(d, p):
    d[p[0]].remove(p)
    if not d[p[0]]:
        del d[p[0]]
    d[p[-1]].remove(p)
    if not d[p[-1]]:
        del d[p[-1]]

def sortPaths(paths):
    #pprint(paths, sys.stderr)
    if not paths:
        return []
    if len(paths) == 1:
        return [paths[0]]

    ends = {}
    for p in paths:
        if len(p) == 1:
            continue
        if len(p) == 2 and p[0] == p[1]:
            continue
        ends.setdefault(p[0], []).append(p)
        ends.setdefault(p[-1], []).append(p)


    newpaths = []
    pos = 0
    for end, endlist in ends.iteritems():
        if (len(endlist) % 2):
            p = endlist[0]
            newpaths.append(p)
            if p[-1] == end:
                p.reverse()
            _removePath(ends, p)
            break
    else:
        newpaths.append(paths[0])
        _removePath(ends, paths[0])

    while ends:
        if not newpaths[pos][-1] in ends:
            ### look for new loop
            for n, p in enumerate(newpaths):
                if p[-1] in ends:
                    pos = n
                    break
            else:
                # error, no continuous path found
                break
        p2 = ends[newpaths[pos][-1]][0]
        if p2[-1] == newpaths[pos][-1]:
            p2.reverse()
        pos += 1
        newpaths.insert(pos, p2)
        _removePath(ends, p2)

    #pprint(newpaths, sys.stderr)
    return newpaths

def mergePaths(paths):
    result = paths[0]
    for p in paths[1:]:
        result.extend(p[1:])
    return result

def getPaths(layer,flat=1.0):
    "return list of lists of float pairs"
    paths = []
    for item in layer.getchildren():
        if item.tag == inkex.addNS('g', 'svg'):
            for i in item.getchildren():
                if i.tag == inkex.addNS('path','svg'):
                    paths.append(Path(i, flat))
        if item.tag == inkex.addNS('path','svg'):
            paths.append(Path(item, flat))
    return paths

def projectToOuterPlane(z_xy, p_xy, z_uv, p_uv, width):
    """front cutting plane at z==0
       back cutting plane at z==width"""
    x, y = p_xy
    u, v = p_uv
    d1 = float(z_xy)
    d2 = float(z_uv - z_xy)
    d3 = float(width - p_uv)
    p_xy = [ x + d1*(x-u)/d2, y + d1*(y-v)/d2 ]
    p_uv = [ u + d3*(u-x)/d2, V + d3*(v-y)/d2 ]

    return p_xy, p_uv

class Path(list):

    def __init__(self, tag, flatness):
        self.tag = tag
        self._readPath(tag, flatness)

    def _readPath(self, item, flat):
        p = cubicsuperpath.parsePath(item.get('d'))
        cspsubdiv.cspsubdiv(p, flat)
        subpaths = []
        for sp in p:
            sps = []
            subpaths.append(sps)
            for c0, c1, c2 in sp:
                sps.append(tuple(c2))
 
        self[:] = mergePaths(sortPaths(subpaths))

class HotWire(inkex.Effect):
    def __init__(self):
        inkex.Effect.__init__(self)
        self.OptionParser.add_option("--main",
                                     action="store", type="string",
                                     dest="main")
        self.OptionParser.add_option("--flatness",
                        action="store", type="float", 
                        dest="flat", default='1.0',
                        help="How strong are bends allowed when converting splines to lines")
        self.OptionParser.add_option("--cspeed", action="store", type="float",
                                     dest="cspeed", default=400.0)
        self.OptionParser.add_option("--mspeed", action="store", type="float",
                                     dest="mspeed", default=400.0)

        self.OptionParser.add_option("--ccorrection", action="store",
                                     type="int",
                                     dest="ccorrection", default=0)
        self.OptionParser.add_option("--cdiam", action="store", type="float",
                                     dest="cdiam", default=1.0)

        self.OptionParser.add_option("-d", "--directory",
                                     action="store", type="string",
                                     dest="directory", default="$HOME/Desktop",
                                     help="Directory for gcode file")
        self.OptionParser.add_option("-f", "--filename",
                                     action="store", type="string",
                                     dest="file", default="hotwire.txt",
                                     help="File name")			
        self.OptionParser.add_option("--add-numeric-suffix-to-filename",
                                     action="store", type="inkbool",
                                     dest="add_numeric_suffix_to_filename",
                                     default=True,help="Add numeric suffix to filename")		

        self.OptionParser.add_option("--twosided", type="inkbool", action="store",
                                     dest="twosided", default=False)
        self.OptionParser.add_option("--mwidth", type="float", action="store",
                                     dest="mwidth", default=800.0)
        self.OptionParser.add_option("--xyplane", type="float", action="store",
                                     dest="xyplane", default=0.0)
        self.OptionParser.add_option("--uvplane", type="float", action="store",
                                     dest="uvplane", default=100.0)


    def effect(self):

        root = self.document.getroot()
        layers = []
        for item in root.getchildren():
            if item.tag == inkex.addNS("g",'svg') and item.get(inkex.addNS('groupmode','inkscape')) == 'layer':
                layers.append(item)

        if len(layers) == 0:
            # XX error message
            return
        
        path1 = sortPaths(getPaths(layers[0], self.options.flat))
        path2 = None

        if len(layers) >= 2:
            path2 = sortPaths(getPaths(layers[1], self.options.flat))

        if not path2:
            path2 = path1
        else:
            if len(path1) != len(path2):
                # XXX Error message
                return
            for i in range(len(path1)):
                alignLinePaths(path1[i], path2[i])

        directory = self.options.directory
        if directory.startswith("$HOME"):
            directory = "/home/" + os.getenv('USERNAME') + directory[5:]

        outfile_orig = outfile = os.path.join(directory, self.options.file)

        # put number before file name extension
        outfile_orig = outfile_orig.rsplit(".", 1)
        if len(outfile_orig) == 2:
            outfile_orig = ".%i.".join(outfile_orig)
        else:
            outfile_orig = outfile_orig[0] + ".%i"

        i = 0
        while os.path.exists(outfile) and self.options.add_numeric_suffix_to_filename:
            i += 1
            outfile = outfile_orig % i

        f = open(outfile, "w")

        f.write("""%%
G21 (use mm)
F%.0f (Speed)
""" % min(self.options.cspeed, self.options.mspeed))

        cd = self.options.cdiam
        f.write(["G40", "G42 D%.2f" % cd, "G41 D%.2f" % cd][self.options.ccorrection])
        f.write("\n\n")

        s = 1 / 3.5433071 # scale svg units to mm

        for p1, p2 in zip(path1, path2):
            if not p1:
                continue
            # sys.stderr.write("%s %s\n" % (repr(p1), repr(p2)))
            #p1, p2 = alignLinePaths(p1, p2)
            # XXX projection to outer planes
            for i in xrange(len(p1)):
                x, y = p1[i]
                u, v = p2[i]
                x, y = s*x, (1052.3622-y)*s
                u, v = s*u, (1052.3622-v)*s
                # reverse Y and V axis to go from svg to inkscape coordinates
                f.write("G01 X%7.2f Y%7.2f U%7.2f V%7.2f\n" % (x, y, u, v))
        f.write("""
M30 (End Program)
%
""")
        f.close()

if __name__ == '__main__':
    e = HotWire()
    e.affect()


# vim: expandtab shiftwidth=4 tabstop=8 softtabstop=4 encoding=utf-8 textwidth=99
