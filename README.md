# euvm-parkraum

Scripte zur "Übersetzung" der eUVM-Parkraumdaten in das OSM-Datenschema mit PyQGIS (Python-Scripte zur Ausführung in der QGIS-Python-Konsole). Welche Layer als Input benötigt werden, ist jeweils in den Scriptköpfen definiert.

1. translation.py (bzw. für den Außenring-Datensatz translation_aussenstadt.py) nimmt die eUVM-Polygone und übersetzt deren Attribute in OSM-Tags (inkl. parsing von Parkbeschränkungen).
2. side.py nimmt a) die Polygone mit übersetzten Tags sowie b) einen Straßen-Liniendatensatz und ordnet jedem Parkplatz-Polygon zu, auf welcher Straßenseite es liegt.
3. centerline_transfer.py überträgt die Parkraumattribute von den Flächen an die nächstgelegenen Straßenlinien.
