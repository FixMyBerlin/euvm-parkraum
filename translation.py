#---------------------------------------------------------------------------#
#   Übersetzt die Attribute von eUVM-Parkraumflächen in Flächen mit         #
#   passenden OSM-Attributen.                                               #
#---------------------------------------------------------------------------#
#   Input: Aktiver Layer in QGIS.                                           #
#   Output: Temporärer Layer in QGIS.                                       #
#---------------------------------------------------------------------------#

import processing, time, re

# Sollen die ursprünglichen eUVM-Attribute im erzeugten OSM-Datensatz gelöscht werden? (Ausnahme: Polygon-ID bleibt zur Kontrolle enthalten)
delete_euvm_attributes = True

osm_attributes = ['amenity', 'parking', 'orientation', 'markings', 'capacity', 'access', 'access:conditional', 'car_sharing', 'disabled', 'emergency', 'emergency:conditional', 'taxi', 'taxi:conditional', 'restriction', 'restriction:conditional', 'restriction:reason', 'maxstay', 'maxstay:conditional', 'fee', 'fee:conditional', 'zone', 'street:name', 'warnings']
time_interval_replace = {
    "Di": "Tu",
    "Mi": "We",
    "Do": "Th",
    "So": "Su",
    " Uhr": "",
    ", ": ",",
}

# Bewirtschaftungszeiten pragmatisch hardcode übersetzen - bei dieser endlichen Zahl an Ausprägungen schneller, einfacher, sichererer
# (alternativ parsen mit "def parse_fee_time_interval", aber dann wäre für fee=yes + fee:conditional=no @ (...) noch ein Flip der Zeiträume erforderlich)
fee_conditional_translation = {
    "Mo-Fr 9-22 Uhr / Sa 9-18 Uhr"              : "no @ (Mo-Fr 00:00-09:00,22:00-24:00; Sa 00:00-09:00,18:00-24:00; Su)",   # "Mo-Fr 09:00-22:00; Sa 09:00-18:00"
    "Mo-Fr 09:00-22:00 Uhr, Sa 09:00-18:00 Uhr" : "no @ (Mo-Fr 00:00-09:00,22:00-24:00; Sa 00:00-09:00,18:00-24:00; Su)",   # "Mo-Fr 09:00-22:00; Sa 09:00-18:00"
    "Mo-Sa 09:00-22:00 Uhr"                     : "no @ (Mo-Sa 00:00-09:00,22:00-24:00; Su)",                               # "Mo-Sa 09:00-22:00"
    "Mo-So 9-24 Uhr"                            : "no @ (00:00-09:00)",                                                     # "Mo-Su 09:00-24:00"
    "Mo-Fr 09-20 Uhr / Sa 09-18 Uhr"            : "no @ (Mo-Fr 00:00-09:00,20:00-24:00; Sa 00:00-09:00,18:00-24:00; Su)",   # "Mo-Fr 09:00-20:00; Sa 09:00-18:00"
    "Mo-Fr 9-20 / Sa 9-18 Uhr"                  : "no @ (Mo-Fr 00:00-09:00,20:00-24:00; Sa 00:00-09:00,18:00-24:00; Su)",   # "Mo-Fr 09:00-20:00; Sa 09:00-18:00"
    "Mo-Sa 09:00-24:00 Uhr"                     : "no @ (Mo-Sa 00:00-09:00; Su)",                                           # "Mo-Sa 09:00-24:00"
    "Mo-Fr 09:00-20:00, Sa 09:00-18:00 Uhr"     : "no @ (Mo-Fr 00:00-09:00,20:00-24:00; Sa 00:00-09:00,18:00-24:00; Su)",   # "Mo-Fr 09:00-20:00; Sa 09:00-18:00"
    "Mo-Sa 9-24 Uhr"                            : "no @ (Mo-Sa 00:00-09:00; Su)",                                           # "Mo-Sa 09:00-24:00"
    "Mo-Sa 9-22 Uhr"                            : "no @ (Mo-Sa 00:00-09:00,22:00-24:00; Su)",                               # "Mo-Sa 09:00-22:00"
    "Mo-Fr 9-20 Uhr"                            : "no @ (Mo-Fr 00:00-09:00,20:00-24:00; Sa-Su)",                            # "Mo-Fr 09:00-20:00"
    "Mo-Sa / 9-20 Uhr"                          : "no @ (Mo-Sa 00:00-09:00,20:00-24:00; Su)",                               # "Mo-Sa 09:00-20:00"
    "Mo-Fr 9-20 Uhr / Sa 9-18 Uhr"              : "no @ (Mo-Fr 00:00-09:00,20:00-24:00; Sa 00:00-09:00,18:00-24:00; Su)",   # "Mo-Fr 09:00-20:00; Sa 09:00-18:00"
    "Mo-Fr 9-18 Uhr"                            : "no @ (Mo-Fr 00:00-09:00,18:00-24:00; Sa-Su)",                            # "Mo-Fr 09:00-18:00"
    "Mo-Fr 09:00-18:00 Uhr"                     : "no @ (Mo-Fr 00:00-09:00,18:00-24:00; Sa-Su)",                            # "Mo-Fr 09:00-18:00"
    "Mo-Sa 9-24 Uhr"                            : "no @ (Mo-Sa 00:00-09:00; Su)",                                           # "Mo-Sa 09:00-24:00"
    "Mo-Fr 9-19 Uhr / Sa 9-14 Uhr"              : "no @ (Mo-Fr 00:00-09:00,19:00-24:00; Sa 00:00-09:00,14:00-24:00; Su)",   # "Mo-Fr 09:00-19:00; Sa 09:00-14:00"
    "Mo-Sa 09:00-24:00 Uhr "                    : "no @ (Mo-Sa 00:00-09:00; Su)",                                           # "Mo-Sa 09:00-24:00"
    "Mo-Fr 09:00-20:00 Uhr, Sa 09:00-18:00 Uhr" : "no @ (Mo-Fr 00:00-09:00,20:00-24:00; Sa 00:00-09:00,18:00-24:00; Su)",   # "Mo-Fr 09:00-20:00; Sa 09:00-18:00"
    "Mo-Fr 9-20 Uhr/ Sa 9-18 Uhr"               : "no @ (Mo-Fr 00:00-09:00,20:00-24:00; Sa 00:00-09:00,18:00-24:00; Su)",   # "Mo-Fr 09:00-20:00; Sa 09:00-18:00"
    "Mo-Sa, 9-22 Uhr"                           : "no @ (Mo-Sa 00:00-09:00,22:00-24:00; Su)",                               # "Mo-Sa 09:00-22:00"
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
    # - falls die Wochentage den Wochentagen des Eintrags davor entsprechen, durch einfaches Komma ohne Leerzeichen zusammenfügen
    # - bei neuem Wochentag semikolongetrennt mit Leerzeichen
    # - falls die Zeit oder der Wochentag im Vergleich zum Eintrag davor zurückspringt, beziehen sich die Angaben vor und nach dem Zeitsprung auf "no_stopping" bzw. "no_parking"
    interval_str = ['', ''] # Zwei Teilstrings, falls no_stopping und no_parking gleichzeitig zu verschiedenen Zeiten gelten
    interval_idx = 0

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

    # Zeitsprünge suchen (Vergleich der ersten Stundenangabe bzw. der Wochentage), um Mehrfach-Angaben von Parkbeschränkungen möglichst zeitlich zu differenzieren
    for i in range(len(intervals)):
        if i == 0:
            interval_str[interval_idx] += f'{intervals[i][0]} {intervals[i][1]}'
        else:
            # Gleiche Wochentage: Zeitsprünge in den Zeitangaben suchen
            if intervals[i][0] == intervals[i - 1][0]:
                try:
                    if int(intervals[i][1][0:2].replace("0", "")) < int(intervals[i - 1][1][0:2].replace("0", "")):
                        if interval_idx == 1:
                            warnings = add_warning(warnings, feature, '[#12] Mehr als ein Zeitsprung in einer Geltungszeit.', 'Warning')
                        interval_idx = 1
                        interval_str[interval_idx] += f'{intervals[i][0]} {intervals[i][1]}'
                    else:
                        # Gleiche Wochentage: Mit Komma und ohne Leerzeichen trennen
                        interval_str[interval_idx] += f',{intervals[i][1]}'
                except:
                    warnings = add_warning(warnings, feature, '[#E1] Fehler bei Suche nach Zeitsprüngen in Zeitangaben.', 'Error')

            # Anderer Wochentag: Zeitsprünge in Wochentagen suchen oder Intervall anhängen
            else:
                try:
                    # Anderer Wochentag, der vor dem vorherigen Wochentag liegt: Zeitsprung - Angabe bezieht sich auf nächste Beschränkung
                    if weekday_num[intervals[i][0][0:2]] < weekday_num[intervals[i - 1][0][0:2]]:
                        if interval_idx == 1:
                            warnings = add_warning(warnings, feature, '[#12] Mehr als ein Zeitsprung in einer Geltungszeit.', 'Warning')
                        interval_idx = 1
                    # Anderer Wochentag ohne Zeitsprung: Mit Semikolon und Leerzeichen trennen
                    else:
                        interval_str[interval_idx] += '; '
                    interval_str[interval_idx] += f'{intervals[i][0]} {intervals[i][1]}'
                except:
                    warnings = add_warning(warnings, feature, '[#E2] Fehler bei Suche nach Zeitsprüngen in Wochentagsangaben.', 'Error')

    # "Mo-Su" und "00:00-24:00" kann weggekürzt werden
    for i in range(1):
        interval_str[i] = interval_str[i].replace("Mo-Su ", "").replace(" 00:00-24:00", "")

    # "Mo-Fr 05:00-16:00 Uhr"
    # "Do 21:00-24:00 Uhr, Fr-Sa 00:00-24:00 Uhr, So 00:00-6:00 Uhr"
    # "Mo-Fr 07:30-08:30 Uhr, Mo-Fr 13:00-18:00 Uhr"
    # "Mo-Fr 07:00-09:00 Uhr, Mo-Fr 15:00-18:00 Uhr, Sa 05:00-10:00 Uhr"
    # "Mo-Fr 06:00-08:00 Uhr, Mo-Fr 15:00-20:00 Uhr, Mo-Fr 08:00-15:00 Uhr"
    # "Mo-Sa"
    # "Mo-So"
    # "Mo-So 07:00-16:00 Uhr"
    # "Mo-Fr 08:00-16:00 Uhr, Sa 08:00-13:00 Uhr, Mo-Fr 16:00-24:00 Uhr, Sa 13:00-24:00 Uhr, So 09:00-24:00 Uhr"

    return interval_str, warnings

# def parse_fee_time_interval(euvm_fee_time_interval):
#     interval_str = euvm_fee_time_interval

#     # Scheib-/Syntaxfehler in Bewirtschaftungszeit beheben
#     interval_str = interval_str.replace("Sa,", "Sa")
#     interval_str = interval_str.replace("Sa /", "Sa")

#     # Besondere Schreibweisen behandeln
#     interval_str = interval_str.replace(" /", ",")
#     interval_str = interval_str.replace("/", ",")

#     for euvm, osm in time_interval_replace.items():
#         interval_str = interval_str.replace(euvm, osm)

#     # Zeitformat vereinheitlichen:
#     # a) vorangestellte 0 vor 0-9 Uhr ergänzen, falls nicht vorhanden (z.B. 9 -> 09)
#     interval_str = re.sub(r'\b([0-9])\b', r'0\1', interval_str)

#     # b) Stunden durch Minuten ergänzen, falls nicht vorhanden (":00")
#     interval_str = re.sub(r'\b(0?[1-9]|1[0-9]|2[0-4])\b(?!:00)', r'\1:00', interval_str)

#     # Im Fall der Bewirtschaftungszeiten behandeln die einzelnen Angaben immer getrennte Tage, also mit ";" statt "," trennen
#     interval_str = interval_str.replace(",", "; ")

#     return interval_str

def add_warning(warnings, feature, warning_str, type):
    print(time.strftime('%H:%M:%S', time.localtime()), f'[{type}][fid={feature['fid']}]{warning_str}')
    if warnings:
        warnings += '; '
    warnings += warning_str
    return warnings



print(time.strftime('%H:%M:%S', time.localtime()), 'Starte Attributübersetzung...')
print(time.strftime('%H:%M:%S', time.localtime()), 'Bereite Daten vor...')

# Reprojizieren
layer = iface.activeLayer()
layer = processing.run('native:reprojectlayer', { 'INPUT' : layer, 'TARGET_CRS' : QgsCoordinateReferenceSystem("EPSG:25833"), 'OUTPUT': 'memory:'})['OUTPUT']

# Zone-Attribut umbenennen, um nicht in Konflikt mit gleichnamigem OSM-Tag zu geraten
with edit(layer):
    idx_zone = layer.fields().indexFromName('zone')
    idx_euvm_zone = layer.fields().indexFromName('euvm_zone')
    if idx_zone != -1 and idx_euvm_zone == -1:
        layer.renameAttribute(idx_zone, 'euvm_zone')

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
idx_markings = layer.fields().indexFromName('markings')
idx_capacity = layer.fields().indexFromName('capacity')

idx_access = layer.fields().indexFromName('access')
idx_access_conditional = layer.fields().indexFromName('access:conditional')
idx_car_sharing = layer.fields().indexFromName('car_sharing')
idx_disabled = layer.fields().indexFromName('disabled')
idx_emergency = layer.fields().indexFromName('emergency')
idx_emergency_conditional = layer.fields().indexFromName('emergency:conditional')
idx_taxi = layer.fields().indexFromName('taxi')
idx_taxi_conditional = layer.fields().indexFromName('taxi:conditional')
idx_restriction = layer.fields().indexFromName('restriction')
idx_restriction_conditional = layer.fields().indexFromName('restriction:conditional')
idx_restriction_reason = layer.fields().indexFromName('restriction:reason')
idx_maxstay = layer.fields().indexFromName('maxstay')
idx_maxstay_conditional = layer.fields().indexFromName('maxstay:conditional')
idx_fee = layer.fields().indexFromName('fee')
idx_fee_conditional = layer.fields().indexFromName('fee:conditional')
idx_zone = layer.fields().indexFromName('zone')
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

        # position (Attribut "parking")
        euvm_position = feature['parkort']
        position = 'yes'
        if euvm_position == 'Fahrbahn':
            position = 'lane'
        elif euvm_position == 'Gehwegparken_halb':
            position = 'half_on_kerb'
        elif euvm_position == 'Gehwegparken_ganz':
            position = 'on_kerb'
        elif euvm_position == 'Parkbucht':
            position = 'street_side'
        
        feature.setAttribute(idx_position, position)

        # orientation
        euvm_orientation = feature['ausrichtung']
        orientation = NULL
        if euvm_orientation == 'Längs':
            orientation = 'parallel'
        elif euvm_orientation == 'Schräg':
            orientation = 'diagonal'
        elif euvm_orientation == 'Quer':
            orientation = 'perpendicular'

        if orientation:
            feature.setAttribute(idx_orientation, orientation)

        # markings
        euvm_markings = feature['markierung_parkraum']
        markings = NULL
        if euvm_markings == 'markiert':
            markings = 'yes'
        elif euvm_markings == 'nicht markiert':
            markings = 'no'

        if markings:
            feature.setAttribute(idx_markings, markings)

        # capacity
        euvm_capacity = feature['errechnete_anzahl_parkplaetze']
        feature.setAttribute(idx_capacity, euvm_capacity)

        # Parkbeschränkungen
        #--------------------

        # restriction und access
        access = NULL
        access_conditional = NULL
        car_sharing = NULL
        disabled = NULL
        emergency = NULL
        emergency_conditional = NULL
        taxi = NULL
        taxi_conditional = NULL
        restriction = NULL
        restriction_conditional = NULL
        restriction_reason = NULL

        warnings = ''

        euvm_restriction = feature['beschraenkung']
        euvm_restriction_time_interval = feature['geltungszeit_der_beschraenkung']
        euvm_restriction_reason = feature['grund_fuer_beschraenkung']
        euvm_car_sharing = feature['carsharing']
        euvm_disabled = feature['nur_schwerbehinderte']
        euvm_charging_only = feature['ladesaeule']

        # Carsharing und Schwerbehindertenparkplätze drücken sich durch access-Tagging aus
        if euvm_car_sharing == 'ja':
            access = 'no'
            car_sharing = 'designated'

        if euvm_disabled == 'ja':
            access = 'no'
            disabled = 'designated'

        time_interval = NULL
        if euvm_restriction_time_interval:
            if euvm_restriction_time_interval != 'Mo-So':
               time_interval, warnings = parse_time_interval(euvm_restriction_time_interval, warnings)
            else:
                warnings = add_warning(warnings, feature, '[#11] Geltungszeit der Parkbeschränkung umfasst "Mo-So", also alle Zeiten, und ist daher unnötig.', 'Warning')

        if euvm_restriction == 'Haltverbot;Eingeschränktes Haltverbot':
            if time_interval:
                if time_interval[1]:
                    restriction_conditional = f'no_stopping @ ({time_interval[0]}); no_parking @ ({time_interval[1]})'
                else:
                    restriction = 'no_stopping;no_parking'
                    warnings = add_warning(warnings, feature, '[#01] Gemeinsames Haltverbot und Eingeschränktes Haltverbot ohne Differenzierung der Geltungszeit.', 'Warning')
            else:
                warnings = add_warning(warnings, feature, '[#00] Gemeinsames Haltverbot und Eingeschränktes Haltverbot ohne Angabe der Geltungszeit.', 'Warning')

        else:
            if euvm_restriction == 'Haltverbot':
                restriction = 'no_stopping'
            elif euvm_restriction == 'Eingeschränktes Haltverbot':
                restriction = 'no_parking'
            
            # Wenn Grund für Beschränkung in Carsharing oder Schwerbehindertenparkplatz liegt, dann keine restriction übernehmen (da durch access ausgedrückt)
            if restriction and euvm_restriction_reason == 'Andere (Restriktion)' and (car_sharing or disabled):
                restriction = NULL

            # Grund für Beschränkung oder besondere Beschränkungsattribute können Default-Beschränkung präzisieren
            if euvm_restriction_reason == 'Ladezone':
                restriction = 'loading_only'

            if euvm_restriction_reason == 'Taxi':
                if time_interval:
                    restriction_conditional = NULL
                    if access != 'no':
                        access_conditional = f'no @ ({time_interval[0]})'
                    if taxi != 'designated':
                        taxi_conditional = f'designated @ ({time_interval[0]})'
                    if time_interval[1]:
                        warnings = add_warning(warnings, feature, '[#09] Zeitsprung bei Geltungszeit eines Taxiwarteplatzes.', 'Warning')
                else:
                    restriction = NULL
                    access = 'no'
                    taxi = 'designated'

            if euvm_restriction_reason == 'Polizeifahrzeuge':
                if time_interval:
                    restriction_conditional = NULL
                    if access != 'no':
                        access_conditional = f'no @ ({time_interval[0]})'
                    if emergency != 'designated':
                        emergency_conditional = f'designated @ ({time_interval[0]})'
                    if time_interval[1]:
                        warnings = add_warning(warnings, feature, '[#10] Zeitsprung bei Geltungszeit eines Stellplatzes für Polizeifahrzeuge.', 'Warning')
                else:
                    restriction = NULL
                    access = 'no'
                    emergency = 'designated'

            if euvm_charging_only == 'ja':
                restriction = 'charging_only'

            # Je nach dem, ob eine Geltungszeit angegeben ist oder nicht, als conditional restriction ausdrücken oder nicht
            if time_interval:
                if restriction:
                    if time_interval[0]:
                        restriction_conditional = f'{restriction} @ ({time_interval[0]})'
                    else:
                        warnings = add_warning(warnings, feature, '[#03] Fehlende Angabe der Geltungszeit der Parkbeschränkung.', 'Warning')
                    if time_interval[1]:
                        warnings = add_warning(warnings, feature, '[#02] Nicht interpretierter Zeitsprung in Geltungszeit der Parkbeschränkung.', 'Warning')
                    restriction = NULL
                else:
                    if euvm_restriction_time_interval and not euvm_restriction:
                        warnings = add_warning(warnings, feature, '[#04] Angabe einer Geltungszeit ohne Angabe einer Parkbeschränkung.', 'Warning')

            if restriction and euvm_restriction_reason == 'Bussonderfahrstreifen':
                restriction_reason = 'bus_lane'

        if access:
            feature.setAttribute(idx_access, access)
        if access_conditional:
            feature.setAttribute(idx_access_conditional, access_conditional)
        if car_sharing:
            feature.setAttribute(idx_car_sharing, car_sharing)
        if disabled:
            feature.setAttribute(idx_disabled, disabled)
        if emergency:
            feature.setAttribute(idx_emergency, emergency)
        if emergency_conditional:
            feature.setAttribute(idx_emergency_conditional, emergency_conditional)
        if taxi:
            feature.setAttribute(idx_taxi, taxi)
        if taxi_conditional:
            feature.setAttribute(idx_taxi_conditional, taxi_conditional)
        if restriction:
            feature.setAttribute(idx_restriction, restriction)
        if restriction_conditional:
            feature.setAttribute(idx_restriction_conditional, restriction_conditional)
        if restriction_reason:
            feature.setAttribute(idx_restriction_reason, restriction_reason)

        # maxstay
        euvm_maxstay = feature['hoechstparkdauer']
        euvm_maxstay_time_interval = feature['geltungszeit_der_hoechstparkdauer']
        if euvm_maxstay_time_interval:
            euvm_maxstay_time_interval = euvm_maxstay_time_interval.replace('\n', '')

        maxstay = NULL
        maxstay_conditional = NULL

        if euvm_maxstay:
            maxstay = euvm_maxstay.replace('h', ' hours').replace('1 hours', '1 hour').replace('min', ' minutes')

        if euvm_maxstay_time_interval:
            time_interval, warnings = parse_time_interval(euvm_maxstay_time_interval, warnings)
            if maxstay:
                feature.setAttribute(idx_maxstay_conditional, f'{maxstay} @ ({time_interval[0]})')
                if time_interval[1]:
                    warnings = add_warning(warnings, feature, '[#08] Zeitsprung in Geltungszeit der Höchstparkdauer – maxstay:conditional unvollständig.', 'Warning')
            else:
                warnings = add_warning(warnings, feature, '[#07] Geltungszeit einer Höchstparkdauer ohne Angabe der Höchstparkdauer selbst.', 'Warning')
        else:
            if maxstay:
                feature.setAttribute(idx_maxstay, maxstay)

        # fee
        euvm_fee = feature['parkgebuehr']
        euvm_fee_time_interval = feature['bewirtschaftungszeit']
        if euvm_fee_time_interval:
            euvm_fee_time_interval = euvm_fee_time_interval.replace('\n', '')

        fee = 'no'
        if euvm_fee and not (car_sharing or disabled or emergency or taxi) and restriction != 'loading_only':
            fee = 'yes'

        fee_conditional = NULL
        if euvm_fee_time_interval:
            if euvm_fee_time_interval in fee_conditional_translation:
                fee_conditional = fee_conditional_translation[euvm_fee_time_interval]
            else:
                warnings = add_warning(warnings, feature, '[#05] Bewirtschaftungszeit nicht in Übersetzungstabelle für fee:conditional enthalten.', 'Warning')

        feature.setAttribute(idx_fee, fee)
        if fee_conditional:
            if fee == 'yes':
                feature.setAttribute(idx_fee_conditional, fee_conditional)
            else:
                if not euvm_fee:
                    warnings = add_warning(warnings, feature, '[#06] Bewirtschaftungszeit, aber keine Parkgebühr angegeben.', 'Warning')

        # # zone
        # euvm_zone = feature['euvm_zone']
        # if euvm_zone:
        #     feature.setAttribute(idx_zone, euvm_zone)

        # Straßennamen übernehmen
        euvm_street_name = feature['strassenname']
        feature.setAttribute(idx_street_name, euvm_street_name)

        # Datenwarnungen für jede Fläche speichern
        if warnings:
            feature.setAttribute(idx_warnings, warnings)

        layer.updateFeature(feature)

# optional: eUVM-Attribute entfernen (außer Polygon-ID)
if delete_euvm_attributes:
    osm_attributes.insert(0, 'polygon_id')
    layer = processing.run('native:retainfields', { 'INPUT' : layer, 'FIELDS' : osm_attributes, 'OUTPUT': 'memory:'})['OUTPUT']

layer.setName('output_parking_areas_translated')
QgsProject.instance().addMapLayer(layer, True)

print(time.strftime('%H:%M:%S', time.localtime()), 'Attributübersetzung fertiggestellt.')

# Datenkorrekturen nach Abschluss:
# - (56x) Segmente mit "restriction" = 'no_stopping;no_parking' müssen manuell auf Gültigkeitszeitraum geprüft werden
# - (988x)(!) Flächen mit (dauerhaft) restriction=no_parking/no_stopping prüfen, ob sie tatsächlich dauerhaft nicht beparkt werden dürfen (warum sind die dann im Datensatz enthalten?)
#   -> dafür am besten einen Style anlegen, der diese Segmente hervorhebt
# - (72x) Flächen mit Mehrfachangabe zum Grund von Beschränkungen manuell prüfen ("grund_fuer_beschraenkung" LIKE '%;%')
# - (87x) restriction:reason=bus_lane manuell prüfen, ob diese Beschränkung nur temporär gilt
# - Parkzonen (zone) aus externem Datensatz ergänzen
# - private Schwerbehindertenparkplätze abgleichen (disabled=private statt disabled=designated)