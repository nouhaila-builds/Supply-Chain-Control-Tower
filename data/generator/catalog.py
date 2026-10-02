"""Static fictional European supply-chain catalog.

Coordinates are city-area locations, offset when several facilities share a city
so geographic markers remain distinguishable.
"""

from __future__ import annotations

# id, name, city, country, lat, lon
SUPPLIERS: list[tuple[str, str, str, str, float, float]] = [
    ("S-001", "Elbe Alloy Works GmbH", "Hamburg", "Germany", 53.58, 10.05),
    ("S-002", "Neckar Precision GmbH", "Stuttgart", "Germany", 48.74, 9.22),
    ("S-003", "Isar Circuit Works GmbH", "Munich", "Germany", 48.18, 11.55),
    ("S-004", "Rhein Polymer GmbH", "Cologne", "Germany", 50.94, 6.91),
    ("S-005", "Saxon Components GmbH", "Leipzig", "Germany", 51.34, 12.40),
    ("S-006", "Franconia Metals GmbH", "Nuremberg", "Germany", 49.45, 11.12),
    ("S-007", "Weser Fabrication GmbH", "Bremen", "Germany", 53.08, 8.85),
    ("S-008", "Elbe Ceramics GmbH", "Dresden", "Germany", 51.05, 13.78),
    ("S-009", "Rhône Assemblies SAS", "Lyon", "France", 45.78, 4.78),
    ("S-010", "Nord Textile Parts SAS", "Lille", "France", 50.67, 3.10),
    ("S-011", "Garonne Aero Parts SAS", "Toulouse", "France", 43.60, 1.40),
    ("S-012", "Loire Packaging SAS", "Nantes", "France", 47.22, -1.55),
    ("S-013", "Rhin Electronics SAS", "Strasbourg", "France", 48.58, 7.75),
    ("S-014", "Méditerranée Polymers SAS", "Marseille", "France", 43.30, 5.37),
    ("S-015", "Aquitaine Materials SAS", "Bordeaux", "France", 44.84, -0.58),
    ("S-016", "Alpine Sensors SAS", "Grenoble", "France", 45.19, 5.72),
    ("S-017", "Seine Fasteners SAS", "Rouen", "France", 49.44, 1.10),
    ("S-018", "Saône Mécanique SAS", "Dijon", "France", 47.32, 5.04),
    ("S-019", "Lambro Components SpA", "Milan", "Italy", 45.50, 9.14),
    ("S-020", "Po Valley Motors SpA", "Turin", "Italy", 45.07, 7.69),
    ("S-021", "Emilia Castings SpA", "Bologna", "Italy", 44.49, 11.34),
    ("S-022", "Adriatic Glass SpA", "Venice", "Italy", 45.44, 12.32),
    ("S-023", "Vesuvio Packaging SpA", "Naples", "Italy", 40.85, 14.27),
    ("S-024", "Arno Textiles SpA", "Florence", "Italy", 43.77, 11.26),
    ("S-025", "Llobregat Plastics SL", "Barcelona", "Spain", 41.42, 2.12),
    ("S-026", "Turia Electronics SL", "Valencia", "Spain", 39.51, -0.34),
    ("S-027", "Nervión Steel SL", "Bilbao", "Spain", 43.26, -2.93),
    ("S-028", "Guadalquivir Parts SL", "Seville", "Spain", 37.39, -5.98),
    ("S-029", "Ebro Polymers SL", "Zaragoza", "Spain", 41.65, -0.89),
    ("S-030", "Vistula Components Sp. z o.o.", "Warsaw", "Poland", 52.26, 21.05),
    ("S-031", "Wisła Metals Sp. z o.o.", "Krakow", "Poland", 50.06, 19.94),
    ("S-032", "Oder Fabrication Sp. z o.o.", "Wroclaw", "Poland", 51.11, 17.04),
    ("S-033", "Baltic Fasteners Sp. z o.o.", "Gdansk", "Poland", 54.35, 18.65),
    ("S-034", "Maas Harbour Parts BV", "Rotterdam", "Netherlands", 51.88, 4.52),
    ("S-035", "Brabant Circuits BV", "Eindhoven", "Netherlands", 51.44, 5.47),
    ("S-036", "Dom Castings BV", "Utrecht", "Netherlands", 52.09, 5.12),
    ("S-037", "Scheldt Chemicals NV", "Antwerp", "Belgium", 51.25, 4.45),
    ("S-038", "Meuse Steel NV", "Liège", "Belgium", 50.63, 5.58),
    ("S-039", "Vltava Precision s.r.o.", "Prague", "Czechia", 50.08, 14.44),
    ("S-040", "Moravia Alloys s.r.o.", "Brno", "Czechia", 49.20, 16.61),
    ("S-041", "Göta Marine Parts AB", "Gothenburg", "Sweden", 57.75, 11.99),
    ("S-042", "Mälaren Electronics AB", "Stockholm", "Sweden", 59.33, 18.07),
    ("S-043", "Douro Fibre SA", "Porto", "Portugal", 41.16, -8.63),
    ("S-044", "Tejo Components SA", "Lisbon", "Portugal", 38.76, -9.15),
    ("S-045", "Danube Instruments GmbH", "Vienna", "Austria", 48.24, 16.41),
    ("S-046", "Styria Motors GmbH", "Graz", "Austria", 47.07, 15.44),
    ("S-047", "Dâmbovița Assemblies SRL", "Bucharest", "Romania", 44.43, 26.10),
    ("S-048", "Transylvania Metals SRL", "Cluj-Napoca", "Romania", 46.77, 23.62),
    ("S-049", "Midlands Forge Ltd", "Birmingham", "United Kingdom", 52.52, -1.85),
    ("S-050", "Irwell Textiles Ltd", "Manchester", "United Kingdom", 53.48, -2.24),
]

FACTORIES: list[tuple[str, str, str, str, float, float]] = [
    ("F-01", "Stuttgart Plant", "Stuttgart", "Germany", 48.82, 9.14),
    ("F-02", "Lyon Plant", "Lyon", "France", 45.80, 4.90),
    ("F-03", "Milan Plant", "Milan", "Italy", 45.42, 9.25),
    ("F-04", "Poznan Plant", "Poznan", "Poland", 52.41, 16.93),
    ("F-05", "Valencia Plant", "Valencia", "Spain", 39.44, -0.42),
]

# Spec IDs are not sequential: W-042 is the injected inbound-delay site.
WAREHOUSES: list[tuple[str, str, str, str, float, float]] = [
    ("W-011", "Rotterdam DC", "Rotterdam", "Netherlands", 51.95, 4.42),
    ("W-018", "Hamburg DC", "Hamburg", "Germany", 53.52, 9.93),
    ("W-023", "Antwerp DC", "Antwerp", "Belgium", 51.19, 4.36),
    ("W-031", "Lille DC", "Lille", "France", 50.60, 3.02),
    ("W-042", "Frankfurt DC", "Frankfurt", "Germany", 50.11, 8.68),
    ("W-055", "Lyon DC", "Lyon", "France", 45.70, 4.86),
    ("W-061", "Milan DC", "Milan", "Italy", 45.49, 9.22),
    ("W-074", "Warsaw DC", "Warsaw", "Poland", 52.20, 20.95),
    ("W-083", "Barcelona DC", "Barcelona", "Spain", 41.35, 2.14),
    ("W-090", "Birmingham DC", "Birmingham", "United Kingdom", 52.45, -1.92),
]

# id, name, city, country, region, lat, lon
HUBS: list[tuple[str, str, str, str, str, float, float]] = [
    ("H-301", "Paris Hub", "Paris", "France", "France", 48.86, 2.35),
    ("H-302", "Lyon Hub", "Lyon", "France", "France", 45.76, 4.83),
    ("H-303", "Lille Hub", "Lille", "France", "France", 50.64, 3.08),
    ("H-310", "Munich Hub", "Munich", "Germany", "DACH", 48.14, 11.58),
    ("H-311", "Berlin Hub", "Berlin", "Germany", "DACH", 52.52, 13.40),
    ("H-312", "Vienna Hub", "Vienna", "Austria", "DACH", 48.21, 16.37),
    ("H-320", "Milan Hub", "Milan", "Italy", "Italy", 45.46, 9.19),
    ("H-321", "Rome Hub", "Rome", "Italy", "Italy", 41.90, 12.50),
    ("H-330", "Madrid Hub", "Madrid", "Spain", "Iberia", 40.42, -3.70),
    ("H-331", "Lisbon Hub", "Lisbon", "Portugal", "Iberia", 38.72, -9.14),
    ("H-340", "Rotterdam Hub", "Rotterdam", "Netherlands", "Benelux", 51.90, 4.48),
    ("H-341", "Brussels Hub", "Brussels", "Belgium", "Benelux", 50.85, 4.35),
    ("H-350", "Birmingham Hub", "Birmingham", "United Kingdom", "UK & Ireland", 52.48, -1.89),
    ("H-360", "Warsaw Hub", "Warsaw", "Poland", "Central Europe", 52.23, 21.01),
    ("H-370", "Gothenburg Hub", "Gothenburg", "Sweden", "Nordics", 57.71, 11.97),
]

CUSTOMER_NAMES: list[str] = [
    "Nordlicht Markets",
    "Mercia Household",
    "Halle Retail Group",
    "Atelier Marchand",
    "Brera Casa",
    "Svea Home",
    "Danube Outlet",
    "Thames & Moor",
    "Ebro Living",
    "Alpine Basket",
    "Loire Provisions",
    "Po Goods",
    "Scheldt Market",
    "Vistula Trade",
    "Sierra Familiar",
    "Canal House Retail",
    "Riviera Domus",
    "Northsea Pantry",
    "Seine & Co",
    "Midlands General",
    "Tagus Mart",
    "Isar Living",
    "Fjord Household",
    "Benelux Basket",
    "Carpathia Shop",
    "Cinder & Co",
    "Porto Largo Stores",
    "Baltic Shelf",
    "Gotha Consumer",
    "Weser General",
]

CATEGORIES: list[str] = [
    "Industrial Components",
    "Electronics",
    "Automotive Parts",
    "Packaging",
    "Consumer Goods",
]

PARTS: list[str] = [
    "bearing housing",
    "servo assembly",
    "control board",
    "seal kit",
    "fastener set",
    "polymer crate",
    "sensor module",
    "wiring harness",
    "textile roll",
    "pump impeller",
    "valve body",
    "display panel",
    "carton blank",
    "motor mount",
    "filter element",
    "cable assembly",
    "hinge set",
    "insulation pack",
    "gear blank",
    "handle kit",
]

# Country of the supplier determines its primary factory.
FACTORY_BY_COUNTRY: dict[str, str] = {
    "Germany": "F-01",
    "Netherlands": "F-01",
    "Belgium": "F-01",
    "Sweden": "F-01",
    "United Kingdom": "F-01",
    "France": "F-02",
    "Italy": "F-03",
    "Poland": "F-04",
    "Czechia": "F-04",
    "Austria": "F-04",
    "Romania": "F-04",
    "Spain": "F-05",
    "Portugal": "F-05",
}

FACTORY_WAREHOUSES: dict[str, list[str]] = {
    "F-01": ["W-042", "W-018", "W-074", "W-011"],
    "F-02": ["W-055", "W-042", "W-031"],
    "F-03": ["W-061", "W-042", "W-083"],
    "F-04": ["W-074", "W-018", "W-011"],
    "F-05": ["W-083", "W-055", "W-061"],
}

# Outbound lanes. Weights concentrate enough volume on Lyon → Madrid
# for the injected cost corridor to be statistically visible.
WAREHOUSE_HUBS: dict[str, list[tuple[str, float]]] = {
    "W-011": [("H-340", 0.46), ("H-341", 0.32), ("H-370", 0.22)],
    "W-018": [("H-311", 0.40), ("H-370", 0.28), ("H-310", 0.32)],
    "W-023": [("H-341", 0.48), ("H-340", 0.27), ("H-301", 0.25)],
    "W-031": [("H-303", 0.46), ("H-301", 0.34), ("H-341", 0.20)],
    "W-042": [("H-310", 0.30), ("H-311", 0.24), ("H-312", 0.16), ("H-341", 0.16), ("H-302", 0.14)],
    "W-055": [("H-302", 0.28), ("H-301", 0.24), ("H-330", 0.32), ("H-320", 0.16)],
    "W-061": [("H-320", 0.46), ("H-321", 0.34), ("H-312", 0.20)],
    "W-074": [("H-360", 0.55), ("H-311", 0.25), ("H-312", 0.20)],
    "W-083": [("H-330", 0.46), ("H-331", 0.36), ("H-321", 0.18)],
    "W-090": [("H-350", 0.78), ("H-340", 0.22)],
}

COST_RATES: dict[str, tuple[float, float]] = {
    # mode: (fixed EUR, EUR per km)
    "road": (48.0, 1.12),
    "rail": (85.0, 0.68),
    "sea": (140.0, 0.34),
    "air": (260.0, 4.60),
    "parcel": (16.0, 1.48),
}

SPEED_KMH: dict[str, float] = {
    "road": 62.0,
    "rail": 48.0,
    "sea": 32.0,
    "air": 520.0,
    "parcel": 42.0,
}

HANDLING_H: dict[str, float] = {
    "road": 10.0,
    "rail": 16.0,
    "sea": 36.0,
    "air": 12.0,
    "parcel": 8.0,
}

CATEGORY_COST: dict[str, tuple[float, float]] = {
    "Industrial Components": (70.0, 480.0),
    "Electronics": (45.0, 720.0),
    "Automotive Parts": (30.0, 280.0),
    "Packaging": (3.0, 24.0),
    "Consumer Goods": (8.0, 95.0),
}

# Injected scenario parameters. Detection does not read this table;
# the generator uses it so the same assumptions are documented in one place.
INJECTED = {
    "supplier_id": "S-018",
    "supplier_anomaly_start": "2026-07-03",
    "supplier_late_probability": 0.27,
    "warehouse_id": "W-042",
    "warehouse_anomaly_start": "2026-07-03",
    "warehouse_expected_days": 2.8,
    "warehouse_observed_days": 5.1,
    "sku": "SKU-2841",
    "sku_target_coverage_days": 1.9,
    "corridor_origin": "W-055",
    "corridor_dest": "H-330",
    "corridor_start": "2026-08-01",
    "corridor_multiplier": 2.55,
    "region": "France",
    "region_start": "2026-08-01",
    "region_late_probability": 0.12,
}
