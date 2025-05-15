#---------------------------------------------------------------------------#
#   Überträgt Parkraumattribute von Flächen an nahegelegene Straßenlinien.  #
#---------------------------------------------------------------------------#
#   Input: Definiert durch Variablen areas_file_path und ways_file_path.    #
#   Output: Temporäre Layer in QGIS.                                        #
#---------------------------------------------------------------------------#

import processing, time

# project directory
from console.console import _console
project_dir = os.path.dirname(_console.console.tabEditorWidget.currentWidget().path) + '/'

areas_file_path = project_dir + 'inputs/parkraumdaten_innenstadt_translated_with_side.gpkg'
ways_file_path = project_dir + 'inputs/osm_street_network_innenstadt.gpkg'

# Attribute für beide Layer, die jeweils den Straßennamen enthalten
areas_street_name_attr = 'snapped_street_name' # 'object:street'
ways_street_name_attr = 'name'

# Distanz in Metern, in der im Umfeld von Straßenlinien maximal nach Parkflächen gesucht wird um Attribute zu übertragen
snapping_distance = 15

# Koordinatenbezugssystem für Verarbeitung (metrisch)
crs = "EPSG:25833"

# Ausgabedatensatz vereinfachen:
delete_columns = True # Polygon- und Straßennamen-ID's ausschließen
simplify_output = True # gleiche Wegsegmente zusammenführen, gleiche left- und right-Attribute zu "both"-Schreibweise vereinfachen

# Soll "markings=no" an der centerline explizit ausgewiesen werden oder NULL bleiben?
show_markings_no = False

# Sollen die an Straßenlinien gesnappten Parkflächen zur Kontrolle ausgegeben werden?
output_parking_areas = False

# Prozentangaben für Fortschrittsausgabe
percent = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

print(time.strftime('%H:%M:%S', time.localtime()), 'Starte Centerline-Transfer...')
print(time.strftime('%H:%M:%S', time.localtime()), 'Lade Daten...')

layer_areas = QgsVectorLayer(areas_file_path + '|geometrytype=Polygon', 'areas', 'ogr')
layer_ways = QgsVectorLayer(ways_file_path + '|geometrytype=LineString', 'ways', 'ogr')



# TODO: delete test_area

layer_ways = processing.run('native:retainfields', { 'INPUT' : layer_ways, 'FIELDS' : ['id', 'highway', 'name', 'test_area'], 'OUTPUT': 'memory:'})['OUTPUT']



# Reprojizieren
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

# Snapping der Flächengeometrien an die Straßenlinien (einzeln für jeden Straßennamen, um Artefakte im Knotenpunktbereich zu reduzieren/vermeiden)
# Snapping-Layer für jeden Straßennamen erzeugen
print(time.strftime('%H:%M:%S', time.localtime()), 'Raste Flächendaten auf Liniendaten ein...')
print(time.strftime('%H:%M:%S', time.localtime()), '   Erzeuge Snapping-Layer nach Straßennamen...')

street_names = layer_areas.uniqueValues(layer_areas.fields().indexFromName(areas_street_name_attr))

QgsProject.instance().addMapLayer(layer_ways, False)
QgsProject.instance().addMapLayer(layer_areas, False)

layer_areas_snapped_street_names = []

for street_name in street_names:
    layer_areas_snapped_street_name = NULL
    # Straßen und Flächen nach Straßennamen selektieren
    processing.run('qgis:selectbyattribute', {'INPUT' : layer_ways, 'FIELD' : ways_street_name_attr, 'VALUE' : street_name })
    processing.run('qgis:selectbyattribute', {'INPUT' : layer_areas, 'FIELD' : areas_street_name_attr, 'VALUE' : street_name })
    # Snapping-Layer für selektierten Straßennamen erzeugen
    # -> Im Umkreis von X Metern an eine Linie mit gleichem Straßennamen anbinden
    if layer_areas.selectedFeatureCount() > 0:
        layer_areas_snapped_street_name = processing.run('native:snapgeometries', { 'INPUT' : QgsProcessingFeatureSourceDefinition(layer_areas.id(), selectedFeaturesOnly=True), 'REFERENCE_LAYER' : QgsProcessingFeatureSourceDefinition(layer_ways.id(), selectedFeaturesOnly=True), 'BEHAVIOR' : 1, 'TOLERANCE' : snapping_distance, 'OUTPUT': 'memory:'})['OUTPUT']
        layer_areas_snapped_street_names.append(layer_areas_snapped_street_name)
    else:
        print(time.strftime('%H:%M:%S', time.localtime()), f'      [!] Keine passende Straße für Straßennamen "{street_name}" gefunden.')

# Snapping-Layer zusammenführen
print(time.strftime('%H:%M:%S', time.localtime()), '   Führe Straßennamen-Snapping-Layer zusammen...')
layer_areas_snapped = processing.run('native:mergevectorlayers', { 'LAYERS' : layer_areas_snapped_street_names, 'OUTPUT': 'memory:'})['OUTPUT']

# Kleinen Buffer für eindeutige Überschneidungen erzeugen
print(time.strftime('%H:%M:%S', time.localtime()), 'Puffere Snapping-Layer...')
layer_areas_snapped = processing.run('native:buffer', { 'INPUT' : layer_areas_snapped, 'DISTANCE' : 0.1, 'OUTPUT': 'memory:'})['OUTPUT']

# Straßensegmente an Parkflächenkanten splitten
print(time.strftime('%H:%M:%S', time.localtime()), 'Zergliedere Snapping-Layer...')
layer_ways_split = processing.run('native:splitwithlines', { 'INPUT' : layer_ways, 'LINES' : layer_areas_snapped, 'OUTPUT': 'memory:'})['OUTPUT']

# Straßensegmente minimal kürzen, um eindeutige geometrische Lagebeziehungen herzustellen
# dafür minimale Puffer an Linienübergängen erzeugen und Linien dort wegschneiden
print(time.strftime('%H:%M:%S', time.localtime()), 'Kürze Liniensegmente...')
print(time.strftime('%H:%M:%S', time.localtime()), '   Erzeuge Übergangspunkte...')
layer_shortener = processing.run('native:lineintersections', {'INPUT': layer_ways_split, 'INTERSECT': layer_ways_split, 'OUTPUT': 'memory:'})['OUTPUT']
print(time.strftime('%H:%M:%S', time.localtime()), '   Puffere Übergangspunkte...')
layer_shortener = processing.run('native:buffer', { 'INPUT' : layer_shortener, 'DISTANCE' : 0.11, 'OUTPUT': 'memory:'})['OUTPUT']
print(time.strftime('%H:%M:%S', time.localtime()), '   Erzeuge Differenz...')
layer_ways_split = processing.run('native:difference', {'INPUT' : layer_ways_split, 'OVERLAY' : layer_shortener, 'OUTPUT': 'memory:'})['OUTPUT']

# Parkraumattribute jeweils für rechte und linke Seite übertragen
print(time.strftime('%H:%M:%S', time.localtime()), 'Parkraumattribute übertragen...')
layer_areas_snapped.setName('output_helper_parking_areas_snapped')
QgsProject.instance().addMapLayer(layer_areas_snapped, output_parking_areas)
# Nur Attribute von Flächen übertragen, die den gleichen Straßennamen tragen
street_names = layer_ways_split.uniqueValues(layer_ways_split.fields().indexFromName(ways_street_name_attr))
layer_ways_split_street_names = []
street_name_len = len(street_names)
count = 0
for street_name in street_names:
    # Fortschritt ausgeben
    count += 1
    if len(percent):
        if count / street_name_len * 100 >= percent[0]:
            print(time.strftime('%H:%M:%S', time.localtime()), f'Parkraumattribute übertragen ({percent.pop(0)} %)...')

    if street_name == NULL:
        continue

    layer_ways_split_street_name = processing.run('qgis:extractbyattribute', { 'INPUT' : layer_ways_split, 'FIELD' : ways_street_name_attr, 'VALUE' : street_name, 'OUTPUT': 'memory:'})['OUTPUT']
    for side in ['left', 'right']:
        processing.run('qgis:selectbyexpression', {'INPUT' : layer_areas_snapped, 'EXPRESSION' : f'"side" = \'{side}\' and "{areas_street_name_attr}" = \'{street_name.replace("'", "\\'")}\''})
        layer_ways_split_street_name = processing.run('native:joinattributesbylocation', {'INPUT': layer_ways_split_street_name, 'JOIN' : QgsProcessingFeatureSourceDefinition(layer_areas_snapped.id(), selectedFeaturesOnly=True), 'JOIN_FIELDS' : ['polygon_id','parking','orientation','markings','access','access:conditional','car_sharing','disabled','emergency','emergency:conditional','taxi','taxi:conditional','restriction','restriction:conditional','restriction:reason','maxstay','maxstay:conditional','fee','fee:conditional','zone','object:street'], 'METHOD' : 2, 'PREDICATE' : [5], 'PREFIX' : f'parking:{side}:', 'OUTPUT': 'memory:'})['OUTPUT']
    layer_ways_split_street_names.append(layer_ways_split_street_name)

# Attributübertragungs-Layer zusammenführen
print(time.strftime('%H:%M:%S', time.localtime()), '   Führe Attributübertragungs-Layer zusammen...')
layer_ways_split = processing.run('native:mergevectorlayers', { 'LAYERS' : layer_ways_split_street_names, 'OUTPUT': 'memory:'})['OUTPUT']
# Attribute bereinigen
layer_ways_split = processing.run('native:deletecolumn', {'INPUT' : layer_ways_split, 'COLUMN' : ['layer', 'path'], 'OUTPUT': 'memory:'})['OUTPUT']

# Primärtags korrigieren und parking=no ergänzen
for side in ['left', 'right']:
    layer_ways_split = processing.run('native:renametablefield', { 'INPUT' : layer_ways_split, 'FIELD' : f'parking:{side}:parking', 'NEW_NAME' : f'parking:{side}', 'OUTPUT': 'memory:'})['OUTPUT']
    layer_ways_split = processing.run('qgis:fieldcalculator', { 'INPUT' : layer_ways_split, 'FIELD_NAME' : f'parking:{side}', 'FORMULA' : f'if("parking:{side}" IS NULL, \'no\', "parking:{side}")', 'OUTPUT': 'memory:'})['OUTPUT']
    if not show_markings_no:
        layer_ways_split = processing.run('qgis:fieldcalculator', { 'INPUT' : layer_ways_split, 'FIELD_NAME' : f'parking:{side}:markings', 'FORMULA' : f'if("parking:{side}:markings" = \'no\', NULL, "parking:{side}:markings")', 'OUTPUT': 'memory:'})['OUTPUT']

# Bei Bedarf Ausgabedatensatz vereinfachen
print(time.strftime('%H:%M:%S', time.localtime()), 'Ausgabedatensatz vereinfachen...')

if delete_columns:
    # Attribute reduzieren
    print(time.strftime('%H:%M:%S', time.localtime()), '   Unnötige Spalten löschen...')
    layer_ways_split = processing.run('native:deletecolumn', {'INPUT' : layer_ways_split, 'COLUMN' : ['id', 'parking:left:polygon_id', 'parking:left:object:street', 'parking:right:polygon_id', 'parking:right:object:street'], 'OUTPUT': 'memory:'})['OUTPUT']

if simplify_output:
    # Wegsegmente mit gleichen Attributen zusammenführen
    print(time.strftime('%H:%M:%S', time.localtime()), '   Gleiche Wegsegmente zusammenführen...')
    layer_ways_split = processing.run('native:dissolve', { 'INPUT' : layer_ways_split, 'FIELD' : ['highway','name','parking:left','parking:left:orientation','parking:left:markings','parking:left:access','parking:left:access:conditional','parking:left:car_sharing','parking:left:disabled','parking:left:emergency','parking:left:emergency:conditional','parking:left:taxi','parking:left:taxi:conditional','parking:left:restriction','parking:left:restriction:conditional','parking:left:restriction:reason','parking:left:maxstay','parking:left:maxstay:conditional','parking:left:fee','parking:left:fee:conditional','parking:left:zone','parking:right','parking:right:orientation','parking:right:markings','parking:right:access','parking:right:access:conditional','parking:right:car_sharing','parking:right:disabled','parking:right:emergency','parking:right:emergency:conditional','parking:right:taxi','parking:right:taxi:conditional','parking:right:restriction','parking:right:restriction:conditional','parking:right:restriction:reason','parking:right:maxstay','parking:right:maxstay:conditional','parking:right:fee','parking:right:fee:conditional','parking:right:zone'], 'OUTPUT': 'memory:'})['OUTPUT']
    layer_ways_split = processing.run('native:multiparttosingleparts', { 'INPUT' : layer_ways_split, 'OUTPUT': 'memory:'})['OUTPUT']
    # gleiche left- und right-Attribute zu "both"-Schreibweise verkürzen
    print(time.strftime('%H:%M:%S', time.localtime()), '   Taggingschreibweise verkürzen...')
    layer_ways_split = processing.run('qgis:fieldcalculator', { 'INPUT' : layer_ways_split, 'FIELD_NAME': 'parking:both', 'FIELD_TYPE': 2, 'FIELD_LENGTH': 0, 'NEW_FIELD': True, 'FORMULA': 'if("parking:left"="parking:right", "parking:left", NULL)', 'OUTPUT': 'memory:'})['OUTPUT']
    tag_list = ['orientation', 'markings', 'access', 'access:conditional', 'car_sharing', 'disabled', 'emergency', 'emergency:conditional', 'taxi', 'taxi:conditional', 'restriction', 'restriction:conditional', 'restriction:reason', 'maxstay', 'maxstay:conditional', 'fee', 'fee:conditional', 'zone']
    for tag in tag_list:
        layer_ways_split = processing.run('qgis:fieldcalculator', { 'INPUT' : layer_ways_split, 'FIELD_NAME': f'parking:both:{tag}', 'FIELD_TYPE': 2, 'FIELD_LENGTH': 0, 'NEW_FIELD': True, 'FORMULA': f'if("parking:left:{tag}"="parking:right:{tag}", "parking:left:{tag}", NULL)', 'OUTPUT': 'memory:'})['OUTPUT']
    for side in ['left', 'right']:
        layer_ways_split = processing.run('qgis:fieldcalculator', { 'INPUT' : layer_ways_split, 'FIELD_NAME' : f'parking:{side}', 'FORMULA' : f'if("parking:both" IS NOT NULL, NULL, "parking:{side}")', 'OUTPUT': 'memory:'})['OUTPUT']
        for tag in tag_list:
            layer_ways_split = processing.run('qgis:fieldcalculator', { 'INPUT' : layer_ways_split, 'FIELD_NAME' : f'parking:{side}:{tag}', 'FORMULA' : f'if("parking:both:{tag}" IS NOT NULL, NULL, "parking:{side}:{tag}")', 'OUTPUT': 'memory:'})['OUTPUT']

print(time.strftime('%H:%M:%S', time.localtime()), 'Ausgabedatensatz einladen...')
layer_ways_split.setName('output_centerline_transfer')
QgsProject.instance().addMapLayer(layer_ways_split, True)

print(time.strftime('%H:%M:%S', time.localtime()), 'Centerline-Transfer abgeschlossen.')