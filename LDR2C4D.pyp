import c4d
import os
import struct
import platform

from c4d import bitmaps, gui, plugins, documents, utils

PLUGIN_ID = 1040042
LDRAWPATH = 1000
RESOLUTION = 1001
LOGO = 1002
OPTIMIZE = 1003
SMOTH = 1004

IDC_LDRAWPATH = 1010
IDC_ABOUT = 1011
IDC_SETPATH = 1012
IDC_LOAD = 1013
IDC_COMBO = 1014
IDC_LOGO = 1015
IDC_OPTIMIZE = 1016
IDC_SMOTH = 1017

COMBO_LOW = 1021
COMBO_STD = 1022
COMBO_HIH = 1023

FILEMANAGER = None
LDRAWCOLORS = None

VERSION = '1.0.3'

print("- - - - - - - - - - - -")
print("           _           ")
print("          [_]          ")
print("       / |   | \\       ")
print("      () '---'  C      ")
print("        |  |  |        ")
print("        [=|=]          ")
print("                       ")
print("LDR2C4D - " + VERSION)
print("- - - - - - - - - - - -")

FLIP = c4d.Matrix(c4d.Vector(0, 0, 0), c4d.Vector(1, 0, 0), c4d.Vector(0, -1, 0), c4d.Vector(0, 0, 1))

CURRENTSPINN = 0
SPINNSTRING = ['¦','/','–','\\']

def spinner():
    global CURRENTSPINN,SPINNSTRING
    if CURRENTSPINN < len(SPINNSTRING) - 1:
        CURRENTSPINN += 1
    else:
        CURRENTSPINN = 0

    return SPINNSTRING[CURRENTSPINN]

def generate(ld,matrix,currentColor,doc,parent,optimizesettings,optimize,smoth):
    global FILEMANAGER

    if (ld is not None):

        if ld.isPart == True:

            c4d.StatusSetText('Generate Part: {0} ({1}) [{2}]'.format(ld.Partname, ld.Name, spinner()))

            Mesh = MeshFiller(optimize)
            Mesh.partToMesh(ld,FLIP)
            #Mesh.computeFaceNormals()
    
            if len(Mesh.verticesArray) > 0:

                obj = c4d.PolygonObject(len(Mesh.verticesArray), len(Mesh.polygons))
                obj.SetName(ld.Partname)
                obj.SetAllPoints(Mesh.verticesArray)

                #Faces and Colors
                colortags = {}
                basecolor = LDRAWCOLORS.getColorbyID(currentColor)
                mat = buildMaterial(doc,basecolor)
                textag = c4d.TextureTag()
                textag.SetMaterial(mat)
                textag.SetParameter( c4d.TEXTURETAG_RESTRICTION, basecolor.name, c4d.DESCFLAGS_SET_0)
                obj.InsertTag(textag)

                selp = c4d.SelectionTag(c4d.Tpolygonselection) 
                selp.SetParameter( c4d.ID_BASELIST_NAME, basecolor.name, c4d.DESCFLAGS_SET_0)
                colortags[basecolor.name] = selp
                bs = selp.GetBaseSelect()

                faceOffset = 0
                for face in Mesh.polygons:
                    fc = Mesh.facecolors[faceOffset]

                    #has face other color as part
                    if currentColor != fc and not (fc == 16 or fc == 24):
                        facecolor = LDRAWCOLORS.getColorbyID(fc)
                        if facecolor.name in colortags:
                            fs = colortags[facecolor.name].GetBaseSelect()
                            fs.Select(faceOffset)
                        else:
                            facemat = buildMaterial(doc,facecolor)
                            facetextag = c4d.TextureTag()
                            facetextag.SetMaterial(facemat)
                            facetextag.SetParameter(c4d.TEXTURETAG_RESTRICTION, facecolor.name, c4d.DESCFLAGS_SET_0)
                            obj.InsertTag(facetextag)

                            faceselp = c4d.SelectionTag(c4d.Tpolygonselection)
                            faceselp[c4d.ID_BASELIST_NAME] = facecolor.name
                            colortags[facecolor.name] = faceselp
                            fs = faceselp.GetBaseSelect()
                            fs.Select(faceOffset)
                    else:
                        bs.Select(faceOffset)

                    obj.SetPolygon(faceOffset,face)

                    faceOffset += 1

                #add Polygon selection
                for key in colortags:
                    if colortags[key].GetBaseSelect().GetCount() > 0:
                        obj.InsertTag(colortags[key])

                if smoth == True:
                    if FILEMANAGER.Quality == COMBO_LOW:
                        obj.SetPhong(True, True, c4d.utils.Rad(46))
                    else:
                        obj.SetPhong(True, True, c4d.utils.Rad(40))

#test
#                for pair in Mesh.lines:
#                    outputSpline = c4d.BaseObject(c4d.Ospline) 
#                    outputSpline.ResizeObject(len(pair))
#                    outputSpline.SetAllPoints(pair)
#                    outputSpline.InsertUnder(obj)
#                    outputSpline.Message(c4d.MSG_UPDATE)
                
#                for pair in Mesh.condlines:
#                    outputSpline = c4d.BaseObject(c4d.Ospline) 
#                    outputSpline.ResizeObject(len(pair))
#                    outputSpline.SetAllPoints(pair)
#                    outputSpline.InsertUnder(obj)
#                    outputSpline.Message(c4d.MSG_UPDATE)


                obj.SetMg(FLIP * matrix * FLIP)

                if optimize == True:
                    c4d.utils.SendModelingCommand(c4d.MCOMMAND_OPTIMIZE, [obj], c4d.MODIFY_ALL, optimizesettings, doc)

                obj.InsertUnder(parent)
                obj.Message(c4d.MSG_UPDATE)

        else:

            if len(ld.Subparts) > 0:

                newnode = c4d.BaseObject(c4d.Onull)
                newnode[c4d.NULLOBJECT_DISPLAY] = c4d.NULLOBJECT_DISPLAY_NONE
                newnode.SetName(ld.Partname)      
                newnode.SetMg(FLIP * matrix * FLIP) 

                for sp in ld.Subparts:
                    generate(sp.Subpart, sp.Matrix , currentColor if sp.Color == 16 or sp.Color == 24 else sp.Color ,doc, newnode , optimizesettings , optimize , smoth)
                
                doc.InsertObject(newnode , parent)

class MeshFiller(object):

    def __init__(self,optimize):
        self.verticesMap = {}
        self.edgeMap = {}
        self.lines = []
        self.condlines = []
        self.verticesArray = []
        self.facecolors = []
        self.facenormals = []
        self.polygons = []
        self.normals = []
        self.inverting = False
        self.optimize = optimize

    def addVertice(self,v):
        res = 0
        if self.optimize == True:
            key = str(int(round(v.x * 100))) + "_" + str(int(round(v.y * 100))) + "_" + str(int(round(v.z * 100)))
            if key in self.verticesMap:
                res = self.verticesMap[key]
            else:
                res = len(self.verticesArray)
                self.verticesMap[key] = res
                self.verticesArray.append(v)
        else:
            res = len(self.verticesArray)
            self.verticesArray.append(v)
        return res

    def partToMesh(self,part,matrix):
        part.fillMesh(matrix, 16, self)

    def addFace3(self,ccw,certified,det,color,v0,v1,v2):
        if not certified == True:
            self.addFace3(False,True,det,color,v2, v1, v0)
            ccw = True
        flip = self.inverting ^ (det < 0) ^ (not ccw)
        self.polygons.append(
            c4d.CPolygon( 
                self.addVertice(v2 if flip == True else v0),
                self.addVertice(v1),
                self.addVertice(v0 if flip == True else v2)
            ) 
        )
        self.facecolors.append(color)

    def addFace4(self,ccw,certified,det,color,v0,v1,v2,v3):
        if not certified == True:
            self.addFace4(False,True,det,color,v2, v1, v0, v3)
            ccw = True
        flip = self.inverting ^ (det < 0) ^ (not ccw)
        self.polygons.append(
            c4d.CPolygon(
                self.addVertice(v2 if flip == True else v0),
                self.addVertice(v1),
                self.addVertice(v0 if flip == True else v2),
                self.addVertice(v3)
            )
        )
        self.facecolors.append(color)

    def addLine(self,v0,v1,color):
#        self.lines.append([v0,v1])
        pass

    def addCondLine(self,v0,v1,v2,v3):
#        key = self.edgeMapKey(self.addVertice(v1),self.addVertice(v2))
#        self.edgeMap[key] = []  # add empy array, later this will be filled by faces sharing this edge
        pass

#    def edgeMapKey(self,idx1,idx2):
#        return str(min(idx1,idx2)) + ":" + str(max(idx1,idx2))
#
#    def computeFaceNormals(self):
#        cb = c4d.Vector(0,0,0)
#        ab = c4d.Vector(0,0,0)
#        for face in self.polygons:
#            vA = self.verticesArray[face.a]
#            vB = self.verticesArray[face.b]
#            vC = self.verticesArray[face.c]
#            cb = vC - vB 
#            ab = vA - vB
#            cb = cb.Cross(ab)
#            cb.Normalize()
#            self.facenormals.append(cb)

#    def smooth


class FileManager(object):

    def __init__(self,LdrawDir,SceneDir, _Quality=COMBO_STD, _LOGO = False):
        self._PartCache = {}
        self._FileCache = {}
        self.PathList = []
        self.LdrawPath = LdrawDir
        self.ScenePath = SceneDir
        self.Quality = _Quality
        self.useLogo = _LOGO
        
        self.PathList.append(os.path.dirname(SceneDir))
        self.PathList.append(self.LdrawPath)

        if os.path.exists(os.path.join(self.LdrawPath, "models")):        
            self.PathList.append(os.path.join(self.LdrawPath, "models"))

        if os.path.exists(os.path.join(self.LdrawPath, "unofficial")):
            self.PathList.append(os.path.join(self.LdrawPath, "unofficial", "parts"))

            if self.Quality == COMBO_HIH and os.path.exists(os.path.join(self.LdrawPath,  "unofficial", "p", "48")):
                self.PathList.append(os.path.join(self.LdrawPath, "unofficial", "p", "48"))

            elif self.Quality == COMBO_LOW and os.path.exists(os.path.join(self.LdrawPath,  "unofficial", "p", "8")):
                self.PathList.append(os.path.join(self.LdrawPath,"unofficial", "p", "8"))
            
            if os.path.exists(os.path.join(self.LdrawPath,  "unofficial", "p")):
                self.PathList.append(os.path.join(self.LdrawPath, "unofficial", "p"))

            if os.path.exists(os.path.join(self.LdrawPath,  "unofficial", "lsynth")):
                self.PathList.append(os.path.join(self.LdrawPath, "unofficial", "lsynth"))

        if os.path.exists(os.path.join(self.LdrawPath, "lsynth")):
            self.PathList.append(os.path.join(self.LdrawPath, "lsynth"))

        if os.path.exists(os.path.join(self.LdrawPath, "parts")):
            self.PathList.append(os.path.join(self.LdrawPath, "parts"))

        if self.Quality == COMBO_HIH and os.path.exists(os.path.join(self.LdrawPath, "p","48")):
            self.PathList.append(os.path.join(self.LdrawPath, "p", "48"))

        elif self.Quality == COMBO_LOW and os.path.exists(os.path.join(self.LdrawPath, "p","8")):
            self.PathList.append(os.path.join(self.LdrawPath, "p", "8"))

        if os.path.exists(os.path.join(self.LdrawPath, "p")):
            self.PathList.append(os.path.join(self.LdrawPath, "p"))

        # use logo insert files to filecache
        if self.useLogo == True and self.Quality != COMBO_LOW and self.Quality != COMBO_HIH:
            self._FileCache['stud.dat'] = ['0 Stud with LEGO Logo - 3D with Sharp Top','0 Name: stud-logo3.dat','0 Author: J.C. Tchang [tchang]','0 !LDRAW_ORG Unofficial_Primitive','0 !LICENSE Redistributable under CCAL version 2.0 : see CAreadme.txt','0 BFC CERTIFY CCW','0 !HISTORY 2010-06-21 [tchang]  New Primitive','0 !HISTORY 2014-01-02 [Steffen] uploaded to parts tracker','1 16 0 0 0 6 0 0 0 1 0 0 0 6 4-4edge.dat','1 16 0 0 0 6 0 0 0 -3.4 0 0 0 6 4-4cyli.dat','1 16 0 -3.4 0 5.6 0 0 0 -5.6 0 0 0 5.6 t01o0714.dat','1 16 0 -3.8 0 5.6 0 0 0 1 0 0 0 5.6 4-4disc.dat','1 16 0 -3.8 0 1 0 0 0 1 0 0 0 1 logo3.dat']
            self._FileCache['logo3.dat'] = ['0 LEGO Logo for Studs - 3D with Sharp Top','0 Name: logo3.dat','0 Author: J.C. Tchang [tchang]','0 !LDRAW_ORG Unofficial_Primitive','0 !LICENSE Redistributable under CCAL version 2.0 : see CAreadme.txt','0 BFC CERTIFY CCW','0 !HISTORY 2010-06-21 [tchang]  New Primitive','0 !HISTORY 2014-01-02 [Steffen] uploaded to parts tracker','1 16 2.25 -0.2 -3.3 0.25 0 0 0 0.2 0 0 0 0.25 2-4cylc.dat','1 16 -1.95 -0.2 -3.5 0 0 -0.25 0 0.2 0 0.25 0 0 2-4cylc.dat','1 16 2.25 -0.2 -4.4 0 0 0.25 0 0.2 0 -0.25 0 0 1-4cylc.dat','4 16 2.5 -0.2 -4.4 2.5 -0.2 -3.3 2 -0.2 -3.3 2.25 -0.2 -4.4','4 16 2.25 -0.2 -4.4 -1.95 -0.2 -3.25 -1.95 -0.2 -3.75 2.25 -0.2 -4.65','3 16 2 -0.2 -4.15 -1.95 -0.2 -3.25 2.25 -0.2 -4.4','3 16 2.25 -0.2 -4.4 2 -0.2 -3.3 2 -0.2 -4.15','2 24 2.5 -0.2 -4.4 2.5 -0.2 -3.3','2 24 2.5 0 -4.4 2.5 0 -3.3','4 16 2.5 0 -4.4 2.5 0 -3.3 2.5 -0.2 -3.3 2.5 -0.2 -4.4','2 24 -1.95 -0.2 -3.75 2.25 -0.2 -4.65','2 24 -1.95 0 -3.75 2.25 0 -4.65','4 16 -1.95 0 -3.75 2.25 0 -4.65 2.25 -0.2 -4.65 -1.95 -0.2 -3.75','2 24 2 -0.2 -4.15 -1.95 -0.2 -3.25','2 24 2 0 -4.15 -1.95 0 -3.25','4 16 2 0 -4.15 -1.95 0 -3.25 -1.95 -0.2 -3.25 2 -0.2 -4.15','2 24 2 -0.2 -3.3 2 -0.2 -4.15','2 24 2 0 -3.3 2 0 -4.15','4 16 2 0 -3.3 2 0 -4.15 2 -0.2 -4.15 2 -0.2 -3.3','2 24 2 -0.2 -4.15 2 0 -4.15','1 16 -1.95 -0.2 -0.2 0.25 0 0 0 0.2 0 0 0 0.25 2-4cylc.dat','1 16 0.1 -0.2 -1.1 0.25 0 0 0 0.2 0 0 0 0.25 2-4cylc.dat','1 16 2.25 -0.2 -1.2 0.25 0 0 0 0.2 0 0 0 0.25 2-4cylc.dat','1 16 -1.95 -0.2 -1.3 -0.25 0 0 0 0.2 0 0 0 -0.25 1-4cylc.dat','1 16 2.25 -0.2 -2.3 0 0 0.25 0 0.2 0 -0.25 0 0 1-4cylc.dat','4 16 2.25 -0.2 -2.3 2.5 -0.2 -2.3 2.5 -0.2 -1.2 2 -0.2 -1.2','4 16 -0.15 -0.2 -1.55 0.35 -0.2 -1.65 0.35 -0.2 -1.1 -0.15 -0.2 -1.1','4 16 2.25 -0.2 -2.55 0.35 -0.2 -1.65 -0.15 -0.2 -1.55 -1.95 -0.2 -1.55','4 16 0.35 -0.2 -1.65 2.25 -0.2 -2.55 2.253 -0.2 -2.3 2 -0.2 -2.05','3 16 2 -0.2 -2.05 2.25 -0.2 -2.3 2 -0.2 -1.2','4 16 -1.7 -0.2 -0.2 -2.2 -0.2 -0.2 -2.2 -0.2 -1.3 -1.95 -0.2 -1.3','4 16 -1.7 -0.2 -1.15 -1.95 -0.2 -1.3 -1.95 -0.2 -1.55 -0.15 -0.2 -1.55','3 16 -1.95 -0.2 -1.3 -1.7 -0.2 -1.15 -1.7 -0.2 -0.2','2 24 2.5 -0.2 -2.3 2.5 -0.2 -1.2','2 24 2.5 0 -2.3 2.5 0 -1.2','4 16 2.5 0 -2.3 2.5 0 -1.2 2.5 -0.2 -1.2 2.5 -0.2 -2.3','2 24 0.35 -0.2 -1.65 0.35 -0.2 -1.1','2 24 0.35 0 -1.65 0.35 0 -1.1','2 24 0.35 0 -1.65 0.35 -0.2 -1.65','4 16 0.35 0 -1.65 0.35 0 -1.1 0.35 -0.2 -1.1 0.35 -0.2 -1.65','2 24 -0.15 -0.2 -1.55 -0.15 -0.2 -1.1','2 24 -0.15 0 -1.55 -0.15 0 -1.1','2 24 -0.15 -0.2 -1.55 -0.15 0 -1.55','4 16 -0.15 -0.2 -1.55 -0.15 -0.2 -1.1 -0.15 0 -1.1 -0.15 0 -1.55','2 24 2.25 -0.2 -2.55 -1.95 -0.2 -1.55','2 24 2.25 0 -2.55 -1.95 0 -1.55','4 16 2.25 -0.2 -2.55 -1.95 -0.2 -1.55 -1.95 0 -1.55 2.25 0 -2.55','2 24 0.35 -0.2 -1.65 2 -0.2 -2.05','2 24 0.35 0 -1.65 2 0 -2.05','4 16 0.35 -0.2 -1.65 2 -0.2 -2.05 2 0 -2.05 0.35 0 -1.65','2 24 2 -0.2 -2.05 2 -0.2 -1.2','2 24 2 0 -2.05 2 0 -1.2','2 24 2 -0.2 -2.05 2 0 -2.05','4 16 2 -0.2 -2.05 2 -0.2 -1.2 2 0 -1.2 2 0 -2.05','2 24 -2.2 -0.2 -0.2 -2.2 -0.2 -1.3','2 24 -2.2 0 -0.2 -2.2 0 -1.3','4 16 -2.2 0 -0.2 -2.2 0 -1.3 -2.2 -0.2 -1.3 -2.2 -0.2 -0.2','2 24 -1.7 -0.2 -1.15 -0.15 -0.2 -1.55','2 24 -1.7 0 -1.15 -0.15 0 -1.55','4 16 -1.7 -0.2 -1.15 -0.15 -0.2 -1.55 -0.15 0 -1.55 -1.7 0 -1.15','2 24 -1.7 -0.2 -1.15 -1.7 -0.2 -0.2','2 24 -1.7 0 -1.15 -1.7 0 -0.2','2 24 -1.7 -0.2 -1.15 -1.7 0 -1.15','4 16 -1.7 0 -1.15 -1.7 0 -0.2 -1.7 -0.2 -0.2 -1.7 -0.2 -1.15','1 16 -1.2 -0.2 1.2 0.1294 0 -0.483 0 1 0 0.483 0 0.1294 2-4ring1.dat','1 16 -1.2 -0.2 1.2 0.1294 0 -0.483 0 1 0 0.483 0 0.1294 2-4edge.dat','1 16 -1.2 -0.2 1.2 0.258819 0 -0.965926 0 1 0 0.965926 0 0.258819 2-4edge.dat','1 16 -1.2 -0.2 1.2 0.258819 0 -0.965926 0 0.2 0 0.965926 0 0.258819 2-4cyli.dat','1 16 -1.2 0 1.2 0.258819 0 -0.965926 0 1 0 0.965926 0 0.258819 2-4edge.dat','0 BFC INVERTNEXT','1 16 -1.2 -0.2 1.2 0.1294 0 -0.483 0 0.2 0 0.483 0 0.1294 2-4cyli.dat','1 16 -1.2 0 1.2 0.1294 0 -0.483 0 1 0 0.483 0 0.1294 2-4edge.dat','1 16 1.5 -0.2 0.5 -0.1294 0 0.483 0 0.5 0 -0.483 0 -0.1294 2-4ring1.dat','1 16 1.5 -0.2 0.5 -0.1294 0 0.483 0 1 0 -0.483 0 -0.1294 2-4edge.dat','1 16 1.5 -0.2 0.5 -0.258819 0 0.965926 0 1 0 -0.965926 0 -0.258819 2-4edge.dat','1 16 1.5 -0.2 0.5 -0.258819 0 0.965926 0 0.2 0 -0.965926 0 -0.258819 2-4cyli.dat','1 16 1.5 0 0.5 -0.258819 0 0.965926 0 1 0 -0.965926 0 -0.258819 2-4edge.dat','0 BFC INVERTNEXT','1 16 1.5 -0.2 0.5 -0.1294 0 0.483 0 0.2 0 -0.483 0 -0.1294 2-4cyli.dat','1 16 1.5 0 0.5 -0.1294 0 0.483 0 1 0 -0.483 0 -0.1294 2-4edge.dat','1 16 0.1 -0.2 0.85 -0.25 0 0 0 0.2 0 0 0 -0.25 2-4cylc.dat','1 16 0.1 -0.2 1.6 0 0 -0.25 0 0.2 0 0.25 0 0 1-4cylc.dat','1 16 -1.006 -0.2 1.924 -0.0647 0 0.2415 0 0.2 0 -0.2415 0 -0.0647 2-4cylc.dat','4 16 -1.3294 -0.2 0.717 -1.4588 -0.2 0.2341 1.2412 -0.2 -0.4659 1.3706 -0.2 0.017','4 16 0.1 -0.2 1.6 -0.15 -0.2 1.6 -0.15 -0.2 0.85 0.35 -0.2 0.85','4 16 0.1 -0.2 1.6 1.6294 -0.2 0.983 1.7588 -0.2 1.4659 0.1 -0.2 1.85','3 16 0.1 -0.2 1.6 0.35 -0.2 0.85 0.35 -0.2 1.35','3 16 0.1 -0.2 1.6 0.35 -0.2 1.35 1.6294 -0.2 0.983','2 24 -1.4588 -0.2 0.2341 1.2412 -0.2 -0.4659','2 24 -1.4588 0 0.2341 1.2412 0 -0.4659','4 16 -1.4588 0 0.2341 1.2412 0 -0.4659 1.2412 -0.2 -0.4659 -1.4588 -0.2 0.2341','2 24 -1.3294 -0.2 0.717 1.3706 -0.2 0.017','2 24 -1.3294 0 0.717 1.3706 0 0.017','4 16 -1.3294 -0.2 0.717 1.3706 -0.2 0.017 1.3706 0 0.017 -1.3294 0 0.717','2 24 -0.15 -0.2 1.6 -0.15 -0.2 0.85','2 24 -0.15 0 1.6 -0.15 0 0.85','4 16 -0.15 0 1.6 -0.15 0 0.85 -0.15 -0.2 0.85 -0.15 -0.2 1.6','2 24 1.7588 -0.2 1.4659 0.1 -0.2 1.85','2 24 1.7588 0 1.4659 0.1 0 1.85','4 16 1.7588 0 1.4659 0.1 0 1.85 0.1 -0.2 1.85 1.7588 -0.2 1.4659','2 24 0.35 -0.2 0.85 0.35 -0.2 1.35','2 24 0.35 0 0.85 0.35 0 1.35','2 24 0.35 -0.2 1.35 0.35 0 1.35','4 16 0.35 0 0.85 0.35 0 1.35 0.35 -0.2 1.35 0.35 -0.2 0.85','2 24 0.35 -0.2 1.35 1.6294 -0.2 0.983','2 24 0.35 0 1.35 1.6294 0 0.983','4 16 0.35 0 1.35 1.6294 0 0.983 1.6294 -0.2 0.983 0.35 -0.2 1.35','1 16 -1.2 -0.2 3.6 0.1294 0 -0.483 0 0.5 0 0.483 0 0.1294 2-4ring1.dat','1 16 -1.2 -0.2 3.6 0.1294 0 -0.483 0 1 0 0.483 0 0.1294 2-4edge.dat','0 BFC INVERTNEXT','1 16 -1.2 -0.2 3.6 0.1294 0 -0.483 0 0.2 0 0.483 0 0.1294 2-4cyli.dat','1 16 -1.2 0 3.6 0.1294 0 -0.483 0 1 0 0.483 0 0.1294 2-4edge.dat','1 16 -1.2 -0.2 3.6 0.258819 0 -0.965926 0 1 0 0.965926 0 0.258819 2-4edge.dat','1 16 -1.2 -0.2 3.6 0.258819 0 -0.965926 0 0.2 0 0.965926 0 0.258819 2-4cyli.dat','1 16 -1.2 0 3.6 0.258819 0 -0.965926 0 1 0 0.965926 0 0.258819 2-4edge.dat','1 16 1.5 -0.2 2.9 -0.1294 0 0.483 0 0.5 0 -0.483 0 -0.1294 2-4ring1.dat','1 16 1.5 -0.2 2.9 -0.1294 0 0.483 0 1 0 -0.483 0 -0.1294 2-4edge.dat','0 BFC INVERTNEXT','1 16 1.5 -0.2 2.9 -0.1294 0 0.483 0 0.2 0 -0.483 0 -0.1294 2-4cyli.dat','1 16 1.5 0 2.9 -0.1294 0 0.483 0 1 0 -0.483 0 -0.1294 2-4edge.dat','1 16 1.5 -0.2 2.9 0.258819 0 0.965926 0 1 0 0.965926 0 -0.258819 2-4edge.dat','1 16 1.5 -0.2 2.9 0.258819 0 0.965926 0 0.2 0 0.965926 0 -0.258819 2-4cyli.dat','1 16 1.5 0 2.9 0.258819 0 0.965926 0 1 0 0.965926 0 -0.258819 2-4edge.dat','4 16 1.7588 -0.2 3.8659 -0.9412 -0.2 4.5659 -1.0706 -0.2 4.083 1.6294 -0.2 3.383','4 16 1.2412 -0.2 1.9341 1.3706 -0.2 2.417 -1.3294 -0.2 3.117 -1.4588 -0.2 2.6341','2 24 1.7588 -0.2 3.8659 -0.9412 -0.2 4.5659','2 24 1.7588 0 3.8659 -0.9412 0 4.5659','4 16 1.7588 0 3.8659 -0.9412 0 4.5659 -0.9412 -0.2 4.5659 1.7588 -0.2 3.8659','2 24 -1.0706 -0.2 4.083 1.6294 -0.2 3.383','2 24 -1.0706 0 4.083 1.6294 0 3.383','4 16 -1.0706 0 4.083 1.6294 0 3.383 1.6294 -0.2 3.383 -1.0706 -0.2 4.083','2 24 1.3706 -0.2 2.417 -1.3294 -0.2 3.117','2 24 1.3706 0 2.417 -1.3294 0 3.117','4 16 1.3706 0 2.417 -1.3294 0 3.117 -1.3294 -0.2 3.117 1.3706 -0.2 2.417','2 24 1.2412 -0.2 1.9341 -1.4588 -0.2 2.6341','2 24 1.2412 0 1.9341 -1.4588 0 2.6341','4 16 1.2412 -0.2 1.9341 -1.4588 -0.2 2.6341 -1.4588 0 2.6341 1.2412 0 1.9341']

    def GetFile(self,FileName):
        if self.FileinPartCache(FileName) == True:
            return self.FileFromPartCache(FileName)
        if self.FileInCache(FileName) == True:
            newld = LdrawFile(FileName, self.FileFromCache(FileName))
            self.AddFileToPartCache(newld)
            return newld
        elif self.FileExist(FileName) == True:
            newld = LdrawFile(FileName, self.FileFromDisk(FileName))
            self.AddFileToPartCache(newld)
            return newld
        return None

    def FileExist(self,FileName):
        if os.path.isfile(FileName):
            return True
        for Dir in self.PathList:
            if os.path.isfile(os.path.join(Dir, FileName)):
                return True
        return False

    def FilePath(self,FileName):
        if os.path.isfile(FileName):
            return FileName
        for Dir in self.PathList:
            if os.path.isfile(os.path.join(Dir, FileName)):
                return os.path.join(Dir, FileName)
        return ''

    def FileFromPartCache(self,FileName):
        if FileName in self._PartCache:
            return self._PartCache[FileName]
        return None

    def FileFromCache(self,FileName):
        if FileName in self._FileCache:
            return self._FileCache[FileName]
        return []

    def ReadFile(self,FileName):
        lines =[]
        if self.FileExist(FileName):
            with open(self.FilePath(FileName), "r") as file:
                for line in file:
                   if not line.strip(): continue
                   lines.append(line.strip())
                file.close()
        return lines

    def FileFromDisk(self,FileName):
        if self.FileExist(FileName):
            lines = self.ReadFile(FileName)

            if self.isMovedto(lines) == True:
                tempfilename = self.Movedto(lines)
                if self.FileExist(tempfilename):
                    print ('{0} is moved to: {1}'.format(FileName, tempfilename))
                    lines = self.ReadFile(tempfilename)

            sections = []
            StartLine = 0
            EndLine = 0
            lineCount = 0
            sectionFilename = FileName
            foundEnd = False

            for line in lines:
                parameters = line.split()
                if len(parameters) >= 2:
                    if parameters[0] == "0" and parameters[1].strip().lower() == "file":
                        if foundEnd == False:
                            EndLine = lineCount
                            if EndLine > StartLine:
                                sections.append([sectionFilename , lines[StartLine:EndLine]])

                        StartLine = lineCount
                        foundEnd = False
                        sectionFilename = ' '.join(parameters[2:]).lower()

                    if parameters[0] == "0" and parameters[1].strip().lower() == "nofile":
                        EndLine = lineCount
                        foundEnd = True
                        sections.append([sectionFilename,lines[StartLine:EndLine]]) 

                lineCount += 1

            if foundEnd == False:
                EndLine = lineCount
                if EndLine > StartLine:
                    sections.append([sectionFilename,lines[StartLine:EndLine]])

            for section in sections:
                self.AddFileToCache(section[0] ,section[1])

            return sections[0][1]
            
        return []

    def AddFileToCache(self,Name,Lines):
        if Name not in self._FileCache:
            self._FileCache[Name] = Lines

    def AddFileToPartCache(self,File):
        if File.Name not in self._PartCache:
            self._PartCache[File.Name] = File

    def FileinPartCache(self,FileName):
        if FileName in self._PartCache:
            return True
        return False

    def FileInCache(self,FileName):
        if FileName in self._FileCache:
            return True
        return False

    def isMovedto(self,lines):
        for l in lines:
            if l.startswith('0 ~Moved to ') == True:
                return True
        return False

    def Movedto(self,lines):
        for l in lines:
            if l.startswith('0 ~Moved to '):
                return l.replace('0 ~Moved to ', '') + '.dat'
        return ''

class LdrawFile(object):
    global FILEMANAGER

    def __init__(self, FileName , Lines):
        self.Geometries = []
        self.Subparts = []
        self.isPart = False
        self.Name = FileName
        self.Partname = ''
        self.Keywords = []
        self.Category = ''
        self.Author = ''

        inverted = False
        ccw = True
        certified = False

        for line in Lines:

            if line == '':
                continue
            tokens = line.split()

            if len(tokens) > 0:

                if tokens[0] == '0':
                    comment = LdrawComment(tokens)

                    if comment.isInvertNext() == True:
                        inverted = True
                    elif comment.isCertify() == True:
                        certified = True
                        ccw = comment.isCertifyCcw()
                    elif comment.isBfcCcw() == True:
                        ccw = True
                    elif comment.isBfcCw() == True:
                        ccw = False

                    if comment.isPart() == True:
                        self.isPart = True

                    if comment.Category() != '':
                        self.Category = comment.Category()

                    if len(comment.Keywords()) > 0:
                        self.Keywords += comment.Keywords()

                    if comment.Name() != '':
                        self.Name = comment.Name()

                    if comment.Author() != '':
                        self.Author = comment.Author()

                elif tokens[0] == '1':
                    self.Subparts.append(LdrawSubpart(tokens, inverted))
                elif tokens[0] == '2':
                    self.Geometries.append(LdrawLine(tokens))
                elif tokens[0] == '3':
                    self.Geometries.append(LdrawTriangle(tokens, ccw, certified))
                elif tokens[0] == '4':
                    self.Geometries.append(LdrawQuad(tokens, ccw, certified))
                elif tokens[0] == '5':
                    self.Geometries.append(LdrawCondition(tokens))
                    
        if self.isPart == False:
        	self.isPart = not self.HasParts(self.Subparts)
        
        if len(Lines) > 0:
            if (Lines[0].find("FILE") > -1):
                self.Partname = Lines[1][2:]
            else:
                self.Partname = Lines[0][2:]

    def HasParts(self,Subparts):
        for sp in Subparts:
            if (sp.Subpart is not None):
                if sp.Subpart.isPart:
                    return True
                else:
                    return self.HasParts(sp.Subpart.Subparts)
        return False

    def fillMesh(self,transform,currentColor,meshfiller):
        for geo in self.Geometries:
            geo.fillMesh(transform,currentColor,meshfiller)

        for sp in self.Subparts:
            sp.fillMesh(transform,currentColor,meshfiller)

class LDrawColors(object):
    def __init__(self):
        global FILEMANAGER
        self.lines = []
        self.colors = []
        if FILEMANAGER.FileExist('LDConfig.ldr'):
            self.lines = FILEMANAGER.ReadFile('LDConfig.ldr')
        elif FILEMANAGER.FileExist('LDCfgalt.ldr'):
            self.lines = FILEMANAGER.ReadFile('LDCfgalt.ldr')

        for line in self.lines:
            if line.lower().strip().startswith('0 !c'):
                self.colors.append(LDrawColor(line.split()))

    def getColorbyID(self,id):
        for col in self.colors:
            if col.code == id:
                return col

        #custom color from ldview
        if id < 512 and id >= 0:
            return self.getColorbyID(16)
        else:
            r = g = b = a = 0

            if (id >= 0x2000000 and id < 0x4000000):
                r = (id & 0xFF0000) >> 16
                g = (id & 0xFF00) >> 8
                b = (id & 0xFF)
                if (id >= 0x3000000):
                    a = 110

            elif (id >= 0x4000000 and id < 0x5000000):
                r = (((id & 0xF00000) >> 20) * 17 + ((id & 0xF00) >> 8) * 17) / 2
                g = (((id & 0xF0000) >> 16) * 17 + ((id & 0xF0) >> 4) * 17) / 2
                b = (((id & 0xF000) >> 12) * 17 + (id & 0xF) * 17) / 2

            elif (id >= 0x5000000 and id < 0x6000000):
                r = ((id & 0xF00000) >> 20) * 17
                g = ((id & 0xF0000) >> 16) * 17
                b = ((id & 0xF000) >> 12) * 17
                if (id >= 0x6000000 and id < 0x7000000):
                    a = 110

            elif (id >= 0x6000000 and id < 0x7000000):
                r = ((id & 0xF00) >> 8) * 17
                g = ((id & 0xF0) >> 4) * 17
                b = (id & 0xF) * 17
                a = 110

            elif (id >= 0x7000000 and id < 0x8000000):
                return self.getColorbyID(16)

            if a > 0:
                return LDrawColor(["0", "!COLOUR", str(id), "CODE", str(id), "VALUE", self.rgb2hex([r,g,b]), "EDGE", "#333333", "ALPHA", a])
            else:
                return LDrawColor(["0", "!COLOUR", str(id), "CODE", str(id), "VALUE", self.rgb2hex([r,g,b]), "EDGE", "#333333"])

        return self.getColorbyID(16)

    def rgb2hex(self,rgb):
        return '#' + struct.pack('BBB',*rgb).encode('hex')
                   
class LDrawColor(object):
    def __init__(self, vals):
        self.name = vals[2]
        self.code = int(self.getColorValue(vals, "CODE"))
        self.color = self.RgbVector(self.getColorValue(vals, "VALUE"))
        self.alpha = 0
        self.luminance = 0
        self.material = 'BASIC'
        self.secondary_color = c4d.Vector(0,0,0)
        self.fraction = 0.0
        self.vfraction = 0.0
        self.size = 0
        self.minsize = 0
        self.maxsize = 0

        if self.hasColorValue(vals, "ALPHA"):
            self.alpha = is_float(self.getColorValue(vals, "ALPHA"))

        if self.hasColorValue(vals, "LUMINANCE"):
            self.luminance =  is_float(self.getColorValue(vals, "LUMINANCE"))

        if self.hasColorValue(vals, "CHROME"):
            self.material = "CHROME"

        if self.hasColorValue(vals, "PEARLESCENT"):
            self.material = "PEARLESCENT"

        if self.hasColorValue(vals, "RUBBER"):
            self.material = "RUBBER"

        if self.hasColorValue(vals, "METAL"):
            self.material = "METAL"

        if self.hasColorValue(vals, "MATERIAL"):
            idx = vals.index("MATERIAL")
            subline = vals[idx:]
            self.material = self.getColorValue(subline, "MATERIAL")
            self.secondary_color = self.RgbVector(self.getColorValue(subline, "VALUE"))
            self.fraction = is_float(self.getColorValue(subline, "FRACTION"))
            self.vfraction = is_float(self.getColorValue(subline, "VFRACTION"))
            self.size = is_float(self.getColorValue(subline, "SIZE"))
            self.minsize = is_int(self.getColorValue(subline, "MINSIZE"))
            self.maxsize = is_int(self.getColorValue(subline, "MAXSIZE"))

    def Rgb(self,hex):
        hex = hex.lstrip('#')
        hlen = len(hex)
        return tuple( int(hex[i:i+int(hlen/3)],16) for i in range(0, hlen, int(hlen/3)))
    
    def RgbVector(self,hex):
        tup = self.Rgb(hex)
        return c4d.Vector(float(tup[0])/255,float(tup[1])/255,float(tup[2])/255)

    def hasColorValue(self,line,value):
        try:
            idx = line.index(value)
        except:
            idx = -1
        if idx > -1:
            return True
        return False

    def getColorValue(self,line,value):
        try:
            idx = line.index(value)
        except:
            idx = -1
        if idx > -1:
            return line[idx + 1]
        return ''

class LdrawComment(object):
    vals = []
    def __init__(self, line):
        self.vals = line
    
    def isCertify(self):
        return (len(self.vals) >= 2) and (self.vals[1] == "BFC") and (self.vals[2] == "CERTIFY")

    def isCertifyCcw(self):
        if (self.isCertify() == True) and (len(self.vals) == 4):
            return (self.vals[3] == 'CCW')
        return True

    def isInvertNext(self):
        return (len(self.vals) >= 3) and (self.vals[1] == "BFC") and (self.vals[2] == "INVERTNEXT")

    def isBfcCcw(self):
        return (len(self.vals) == 3) and (self.vals[1] == "BFC") and (self.vals[2] == "CCW")

    def isBfcCw(self):
        return (len(self.vals) == 3) and (self.vals[1] == "BFC") and (self.vals[2] == "CW")

    def isPart(self):
        return (len(self.vals) >= 3) and (self.vals[1] == "!LDRAW_ORG") and ((self.vals[2].find("Part") > -1) or (self.vals[2].find("Subpart") > -1) or (self.vals[2].find("Shortcut") > -1))
        
    def Category(self):
        if (len(self.vals) >= 2) and (self.vals[1] == "!CATEGORY"):
            return ' '.join(self.vals[2:])
        else:
            return ''

    def Keywords(self):
        if (len(self.vals) >= 2) and (self.vals[1] == "!KEYWORDS"):
            return ' '.join(self.vals[2:]).split(',')
        else:
            return []

    def Name(self):
        if (len(self.vals) >= 2) and (self.vals[1] == "Name:"):
            return ' '.join(self.vals[2:])
        else:
            return ''

    def Author(self):
        if (len(self.vals) >= 2) and (self.vals[1] == "Author:"):
            return ' '.join(self.vals[2:])
        else:
            return ''

    def fillMesh(self,transform,currentColor,meshfiller):
        pass

class LdrawSubpart(object):
    def __init__(self, Values , _inverted ):
        global FILEMANAGER
        self.Inverted = _inverted
        self.Color = is_color(Values[1])
        (x, y, z, a, b, c, d, e, f, g, h, i) = map(float, Values[2:14])
        self.Matrix = c4d.Matrix(c4d.Vector(x, y, z), c4d.Vector(a, d, g), c4d.Vector(b, e, h), c4d.Vector(c, f, i))
        self.Name = ' '.join(Values[14:]).lower()
        self.Subpart = FILEMANAGER.GetFile(self.Name)
        if self.Subpart is None:
            print ('Part Not Found: ' + self.Name)

    def fillMesh(self,transform,currentColor,meshfiller):
        if self.Inverted == True: meshfiller.inverting = not self.Inverted
        self.Subpart.fillMesh(transform * self.Matrix, currentColor if self.Color == 16 or self.Color == 24 else self.Color, meshfiller)
        if self.Inverted == True: meshfiller.inverting = not self.Inverted

class LdrawLine(object):
    def __init__(self, Values):
        self.Color = is_color(Values[1])
        self.P1 = c4d.Vector(is_float(Values[2]), is_float(Values[3]), is_float(Values[4]))
        self.P2 = c4d.Vector(is_float(Values[5]), is_float(Values[6]), is_float(Values[7]))
    
    def fillMesh(self,transform,currentColor,meshfiller):
        meshfiller.addLine(transform.Mul(self.P1), transform.Mul(self.P2), currentColor if self.Color == 16 or self.Color == 24 else self.Color)

class LdrawTriangle(object):
    def __init__(self, Values ,_ccw,_certified):
        self.ccw = _ccw
        self.certified = _certified
        self.Color = is_color(Values[1])
        self.P1 = c4d.Vector(is_float(Values[2]), is_float(Values[3]), is_float(Values[4]))
        self.P2 = c4d.Vector(is_float(Values[5]), is_float(Values[6]), is_float(Values[7]))
        self.P3 = c4d.Vector(is_float(Values[8]), is_float(Values[9]), is_float(Values[10]))

    def fillMesh(self,transform,currentColor,meshfiller):
        meshfiller.addFace3(self.ccw, self.certified, Determinant(transform), currentColor if self.Color == 16 or self.Color == 24 else self.Color, transform.Mul(self.P1), transform.Mul(self.P2), transform.Mul(self.P3) )

class LdrawQuad(object):
    def __init__(self, Values ,_ccw,_certified):
        self.ccw = _ccw
        self.certified = _certified
        self.Color = is_color(Values[1])
        self.P1 = c4d.Vector(is_float(Values[2]), is_float(Values[3]), is_float(Values[4]))
        self.P2 = c4d.Vector(is_float(Values[5]), is_float(Values[6]), is_float(Values[7]))
        self.P3 = c4d.Vector(is_float(Values[8]), is_float(Values[9]), is_float(Values[10]))
        self.P4 = c4d.Vector(is_float(Values[11]), is_float(Values[12]), is_float(Values[13]))

    def fillMesh(self,transform,currentColor,meshfiller):
        meshfiller.addFace4(self.ccw, self.certified, Determinant(transform), currentColor if self.Color == 16 or self.Color == 24 else self.Color, transform.Mul(self.P1), transform.Mul(self.P2), transform.Mul(self.P3), transform.Mul(self.P4) )

class LdrawCondition(object):
    def __init__(self, Values):
        self.Color = is_color(Values[1])
        self.P1 = c4d.Vector(is_float(Values[2]), is_float(Values[3]), is_float(Values[4]))
        self.P2 = c4d.Vector(is_float(Values[5]), is_float(Values[6]), is_float(Values[7]))
        self.P3 = c4d.Vector(is_float(Values[8]), is_float(Values[9]), is_float(Values[10]))
        self.P4 = c4d.Vector(is_float(Values[11]), is_float(Values[12]), is_float(Values[13]))
    
    def fillMesh(self,transform,currentColor,meshfiller):
        meshfiller.addCondLine(transform.Mul(self.P1), transform.Mul(self.P2), transform.Mul(self.P3), transform.Mul(self.P4))

def is_float(s):
    try:
        float(s)
        return float(s)
    except ValueError:
        return 0

def is_color(s):
    try:
        int(s)
        return int(s)
    except ValueError:
        return 16

def is_int(s):
    try:
        int(s)
        return int(s)
    except ValueError:
        return 0

def Determinant(m):
    return m.v1.x * (m.v2.y * m.v3.z - m.v2.z * m.v3.y) - m.v1.y * (m.v2.x * m.v3.z - m.v2.z * m.v3.x) + m.v1.z * (m.v2.x * m.v3.y - m.v2.y * m.v3.x)

def buildMaterial(doc, mat):
    m = doc.SearchMaterial(str(mat.name))
    if (m is None):

        m = c4d.Material(c4d.Mmaterial)
        m.SetParameter(c4d.ID_BASELIST_NAME, mat.name, c4d.DESCFLAGS_SET_0)
        if mat.alpha == 0:
            m.SetParameter(c4d.MATERIAL_COLOR_COLOR, mat.color, c4d.DESCFLAGS_SET_0)
            m.SetParameter(c4d.MATERIAL_USE_COLOR, True, c4d.DESCFLAGS_SET_0)
        else:
            m.SetParameter(c4d.MATERIAL_USE_COLOR, False, c4d.DESCFLAGS_SET_0)

        m.RemoveReflectionAllLayers()
        
        if mat.material == 'BASIC' or mat.material == 'GLITTER' or mat.material == 'SPECKLE':
            if mat.alpha > 0:
                m.SetParameter(c4d.MATERIAL_COLOR_BRIGHTNESS, 0.5, c4d.DESCFLAGS_SET_0)
                m.SetParameter(c4d.MATERIAL_USE_TRANSPARENCY, True, c4d.DESCFLAGS_SET_0)
                m.SetParameter(c4d.MATERIAL_TRANSPARENCY_BRIGHTNESS, 1, c4d.DESCFLAGS_SET_0)
                m.SetParameter(c4d.MATERIAL_TRANSPARENCY_REFRACTION, 1.575, c4d.DESCFLAGS_SET_0)
                m.SetParameter(c4d.MATERIAL_TRANSPARENCY_COLOR, mat.color, c4d.DESCFLAGS_SET_0)
                
            layer = m.AddReflectionLayer()
            if layer is not None:
                layerID = layer.GetDataID()
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_MAIN_VALUE_REFLECTION, 0.8, c4d.DESCFLAGS_SET_0)
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_MAIN_VALUE_ROUGHNESS, 0.28, c4d.DESCFLAGS_SET_0)
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_MODE, c4d.REFLECTION_FRESNEL_DIELECTRIC, c4d.DESCFLAGS_SET_0)
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_PRESET, c4d.REFLECTION_FRESNEL_DIELECTRIC_PET, c4d.DESCFLAGS_SET_0)


        elif mat.material == 'CHROME':
            layer = m.AddReflectionLayer()
            if layer is not None:
                layerID = layer.GetDataID()
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_MAIN_VALUE_REFLECTION, 0.8, c4d.DESCFLAGS_SET_0)
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_MODE, c4d.REFLECTION_FRESNEL_CONDUCTOR, c4d.DESCFLAGS_SET_0)
                if 'Gold' in mat.name:
                    m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_METAL, c4d.REFLECTION_FRESNEL_METAL_GOLD, c4d.DESCFLAGS_SET_0)
                elif 'Silver' in mat.name:
                    m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_METAL, c4d.REFLECTION_FRESNEL_METAL_SILVER, c4d.DESCFLAGS_SET_0)
                else:
                    m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_METAL, c4d.REFLECTION_FRESNEL_METAL_CHROMIUM, c4d.DESCFLAGS_SET_0)

        elif mat.material == 'RUBBER':
            layer = m.AddReflectionLayer()
            if layer is not None:
                layerID = layer.GetDataID()
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_MAIN_VALUE_REFLECTION, 0.8, c4d.DESCFLAGS_SET_0)
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_MAIN_VALUE_ROUGHNESS, 0.5, c4d.DESCFLAGS_SET_0)
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_COLOR_BRIGHTNESS, 0.5, c4d.DESCFLAGS_SET_0)
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_MODE, c4d.REFLECTION_FRESNEL_DIELECTRIC, c4d.DESCFLAGS_SET_0)
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_PRESET, c4d.REFLECTION_FRESNEL_DIELECTRIC_ASPHALT, c4d.DESCFLAGS_SET_0)

        elif mat.material == 'METAL':
            layer = m.AddReflectionLayer()
            if layer is not None:
                layerID = layer.GetDataID()
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_MAIN_VALUE_REFLECTION, 0.8, c4d.DESCFLAGS_SET_0)
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_MAIN_VALUE_ROUGHNESS, 0.1, c4d.DESCFLAGS_SET_0)
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_MODE, c4d.REFLECTION_FRESNEL_CONDUCTOR, c4d.DESCFLAGS_SET_0)
                m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_METAL, c4d.REFLECTION_FRESNEL_METAL_ALUMINUM, c4d.DESCFLAGS_SET_0)

        elif mat.material == 'PEARLESCENT':
            layer = m.AddReflectionLayer()
            if layer is not None:
               layerID = layer.GetDataID()
               m.SetParameter(layerID + c4d.REFLECTION_LAYER_MAIN_VALUE_REFLECTION, 0.8, c4d.DESCFLAGS_SET_0)
               m.SetParameter(layerID + c4d.REFLECTION_LAYER_MAIN_VALUE_ROUGHNESS, 0.15, c4d.DESCFLAGS_SET_0)
               m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_MODE, c4d.REFLECTION_FRESNEL_CONDUCTOR, c4d.DESCFLAGS_SET_0)
               if 'Gold' in mat.name:
                   m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_METAL, c4d.REFLECTION_FRESNEL_METAL_GOLD, c4d.DESCFLAGS_SET_0)
               elif 'Copper' in mat.name:
                   m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_METAL, c4d.REFLECTION_FRESNEL_METAL_COPPER, c4d.DESCFLAGS_SET_0)
               else:
                   m.SetParameter(layerID + c4d.REFLECTION_LAYER_FRESNEL_METAL, c4d.REFLECTION_FRESNEL_METAL_ALUMINUM, c4d.DESCFLAGS_SET_0)

        if mat.luminance > 0:
            m.SetParameter(c4d.MATERIAL_USE_LUMINANCE, True, c4d.DESCFLAGS_SET_0)
            m.SetParameter(c4d.MATERIAL_LUMINANCE_BRIGHTNESS, (mat.luminance/100) * 2, c4d.DESCFLAGS_SET_0)

        doc.InsertMaterial(m)
        doc.AddUndo(c4d.UNDOTYPE_NEW, m)
    return m         

#Maindialog
class LDRDialog(gui.GeDialog):
    LDRData = None
    ldrawpath = ''
    resolution = COMBO_STD
    logo = True
    optimize = True
    smoth = True

    def CreateLayout(self):
        global FILELOADER

        self.SetTitle("LDR Import")
        self.MenuFlushAll()
        self.MenuSubBegin("Info")
        self.MenuAddString(IDC_ABOUT, "About")
        self.MenuSubEnd()
        self.MenuFinished()
        
        self.GroupBegin(99, c4d.BFH_SCALEFIT, cols=1, rows=1)
        self.GroupBorderSpace(5, 5, 5, 5)

        self.GroupBegin(100, c4d.BFH_SCALEFIT, cols=2, rows=1, title='Ldraw Dir', groupflags=0)
        self.GroupBorderSpace(5, 5, 5, 5)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(5, 5, 5, 5)
        self.AddStaticText(id=IDC_LDRAWPATH, flags=c4d.BFH_SCALEFIT, initw=0, inith=0, name='', borderstyle=c4d.BORDER_THIN_IN)
        self.AddButton(id=IDC_SETPATH, flags=c4d.BFH_RIGHT, initw=8, inith=8, name="...")
        self.GroupEnd()
        
        self.GroupBegin(101, c4d.BFH_SCALEFIT, cols=1, rows=1, title='Quality', groupflags=0)
        self.GroupBorderSpace(5, 5, 5, 5)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.AddComboBox(IDC_COMBO, c4d.BFH_LEFT, initw=0)
        self.AddChild(IDC_COMBO, COMBO_HIH, "HighRes") 
        self.AddChild(IDC_COMBO, COMBO_STD, "Standard") 
        self.AddChild(IDC_COMBO, COMBO_LOW, "LowRes")  
        self.SetInt32(IDC_COMBO ,self.resolution)
        self.GroupEnd()

        self.GroupBegin(102, c4d.BFH_SCALEFIT, cols=1, rows=1, title='Logo', groupflags=0)
        self.GroupBorderSpace(5, 5, 5, 5)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.AddCheckbox(IDC_LOGO, c4d.BFH_LEFT, initw=0, inith=0, name='Logo on Studs')
        self.SetBool(IDC_LOGO, self.logo)
        self.GroupEnd()

        self.GroupBegin(103, c4d.BFH_SCALEFIT, cols=1, rows=1, title='Optimize Settings', groupflags=0)
        self.GroupBorderSpace(5, 5, 5, 5)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.AddCheckbox(IDC_OPTIMIZE, c4d.BFH_LEFT, initw=0, inith=0, name='Optimize Model')
        self.AddCheckbox(IDC_SMOTH, c4d.BFH_LEFT, initw=0, inith=0, name='Smoth Shading')
        self.SetBool(IDC_OPTIMIZE, self.optimize)
        self.SetBool(IDC_SMOTH, self.smoth)
        self.GroupEnd()

        self.AddButton(id=IDC_LOAD, flags=c4d.BFH_CENTER, initw=200, inith=25, name="Load")

        self.GroupEnd()

        self.Enable(IDC_LOAD, False)
        return True

    def Command(self, id, msg):
        if id == IDC_ABOUT:
            self.About()

        elif id == IDC_SETPATH:
            self.Setpath()  

        elif id == IDC_LOAD:
            self.Load()

        elif id == IDC_COMBO:
            self.resolution = self.GetInt32(IDC_COMBO)

        elif id == IDC_LOGO:
            self.logo = self.GetBool(IDC_LOGO)

        elif id == IDC_OPTIMIZE:
            self.optimize = self.GetBool(IDC_OPTIMIZE)
            if self.optimize == True:
                self.Enable(IDC_SMOTH, True)
            else:
                self.smoth  = False
                self.Enable(IDC_SMOTH, self.smoth)
                self.SetBool(IDC_SMOTH, self.smoth)

        elif id == IDC_SMOTH:
            self.smoth = self.GetBool(IDC_SMOTH)

        if self.resolution != COMBO_STD:
            self.logo = False
            self.Enable(IDC_LOGO, False)
            self.SetBool(IDC_LOGO, False)
        else:
            self.Enable(IDC_LOGO, True)

        self.UpdatePrefs()
        return True

    def Setpath(self):
        self.ldrawpath = str(c4d.storage.LoadDialog(flags=c4d.FILESELECT_DIRECTORY, title='select Ldraw path'))
        if self.ldrawpath != '':
            if self.isLdrawDir(self.ldrawpath) == True:
                self.Enable(IDC_LOAD, True)
                self.SetString(IDC_LDRAWPATH,self.ldrawpath)
            elif self.findLdrawDir() == True:
                self.Enable(IDC_LOAD, True)
                self.SetString(IDC_LDRAWPATH,self.ldrawpath) 
            else:
                self.Enable(IDC_LOAD, False)
                self.SetString(IDC_LDRAWPATH,'')
                self.ldrawpath = ''

    def findLdrawDir(self):
        if platform.system() == "Windows":
            ldrawPossibleDirectories = ["C:\\LDraw","C:\\Program Files\\LDraw","C:\\Program Files (x86)\\LDraw"]
        elif platform.system() == "Darwin":
            ldrawPossibleDirectories = ["~/ldraw/","/Applications/LDraw/","/Applications/ldraw/","/usr/local/share/ldraw"]

        for dir in ldrawPossibleDirectories:
            dir = os.path.expanduser(dir)
            if os.path.isfile(os.path.join(dir, "LDConfig.ldr")):
                self.ldrawpath = dir
                return True
        return False

    def isLdrawDir(self,Dir):
        if os.path.exists(os.path.join(Dir, "LDConfig.ldr")):
            return True
        elif os.path.exists(os.path.join(Dir, "LDCfgalt.ldr")):
            return True
        return False

    def About(self):
        gui.MessageDialog("LDR2C4D jonnysp (C)2017", c4d.GEMB_OK)
        
    def InitValues(self):
        self.LDRData = plugins.GetWorldPluginData(id = PLUGIN_ID)
        if self.LDRData is None:
            self.LDRData = c4d.BaseContainer()
        else:
            if self.LDRData[LDRAWPATH]:
                self.ldrawpath = self.LDRData[LDRAWPATH]
                if self.ldrawpath != '':
                    if self.isLdrawDir(self.ldrawpath) == True:
                        self.Enable(IDC_LOAD, True)
                        self.SetString(IDC_LDRAWPATH,self.ldrawpath)
                    else:
                        self.Enable(IDC_LOAD, False)
                        self.SetString(IDC_LDRAWPATH,'')
                        self.ldrawpath = ''
            elif self.findLdrawDir() == True:
                self.Enable(IDC_LOAD, True)
                self.SetString(IDC_LDRAWPATH,self.ldrawpath)  

            if self.LDRData[RESOLUTION]:
                self.resolution = int(self.LDRData[RESOLUTION])
                self.SetInt32(IDC_COMBO ,self.resolution)
            
            if self.LDRData[LOGO]:
                self.logo = bool(self.LDRData[LOGO])
            else:
                self.logo = False

            if self.resolution != COMBO_STD:
                self.logo = False
                self.Enable(IDC_LOGO, False)
                self.SetBool(IDC_LOGO, False)
            else:
                self.Enable(IDC_LOGO, True)

            self.SetBool(IDC_LOGO, self.logo)

            if self.LDRData[SMOTH] == True:
                self.smoth = True
            else:
                self.smoth = False

            if self.LDRData[OPTIMIZE] == True:
                self.optimize = True
                self.Enable(IDC_SMOTH, True)
            else:
                self.optimize = False
                self.smoth = False
                self.Enable(IDC_SMOTH, False)

            self.SetBool(IDC_OPTIMIZE, self.optimize)
            self.SetBool(IDC_SMOTH, self.smoth)
        return True

    def UpdatePrefs(self):
        if self.LDRData is None:
            self.LDRData = c4d.BaseContainer()
            self.UpdatePrefs()
        else:
            self.LDRData.SetString(LDRAWPATH, self.ldrawpath)
            self.LDRData.SetString(RESOLUTION, self.resolution)
            self.LDRData.SetBool(LOGO, self.logo)
            self.LDRData.SetBool(OPTIMIZE, self.optimize)
            self.LDRData.SetBool(SMOTH, self.smoth)

            plugins.SetWorldPluginData(PLUGIN_ID,self.LDRData)
        return True

    def Load(self):
        global FILEMANAGER,LDRAWCOLORS

        file = c4d.storage.LoadDialog(type=c4d.FILESELECTTYPE_SCENES, title="Select File (ldr,mdp,dat)")
        if file:
            FILEMANAGER = FileManager(self.ldrawpath , file , self.resolution, self.logo)
            LDRAWCOLORS = LDrawColors()

            optimizesettings = c4d.BaseContainer()
            optimizesettings.SetData(c4d.MDATA_OPTIMIZE_POLYGONS, True)
            optimizesettings.SetData(c4d.MDATA_OPTIMIZE_UNUSEDPOINTS, True)
            optimizesettings.SetData(c4d.MDATA_OPTIMIZE_POINTS, True)
            optimizesettings.SetData(c4d.MDATA_OPTIMIZE_TOLERANCE, 0.01)

            c4d.StatusSetText('scanning LDraw ... please wait')
            c4d.StatusSetSpin()

            scene = FILEMANAGER.GetFile(file)

            doc = c4d.documents.GetActiveDocument()
            doc.StartUndo()
            c4d.StopAllThreads()

            parent = c4d.BaseObject(c4d.Onull)
            parent.SetName(scene.Name)  
            parent[c4d.NULLOBJECT_DISPLAY] = c4d.NULLOBJECT_DISPLAY_NONE

            generate(scene,c4d.Matrix(),16,doc,parent,optimizesettings,self.optimize,self.smoth)

            doc.InsertObject(parent)
            doc.AddUndo(c4d.UNDOTYPE_NEW, parent)

            c4d.EventAdd(c4d.EVENT_FORCEREDRAW) 
            doc.EndUndo()
            
            c4d.StatusClear()
            doc.Message(c4d.MSG_UPDATE)
        return True

class MainPlugin(plugins.CommandData):
    dialog = None
    def Execute(self, doc):
        if self.dialog is None:
            self.dialog = LDRDialog()
            pass
        return self.dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID, defaultw=400, defaulth=0)

    def RestoreLayout(self, sec_ref):
        if self.dialog is None:
            self.dialog = LDRDialog()
            pass
        return self.dialog.Restore(pluginid=PLUGIN_ID, secret=sec_ref)

if __name__ == "__main__":
    bmp = bitmaps.BaseBitmap()
    dir, file = os.path.split(__file__)
    bmp.InitWith(os.path.join(dir, "res", "icon.png"))
    plugins.RegisterCommandPlugin(id=PLUGIN_ID, str="LDR2C4D", info=0,help="Import LDR Files to Cinema4D", dat=MainPlugin(), icon=bmp)