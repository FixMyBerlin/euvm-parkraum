#---------------------------------------------------------------------------#
#   Übersetzt die Attribute von eUVM-Parkraumflächen in Flächen mit         #
#   passenden OSM-Attributen (für den Außenstadt-Datensatz).                #
#---------------------------------------------------------------------------#
#   Input: Aktiver Layer in QGIS.                                           #
#   Output: Temporärer Layer in QGIS.                                       #
#---------------------------------------------------------------------------#

import processing, time, re

# Sollen die ursprünglichen eUVM-Attribute im erzeugten OSM-Datensatz gelöscht werden? (Ausnahme: Polygon-ID bleibt zur Kontrolle enthalten)
delete_euvm_attributes = True

osm_attributes = ['amenity', 'parking', 'orientation', 'capacity', 'restriction', 'restriction:conditional', 'maxstay', 'street:name', 'warnings']
time_interval_replace = {
    "Di": "Tu",
    "Mi": "We",
    "Do": "Th",
    "So": "Su",
    " Uhr": "",
    ", ": ",",
}

weekday_num = {
    "Mo": 1,
    "Di": 2,
    "Tu": 2,
    "Mi": 3,
    "We": 3,
    "Do": 4,
    "Th": 4,
    "Fr": 5,
    "Sa": 6,
    "So": 7,
    "Su": 7
}

def parse_time_interval(euvm_time_interval, warnings):
    interval_str = euvm_time_interval
    for euvm, osm in time_interval_replace.items():
        interval_str = interval_str.replace(euvm, osm)

    # Liste der einzelnen Intervalle erzeugen mit zwei Bestandteilen: Den Wochentagen und den Zeiten
    intervals = interval_str.split(",")
    for i in range(len(intervals)):
        parts = intervals[i].split(" ", 1)
        weekdays = parts[0]
        times = "00:00-24:00"
        if len(parts) > 1:
            times = re.sub(r'\b([0-9])\b', r'0\1', parts[1]) # vorangestellte 0 vor 0-9 Uhr ergänzen, falls nicht vorhanden (z.B. 9 -> 09)
        intervals[i] = [weekdays, times]

    # Intervalle durchgehen und zusammensetzen:
    # - falls die Wochentage den Wochentagen des Eintrags davor entsprechen oder es einen Sprung zurück gibt (z.B. von "Sa" auf "Mo"), Warnung zur manuellen Nachkontrolle erzeugen
    # - bei neuem Wochentag semikolongetrennt mit Leerzeichen
    interval_str = ''

    # Überhängende Zeiten verbinden (z.B. 20:00-00:00 + 00:00-05:00 -> 20:00-05:00)
    for i in range(len(intervals)):
        if i > 0:
            try:
                if intervals[i][0] == intervals[i - 1][0]:
                    if intervals[i][1][0:2] == "00":
                        intervals[i - 1][1] = intervals[i - 1][1][0:6] + intervals[i][1][6:8] + intervals[i - 1][1][8:]
                        intervals.pop(i)
            except:
                continue

    for i in range(len(intervals)):
        if i == 0:
            interval_str += f'{intervals[i][0]} {intervals[i][1]}'
        else:
            # Gleiche Wochentage: Warnung erzeugen
            if intervals[i][0] == intervals[i - 1][0]:
                interval_str += f',{intervals[i][1]}'
                warnings = add_warning(warnings, feature, '[#52] Wiederholende Wochentage in Geltungszeit der Ladezone manuell prüfen.', 'Warning')

            # Anderer Wochentag: Mit Semikolon anhängen
            else:
                interval_str += f'; {intervals[i][0]} {intervals[i][1]}'

                # Warnung zur manuellen Nachkontrolle erzeugen, falls Wochentag wieder zurückspringt (z.B. "Mo" nach "Sa")
                if weekday_num[intervals[i][0][0:2]] < weekday_num[intervals[i - 1][0][0:2]]:
                    warnings = add_warning(warnings, feature, '[#53] Zeitsprung in Wochentagen der Geltungszeit der Ladezone manuell prüfen.', 'Warning')

    # "Mo-Su" und "00:00-24:00" kann weggekürzt werden
    interval_str = interval_str.replace("Mo-Su ", "").replace(" 00:00-24:00", "")

    return interval_str, warnings

def add_warning(warnings, feature, warning_str, type):
    # print(time.strftime('%H:%M:%S', time.localtime()), f'[{type}][fid={feature['fid']}]{warning_str}')
    if warnings:
        warnings += '; '
    warnings += warning_str
    return warnings



print(time.strftime('%H:%M:%S', time.localtime()), 'Starte Attributübersetzung (Datensatz: Außenstadt)...')
print(time.strftime('%H:%M:%S', time.localtime()), 'Bereite Daten vor...')

# Reprojizieren
layer = iface.activeLayer()
layer = processing.run('native:reprojectlayer', { 'INPUT' : layer, 'TARGET_CRS' : QgsCoordinateReferenceSystem("EPSG:25833"), 'OUTPUT': 'memory:'})['OUTPUT']

# OSM-Attribute anlegen
with edit(layer):
    for attr in osm_attributes:
        if layer.fields().indexFromName(attr) == -1:
            if attr == 'capacity':
                layer.addAttribute(QgsField(attr, QVariant.Int))
            else:
                layer.addAttribute(QgsField(attr, QVariant.String))
    layer.updateFields()

idx_amenity = layer.fields().indexFromName('amenity')
idx_position = layer.fields().indexFromName('parking') # position = Attribut "parking"
idx_orientation = layer.fields().indexFromName('orientation')
idx_capacity = layer.fields().indexFromName('capacity')

idx_restriction = layer.fields().indexFromName('restriction')
idx_restriction_conditional = layer.fields().indexFromName('restriction:conditional')
idx_maxstay = layer.fields().indexFromName('maxstay')
idx_street_name = layer.fields().indexFromName('street:name')
idx_warnings = layer.fields().indexFromName('warnings')

print(time.strftime('%H:%M:%S', time.localtime()), 'Erstelle Daten (0 %)...')

# OSM-Attribute füllen
feature_count = layer.featureCount()
count = 0
percent = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
for feature in layer.getFeatures():
    with edit(layer):

        # Fortschritt ausgeben
        count += 1
        if len(percent):
            if count / feature_count * 100 >= percent[0]:
                print(time.strftime('%H:%M:%S', time.localtime()), f'Erstelle Daten ({percent.pop(0)} %)...')

        # physische Eigenschaften
        #-------------------------

        feature.setAttribute(idx_amenity, 'parking')

        # position (nicht im Datensatz enthalten - unspezifisch lassen)
        parking = 'yes'

        # orientation
        euvm_orientation = feature['Ausrichtung']
        orientation = NULL
        if euvm_orientation == 'Längs':
            orientation = 'parallel'
        elif euvm_orientation == 'Schräg':
            orientation = 'diagonal'
        elif euvm_orientation == 'Quer':
            orientation = 'perpendicular'

        if orientation:
            feature.setAttribute(idx_orientation, orientation)

        # capacity
        euvm_capacity = feature['Errechnete Anzahl Parkplätze']
        feature.setAttribute(idx_capacity, euvm_capacity)

        # Parkbeschränkungen
        #--------------------

        # restriction
        restriction = NULL
        restriction_conditional = NULL

        warnings = ''

        euvm_restriction = feature['Category']
        euvm_loading_time_interval = feature['Geltungszeit der Ladezone']

        # if euvm_restriction == 'Parken (ohne Beschränkungen)':

        # if euvm_restriction == 'Parking':

        if euvm_restriction in ['Nutzungsgruppe', 'Beschränkungen']:
            restriction = 'yes'

        if euvm_restriction == 'Parken mit zeitlicher Beschränkung':
            restriction_conditional = 'yes'

        if euvm_restriction == 'Parkverbot':
            restriction = 'no_parking'
            parking = 'no'

        time_interval = NULL
        if euvm_restriction == 'Ladezone':
            if euvm_loading_time_interval:
                if euvm_loading_time_interval != 'Mo-So':
                    time_interval, warnings = parse_time_interval(euvm_loading_time_interval, warnings)
                    restriction_conditional = f'loading_only @ ({time_interval})'
                else:
                    warnings = add_warning(warnings, feature, '[#51] Geltungszeit der Ladezone umfasst "Mo-So", also alle Zeiten, und ist daher unnötig.', 'Warning')
                    restriction = 'loading_only'
            else:
                restriction = 'loading_only'
    
        if restriction:
            feature.setAttribute(idx_restriction, restriction)
        if restriction_conditional:
            feature.setAttribute(idx_restriction_conditional, restriction_conditional)

        # maxstay
        if euvm_restriction == 'Beschränkte Parkdauer':
            feature.setAttribute(idx_maxstay, 'yes')

        # Straßennamen übernehmen
        euvm_street_name = feature['Straßenname']
        feature.setAttribute(idx_street_name, euvm_street_name)

        # Hinweis, falls Baustelle vermerkt ist
        euvm_construction = feature['Baustelle']
        if euvm_construction:
            warnings = add_warning(warnings, feature, '[#30] Baustelle im Befahrungszeitraum Innovitas 2021.', 'Warning')

        # Datenwarnungen für jede Fläche speichern
        if warnings:
            feature.setAttribute(idx_warnings, warnings)

        feature.setAttribute(idx_position, parking)

        layer.updateFeature(feature)

# Polygon-ID umbenennen, damit sie dem Schema der Innenstadt-Daten entspricht
layer = processing.run('native:renametablefield', { 'INPUT' : layer, 'FIELD' : 'Polygon-ID', 'NEW_NAME' : 'polygon_id', 'OUTPUT': 'memory:'})['OUTPUT']

# optional: eUVM-Attribute entfernen (außer Polygon-ID)
if delete_euvm_attributes:
    osm_attributes.insert(0, 'polygon_id')
    layer = processing.run('native:retainfields', { 'INPUT' : layer, 'FIELDS' : osm_attributes, 'OUTPUT': 'memory:'})['OUTPUT']

layer.setName('output_parking_areas_translated_aussenstadt')
QgsProject.instance().addMapLayer(layer, True)

print(time.strftime('%H:%M:%S', time.localtime()), 'Attributübersetzung fertiggestellt.')