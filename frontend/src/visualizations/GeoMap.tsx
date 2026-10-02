import { useEffect, useRef } from "react";
import maplibregl, { type Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { NetworkEdge, NetworkNode } from "../types";
import { tone } from "../lib/format";

const empty = { type: "FeatureCollection" as const, features: [] };

export function GeoMap({
  nodes,
  edges,
  sizeKey,
  emphasisIds = [],
  onSelect,
  onHover,
}: {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  sizeKey: "shipments" | "orders" | "inventory_units" | "inventory_value";
  emphasisIds?: string[];
  onSelect: (id: string) => void;
  onHover: (id: string | null, x: number, y: number) => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const selectRef = useRef(onSelect);
  const hoverRef = useRef(onHover);
  selectRef.current = onSelect;
  hoverRef.current = onHover;

  useEffect(() => {
    if (!ref.current) return;
    const map = new maplibregl.Map({
      container: ref.current,
      style: "https://tiles.openfreemap.org/styles/positron",
      center: [7.4, 49.2],
      zoom: 4.05,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    map.on("load", () => {
      map.addSource("edges", { type: "geojson", data: empty });
      map.addSource("nodes", { type: "geojson", data: empty });
      map.addLayer({
        id: "edges",
        type: "line",
        source: "edges",
        paint: {
          "line-color": ["get", "color"],
          "line-width": ["interpolate", ["linear"], ["get", "shipments"], 0, 0.7, 2000, 3.2],
          "line-opacity": ["get", "opacity"],
        },
      });
      map.addLayer({
        id: "nodes",
        type: "circle",
        source: "nodes",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "size"], 0, 4, 1, 14],
          "circle-color": ["get", "color"],
          "circle-stroke-color": ["case", ["==", ["get", "hot"], 1], "#2c6cb5", "#ffffff"],
          "circle-stroke-width": ["case", ["==", ["get", "hot"], 1], 2, 1.2],
          "circle-opacity": ["get", "opacity"],
        },
      });
      map.on("click", "nodes", (event) => {
        const id = event.features?.[0]?.properties?.id;
        if (id) selectRef.current(String(id));
      });
      map.on("mousemove", "nodes", (event) => {
        map.getCanvas().style.cursor = "pointer";
        const id = event.features?.[0]?.properties?.id;
        if (id) hoverRef.current(String(id), event.point.x, event.point.y);
      });
      map.on("mouseleave", "nodes", () => {
        map.getCanvas().style.cursor = "";
        hoverRef.current(null, 0, 0);
      });
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const maxSize = Math.max(...nodes.map((node) => Number(node[sizeKey] ?? 0)), 1);
    const nodeIndex = new Map(nodes.map((node) => [node.id, node]));
    const emphasis = new Set(emphasisIds);
    const linked = new Set(emphasis);
    if (emphasis.size) {
      edges.forEach((edge) => {
        if (emphasis.has(edge.source) || emphasis.has(edge.target)) {
          linked.add(edge.source);
          linked.add(edge.target);
        }
      });
    }
    const push = () => {
      const edgeSource = map.getSource("edges") as maplibregl.GeoJSONSource | undefined;
      const nodeSource = map.getSource("nodes") as maplibregl.GeoJSONSource | undefined;
      if (!edgeSource || !nodeSource) return;
      edgeSource.setData({
        type: "FeatureCollection",
        features: edges.flatMap((edge) => {
          const source = nodeIndex.get(edge.source);
          const target = nodeIndex.get(edge.target);
          if (!source || !target) return [];
          const hot = !emphasis.size || emphasis.has(edge.source) || emphasis.has(edge.target);
          return [{
            type: "Feature" as const,
            properties: { color: tone(edge.otd), shipments: edge.shipments, opacity: hot ? 0.8 : 0.08 },
            geometry: { type: "LineString" as const, coordinates: [[source.lon, source.lat], [target.lon, target.lat]] },
          }];
        }),
      });
      nodeSource.setData({
        type: "FeatureCollection",
        features: nodes.map((node) => ({
          type: "Feature" as const,
          properties: {
            id: node.id,
            size: Math.max(0.05, Number(node[sizeKey] ?? 0) / maxSize) * (emphasis.has(node.id) ? 1.35 : 1),
            color: tone(node.otd),
            hot: emphasis.has(node.id) ? 1 : 0,
            opacity: !emphasis.size || linked.has(node.id) ? 1 : 0.2,
          },
          geometry: { type: "Point" as const, coordinates: [node.lon, node.lat] },
        })),
      });
    };
    if (map.isStyleLoaded() && map.getSource("nodes")) push();
    else map.once("load", push);
  }, [nodes, edges, sizeKey, emphasisIds]);

  const framed = useRef(false);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || framed.current || nodes.length === 0) return;
    const frame = () => {
      if (framed.current || !map.getStyle()) return;
      const bounds = new maplibregl.LngLatBounds();
      nodes.forEach((node) => bounds.extend([node.lon, node.lat]));
      map.fitBounds(bounds, { padding: { top: 64, bottom: 48, left: 40, right: 40 }, duration: 0, maxZoom: 4.7 });
      framed.current = true;
    };
    if (map.isStyleLoaded()) frame();
    else map.once("load", frame);
  }, [nodes]);

  const emphasisKey = emphasisIds.join("|");
  useEffect(() => {
    const map = mapRef.current;
    if (!map || emphasisIds.length !== 1) return;
    const node = nodes.find((item) => item.id === emphasisIds[0]);
    if (!node) return;
    map.flyTo({ center: [node.lon, node.lat], zoom: Math.max(map.getZoom(), 4.3), duration: 650, essential: true });
  }, [emphasisKey, nodes, emphasisIds]);

  return <div ref={ref} className="map-root" />;
}
