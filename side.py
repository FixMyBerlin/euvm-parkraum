#---------------------------------------------------------------------------#
#   Ermittelt für einen Flächendatensatz, auf welcher Seite einer Linie     #
#   eines Liniendatensatzes sich jede Fläche befindet (unter                #
#   Berücksichtigung der Linienrichtung; links oder rechts).                #
#---------------------------------------------------------------------------#
#   Input: Definiert durch Variablen areas_file_path und ways_file_path.    #
#   Output: Temporäre Layer in QGIS.                                        #
#---------------------------------------------------------------------------#

import processing, time

# project directory
from console.console import _console
project_dir = os.path.dirname(_console.console.tabEditorWidget.currentWidget().path) + '/'

areas_file_path = project_dir + 'inputs/parkraumdaten_innenstadt_translated.gpkg'
ways_file_path = project_dir + 'inputs/osm_street_network_innenstadt.gpkg'

unique_attribute = 'fid'

crs = "EPSG:25833"

print(time.strftime('%H:%M:%S', time.localtime()), 'Starte Seitenermittlung...')
print(time.strftime('%H:%M:%S', time.localtime()), 'Lade Daten...')

layer_areas = QgsVectorLayer(areas_file_path + '|geometrytype=Polygon', 'areas', 'ogr')
layer_ways = QgsVectorLayer(ways_file_path + '|geometrytype=LineString', 'ways', 'ogr')

print(time.strftime('%H:%M:%S', time.localtime()), 'Reprojiziere Daten...')

layer_areas_crs = layer_areas.crs().authid()
layer_ways_crs = layer_ways.crs().authid()

if layer_areas_crs != crs:
    print(time.strftime('%H:%M:%S', time.localtime()), '   Reprojiziere Flächendaten...')
    layer_areas = processing.run('native:reprojectlayer', { 'INPUT' : layer_areas, 'TARGET_CRS' : QgsCoordinateReferenceSystem(crs), 'OUTPUT': 'memory:'})['OUTPUT']
else:
    print(time.strftime('%H:%M:%S', time.localtime()), '   Flächendaten sind bereits reprojiziert.')

if layer_ways_crs != crs:
    print(time.strftime('%H:%M:%S', time.localtime()), '   Reprojiziere Liniendaten...')
    layer_ways = processing.run('native:reprojectlayer', { 'INPUT' : layer_ways, 'TARGET_CRS' : QgsCoordinateReferenceSystem(crs), 'OUTPUT': 'memory:'})['OUTPUT']
else:
    print(time.strftime('%H:%M:%S', time.localtime()), '   Liniendaten sind bereits reprojiziert.')

print(time.strftime('%H:%M:%S', time.localtime()), 'Erzeuge Flächenbezugspunkte...')

# "Punkt auf Oberfläche" der Flächen berechnen
layer_areas_point_on_surface = processing.run('native:pointonsurface', { 'INPUT' : layer_areas, 'ALL_PARTS' : False, 'OUTPUT': 'memory:'})['OUTPUT']

# Punkt auf Straßenlinie snappen
layer_areas_point_on_surface_snapped = processing.run('native:snapgeometries', { 'INPUT' : layer_areas_point_on_surface, 'REFERENCE_LAYER' : layer_ways, 'BEHAVIOR' : 1, 'TOLERANCE' : 40, 'OUTPUT': 'memory:'})['OUTPUT']

print(time.strftime('%H:%M:%S', time.localtime()), 'Erzeuge Straßeneinzelsegmente...')

# Straßennetz in Einzelsegmente explodieren
layer_ways = processing.run('native:explodelines', { 'INPUT' : layer_ways, 'OUTPUT': 'memory:'})['OUTPUT']

print(time.strftime('%H:%M:%S', time.localtime()), 'Reduziere Straßeneinzelsegmente...')

# Nur die Straßensegmente behalten, die an einem Punkt liegen (Punkte dafür um 10 cm buffern, da gesnappte Geometrien leider nicht sicher topologisch die Linien schneiden)
layer_areas_point_on_surface_snapped_buffered = processing.run('native:buffer', { 'INPUT' : layer_areas_point_on_surface_snapped, 'DISTANCE' : 0.1, 'OUTPUT': 'memory:'})['OUTPUT']
layer_ways = processing.run('native:extractbylocation', { 'INPUT' : layer_ways, 'INTERSECT' : layer_areas_point_on_surface_snapped_buffered, 'PREDICATE' : [0], 'OUTPUT': 'memory:'})['OUTPUT']

print(time.strftime('%H:%M:%S', time.localtime()), 'Berechne Straßenwinkel...')

# Winkel des Straßensegments ermitteln
layer_ways = processing.run('qgis:fieldcalculator', { 'INPUT': layer_ways, 'FIELD_NAME': 'angle', 'FIELD_TYPE': 0, 'FIELD_LENGTH': 6, 'FIELD_PRECISION': 2, 'NEW_FIELD': True, 'FORMULA': 'degrees(azimuth(start_point($geometry), end_point($geometry)))', 'OUTPUT': 'memory:'})['OUTPUT']

print(time.strftime('%H:%M:%S', time.localtime()), 'Führe Winkel zusammen...')

# Straßenwinkel (und Straßennamen) an der Snapping-Position auf Punkt übertragen
layer_areas_point_on_surface_snapped = processing.run('native:joinbynearest', { 'INPUT' : layer_areas_point_on_surface_snapped, 'INPUT_2' : layer_ways, 'FIELDS_TO_COPY' : ['name','angle'], 'MAX_DISTANCE' : 0.1, 'NEIGHBORS' : 1, 'PREFIX' : 'snapped_street_', 'OUTPUT': 'memory:'})['OUTPUT']

# Nabenlinie zwischen Punkt und nächstgelegenem Punkt auf der Straße erzeugen
layer_hublines = processing.run('native:hublines', { 'HUBS' : layer_areas_point_on_surface, 'HUB_FIELD' : unique_attribute, 'HUB_FIELDS' : [], 'SPOKES' : layer_areas_point_on_surface_snapped, 'SPOKE_FIELD' : unique_attribute, 'SPOKE_FIELDS' : ['snapped_street_name','snapped_street_angle'], 'OUTPUT': 'memory:'})['OUTPUT']

# Winkel der Nabenlinie ermitteln und Seite sowie nützliche Attribute zum Debugging daraus berechnen (Distanz, relativer Winkel)
layer_hublines = processing.run('qgis:fieldcalculator', { 'INPUT': layer_hublines, 'FIELD_NAME': 'angle', 'FIELD_TYPE': 0, 'FIELD_LENGTH': 6, 'FIELD_PRECISION': 2, 'NEW_FIELD': True, 'FORMULA': 'degrees(azimuth(start_point($geometry), end_point($geometry)))', 'OUTPUT': 'memory:'})['OUTPUT']
layer_hublines = processing.run('qgis:fieldcalculator', { 'INPUT': layer_hublines, 'FIELD_NAME': 'side', 'FIELD_TYPE': 2, 'FIELD_LENGTH': 0, 'FIELD_PRECISION': 0, 'NEW_FIELD': True, 'FORMULA': 'if(("snapped_street_angle" - "angle" >= 0 AND "snapped_street_angle" - "angle" <= 180) OR "snapped_street_angle" - "angle" <= -180, \'right\', \'left\')', 'OUTPUT': 'memory:'})['OUTPUT']
layer_hublines = processing.run('qgis:fieldcalculator', { 'INPUT': layer_hublines, 'FIELD_NAME': 'distance', 'FIELD_TYPE': 0, 'FIELD_LENGTH': 6, 'FIELD_PRECISION': 2, 'NEW_FIELD': True, 'FORMULA': 'distance(start_point($geometry), end_point($geometry))', 'OUTPUT': 'memory:'})['OUTPUT']
layer_hublines = processing.run('qgis:fieldcalculator', { 'INPUT': layer_hublines, 'FIELD_NAME': 'deviation_angle', 'FIELD_TYPE': 0, 'FIELD_LENGTH': 6, 'FIELD_PRECISION': 2, 'NEW_FIELD': True, 'FORMULA': 'round(abs(90 - if(if("snapped_street_angle" > 180, "snapped_street_angle" - 180, "snapped_street_angle") > if("angle" > 180, "angle" - 180, "angle"), abs(if("snapped_street_angle" > 180, "snapped_street_angle" - 180, "snapped_street_angle") - if("angle" > 180, "angle" - 180, "angle")), abs(if("angle" > 180, "angle" - 180, "angle") - if("snapped_street_angle" > 180, "snapped_street_angle" - 180, "snapped_street_angle")))), 2)', 'OUTPUT': 'memory:'})['OUTPUT']

print(time.strftime('%H:%M:%S', time.localtime()), 'Seitenattribut übertragen...')

# Seitenattribut auf Flächen übertragen
layer_areas = processing.run('native:joinattributestable', { 'INPUT': layer_areas, 'INPUT_2' : layer_hublines, 'FIELD' : unique_attribute, 'FIELDS_TO_COPY' : ['snapped_street_name', 'side'], 'FIELD_2' : unique_attribute, 'METHOD' : 1, 'PREFIX' : '', 'OUTPUT': 'memory:'})['OUTPUT']

# Warnung erzeugen, wenn eUVM- und gesnappter OSM-Straßenname nicht übereinstimmen
layer_areas = processing.run('qgis:fieldcalculator', { 'INPUT': layer_areas, 'FIELD_NAME': 'warnings', 'NEW_FIELD': False, 'FORMULA': 'if("object:street" != "snapped_street_name", if("warnings" IS NOT NULL, "warnings" + \'; \', \'\') + \'[#50] Angegebener Straßenname stimmt nicht mit nächstgelegenem Straßennamen überein.\', "warnings")', 'OUTPUT': 'memory:'})['OUTPUT']

print(time.strftime('%H:%M:%S', time.localtime()), 'Lade Ergebnis...')

layer_areas.setName('output_parking_areas_with_side')
QgsProject.instance().addMapLayer(layer_areas, True)
layer_hublines.setName('output_helper_side_hublines')
QgsProject.instance().addMapLayer(layer_hublines, True)

print(time.strftime('%H:%M:%S', time.localtime()), 'Seitenermittlung abgeschlossen.')