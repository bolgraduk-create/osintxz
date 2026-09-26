from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Iterable
from xml.etree import ElementTree as ET

from app.core.config import DATA_DIR


MAX_VECTOR_FILE_BYTES = 5_000_000
MAX_VECTOR_FEATURES = 5_000
MAX_VECTOR_COORDINATES = 100_000
SUPPORTED_VECTOR_EXTENSIONS = frozenset({
    ".geojson",
    ".json",
    ".kml",
    ".gpx",
})


@dataclass(slots=True)
class MapVectorLayer:
    id: str
    name: str
    source_format: str
    source_name: str
    features: list[dict[str, Any]]
    scope_id: str = "global"
    visible: bool = True
    opacity: float = 0.9
    bounds: list[float] = field(default_factory=list)
    imported: bool = True

    def __post_init__(self) -> None:
        self.id = _normalize_id(self.id)
        if not self.id:
            raise ValueError("Map layer id is required.")

        self.name = str(self.name or "").strip()
        if not self.name:
            raise ValueError("Map layer name is required.")

        self.source_format = str(self.source_format or "").strip().lower()
        if self.source_format not in {"geojson", "kml", "gpx"}:
            raise ValueError("Unsupported vector layer format.")

        self.source_name = Path(str(self.source_name or "")).name
        self.scope_id = str(self.scope_id or "global").strip() or "global"
        self.opacity = max(0.05, min(1.0, float(self.opacity)))
        self.visible = bool(self.visible)
        self.imported = bool(self.imported)

    def to_payload(self, *, include_features: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "kind": "vector",
            "sourceFormat": self.source_format,
            "sourceName": self.source_name,
            "scopeId": self.scope_id,
            "visible": self.visible,
            "opacity": self.opacity,
            "bounds": list(self.bounds),
            "featureCount": len(self.features),
            "imported": self.imported,
        }
        if include_features:
            payload["features"] = [
                dict(feature)
                for feature in self.features
            ]
        return payload


class MapLayerRegistry:
    """Persistent, bounded analyst-imported map vector layers."""

    def __init__(
        self,
        *,
        storage_dir: Path | None = None,
    ) -> None:
        self.storage_dir = Path(
            storage_dir
            or (DATA_DIR / "map_layers")
        )
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._layers: dict[str, MapVectorLayer] = {}
        self._load()

    def all(self, *, include_features: bool = True) -> list[dict[str, Any]]:
        rows = sorted(
            self._layers.values(),
            key=lambda item: item.name.casefold(),
        )
        return [
            layer.to_payload(include_features=include_features)
            for layer in rows
        ]

    def get(self, layer_id: str) -> MapVectorLayer | None:
        return self._layers.get(_normalize_id(layer_id))

    def import_file(
        self,
        file_path: str | Path,
        *,
        scope_id: str = "global",
    ) -> MapVectorLayer:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError("Selected map layer file does not exist.")

        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_VECTOR_EXTENSIONS:
            raise ValueError(
                "Supported map layer formats are GeoJSON, KML, and GPX."
            )

        size = path.stat().st_size
        if size <= 0:
            raise ValueError("Selected map layer file is empty.")
        if size > MAX_VECTOR_FILE_BYTES:
            raise ValueError(
                "Map layer file exceeds the 5 MB import limit."
            )

        raw = path.read_bytes()
        if suffix in {".geojson", ".json"}:
            source_format = "geojson"
            features = _parse_geojson(raw)
        elif suffix == ".kml":
            source_format = "kml"
            features = _parse_kml(raw)
        else:
            source_format = "gpx"
            features = _parse_gpx(raw)

        if not features:
            raise ValueError(
                "No supported Point, LineString, or Polygon geometry was found."
            )

        if len(features) > MAX_VECTOR_FEATURES:
            raise ValueError(
                f"Map layer contains more than {MAX_VECTOR_FEATURES} features."
            )

        coordinate_count = sum(
            _coordinate_count(feature.get("coordinates"))
            for feature in features
        )
        if coordinate_count > MAX_VECTOR_COORDINATES:
            raise ValueError(
                "Map layer contains too many coordinates for the interactive map."
            )

        layer_id = self._next_id(path.stem)
        bounds = _features_bounds(features)
        layer = MapVectorLayer(
            id=layer_id,
            name=path.stem,
            source_format=source_format,
            source_name=path.name,
            features=features,
            scope_id=str(scope_id or "global").strip() or "global",
            bounds=bounds,
        )
        self._layers[layer.id] = layer
        self._persist(layer)
        return layer

    def set_visibility(self, layer_id: str, visible: bool) -> bool:
        layer = self.get(layer_id)
        if layer is None:
            return False
        layer.visible = bool(visible)
        self._persist(layer)
        return True

    def set_opacity(self, layer_id: str, opacity: float) -> bool:
        layer = self.get(layer_id)
        if layer is None:
            return False
        layer.opacity = max(0.05, min(1.0, float(opacity)))
        self._persist(layer)
        return True

    def remove(self, layer_id: str) -> bool:
        key = _normalize_id(layer_id)
        layer = self._layers.pop(key, None)
        if layer is None:
            return False

        path = self._layer_path(key)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            self._layers[key] = layer
            raise
        return True

    def _next_id(self, name: str) -> str:
        base = _normalize_id(name) or "vector_layer"
        if not base.startswith("layer_"):
            base = "layer_" + base

        if base not in self._layers:
            return base

        suffix = 2
        while f"{base}_{suffix}" in self._layers:
            suffix += 1
        return f"{base}_{suffix}"

    def _layer_path(self, layer_id: str) -> Path:
        return self.storage_dir / f"{_normalize_id(layer_id)}.json"

    def _persist(self, layer: MapVectorLayer) -> None:
        path = self._layer_path(layer.id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "version": 1,
                    "layer": layer.to_payload(include_features=True),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _load(self) -> None:
        for path in sorted(self.storage_dir.glob("layer_*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                row = raw.get("layer") if isinstance(raw, dict) else None
                if not isinstance(row, dict):
                    continue
                features = row.get("features")
                if not isinstance(features, list):
                    continue
                if len(features) > MAX_VECTOR_FEATURES:
                    continue
                coordinate_count = sum(
                    _coordinate_count(feature.get("coordinates"))
                    for feature in features
                    if isinstance(feature, dict)
                )
                if coordinate_count > MAX_VECTOR_COORDINATES:
                    continue
                layer = MapVectorLayer(
                    id=str(row.get("id") or ""),
                    name=str(row.get("name") or ""),
                    source_format=str(row.get("sourceFormat") or ""),
                    source_name=str(row.get("sourceName") or ""),
                    scope_id=str(row.get("scopeId") or "global"),
                    features=[
                        dict(feature)
                        for feature in features
                        if isinstance(feature, dict)
                    ],
                    visible=bool(row.get("visible", True)),
                    opacity=float(row.get("opacity", 0.9)),
                    bounds=[
                        float(value)
                        for value in (row.get("bounds") or [])
                        if isinstance(value, (int, float))
                    ][:4],
                )
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            self._layers[layer.id] = layer


def _parse_geojson(raw: bytes) -> list[dict[str, Any]]:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid GeoJSON file.") from exc

    features: list[dict[str, Any]] = []

    def append_geometry(
        geometry: Any,
        *,
        title: str = "",
        properties: dict[str, Any] | None = None,
    ) -> None:
        if not isinstance(geometry, dict):
            return

        geometry_type = str(geometry.get("type") or "")
        coordinates = geometry.get("coordinates")

        if geometry_type in {"Point", "LineString", "Polygon"}:
            normalized = _normalize_geometry(
                geometry_type,
                coordinates,
            )
            if normalized is not None:
                features.append(
                    _feature(
                        len(features),
                        geometry_type,
                        normalized,
                        title=title,
                        properties=properties,
                    )
                )
            return

        if geometry_type == "MultiPoint" and isinstance(coordinates, list):
            for item in coordinates:
                append_geometry(
                    {"type": "Point", "coordinates": item},
                    title=title,
                    properties=properties,
                )
            return

        if geometry_type == "MultiLineString" and isinstance(coordinates, list):
            for item in coordinates:
                append_geometry(
                    {"type": "LineString", "coordinates": item},
                    title=title,
                    properties=properties,
                )
            return

        if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
            for item in coordinates:
                append_geometry(
                    {"type": "Polygon", "coordinates": item},
                    title=title,
                    properties=properties,
                )
            return

        if geometry_type == "GeometryCollection":
            for item in geometry.get("geometries") or []:
                append_geometry(
                    item,
                    title=title,
                    properties=properties,
                )

    if not isinstance(payload, dict):
        raise ValueError("GeoJSON root must be an object.")

    root_type = str(payload.get("type") or "")
    if root_type == "FeatureCollection":
        rows = payload.get("features")
        if not isinstance(rows, list):
            raise ValueError("GeoJSON FeatureCollection has no features.")
        for row in rows:
            if not isinstance(row, dict):
                continue
            properties = _bounded_properties(row.get("properties"))
            title = _feature_title(properties)
            append_geometry(
                row.get("geometry"),
                title=title,
                properties=properties,
            )
    elif root_type == "Feature":
        properties = _bounded_properties(payload.get("properties"))
        append_geometry(
            payload.get("geometry"),
            title=_feature_title(properties),
            properties=properties,
        )
    else:
        append_geometry(payload)

    return features


def _parse_kml(raw: bytes) -> list[dict[str, Any]]:
    root = _parse_safe_xml(raw, "KML")
    features: list[dict[str, Any]] = []

    for placemark in _elements_named(root, "Placemark"):
        name = _first_child_text(placemark, "name")

        for point in _elements_named(placemark, "Point"):
            coordinates = _first_child_text(point, "coordinates")
            values = _parse_kml_coordinates(coordinates)
            if values:
                features.append(
                    _feature(
                        len(features),
                        "Point",
                        values[0],
                        title=name,
                    )
                )

        for line in _elements_named(placemark, "LineString"):
            coordinates = _first_child_text(line, "coordinates")
            values = _parse_kml_coordinates(coordinates)
            if len(values) >= 2:
                features.append(
                    _feature(
                        len(features),
                        "LineString",
                        values,
                        title=name,
                    )
                )

        for polygon in _elements_named(placemark, "Polygon"):
            rings: list[list[list[float]]] = []
            for ring in _elements_named(polygon, "LinearRing"):
                coordinates = _first_child_text(ring, "coordinates")
                values = _parse_kml_coordinates(coordinates)
                if len(values) >= 3:
                    rings.append(values)
            if rings:
                features.append(
                    _feature(
                        len(features),
                        "Polygon",
                        rings,
                        title=name,
                    )
                )

    return features


def _parse_gpx(raw: bytes) -> list[dict[str, Any]]:
    root = _parse_safe_xml(raw, "GPX")
    features: list[dict[str, Any]] = []

    for waypoint in _elements_named(root, "wpt"):
        point = _lat_lon(waypoint)
        if point is None:
            continue
        features.append(
            _feature(
                len(features),
                "Point",
                point,
                title=_first_child_text(waypoint, "name"),
            )
        )

    for route in _elements_named(root, "rte"):
        points = [
            point
            for point in (
                _lat_lon(element)
                for element in _direct_children_named(route, "rtept")
            )
            if point is not None
        ]
        if len(points) >= 2:
            features.append(
                _feature(
                    len(features),
                    "LineString",
                    points,
                    title=_first_child_text(route, "name") or "GPX route",
                )
            )

    for track in _elements_named(root, "trk"):
        track_name = _first_child_text(track, "name") or "GPX track"
        for segment in _direct_children_named(track, "trkseg"):
            points = [
                point
                for point in (
                    _lat_lon(element)
                    for element in _direct_children_named(segment, "trkpt")
                )
                if point is not None
            ]
            if len(points) >= 2:
                features.append(
                    _feature(
                        len(features),
                        "LineString",
                        points,
                        title=track_name,
                    )
                )

    return features


def _parse_safe_xml(raw: bytes, label: str) -> ET.Element:
    probe = raw[:].upper()
    if b"<!DOCTYPE" in probe or b"<!ENTITY" in probe:
        raise ValueError(
            f"{label} files containing DOCTYPE or ENTITY declarations are blocked."
        )
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid {label} XML file.") from exc


def _feature(
    index: int,
    geometry_type: str,
    coordinates: Any,
    *,
    title: str = "",
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": f"feature-{index + 1}",
        "geometryType": geometry_type,
        "coordinates": coordinates,
        "title": str(title or "").strip()[:240],
        "properties": dict(properties or {}),
    }


def _normalize_geometry(
    geometry_type: str,
    coordinates: Any,
) -> Any | None:
    if geometry_type == "Point":
        return _point(coordinates)

    if geometry_type == "LineString":
        if not isinstance(coordinates, list):
            return None
        points = [
            point
            for point in (_point(item) for item in coordinates)
            if point is not None
        ]
        return points if len(points) >= 2 else None

    if geometry_type == "Polygon":
        if not isinstance(coordinates, list):
            return None
        rings: list[list[list[float]]] = []
        for ring in coordinates:
            if not isinstance(ring, list):
                continue
            points = [
                point
                for point in (_point(item) for item in ring)
                if point is not None
            ]
            if len(points) >= 3:
                rings.append(points)
        return rings or None

    return None


def _point(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        longitude = float(value[0])
        latitude = float(value[1])
    except (TypeError, ValueError):
        return None
    if not -180.0 <= longitude <= 180.0:
        return None
    if not -90.0 <= latitude <= 90.0:
        return None
    return [longitude, latitude]


def _parse_kml_coordinates(value: str) -> list[list[float]]:
    rows: list[list[float]] = []
    for token in str(value or "").replace("\n", " ").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        point = _point(parts)
        if point is not None:
            rows.append(point)
    return rows


def _lat_lon(element: ET.Element) -> list[float] | None:
    try:
        latitude = float(element.attrib.get("lat", ""))
        longitude = float(element.attrib.get("lon", ""))
    except (TypeError, ValueError):
        return None
    return _point([longitude, latitude])


def _bounded_properties(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    result: dict[str, str] = {}
    for key, raw in list(value.items())[:24]:
        if isinstance(raw, (dict, list, tuple)):
            continue
        text = str(raw if raw is not None else "").strip()
        if not text:
            continue
        result[str(key)[:80]] = text[:400]
    return result


def _feature_title(properties: dict[str, str]) -> str:
    for key in ("name", "title", "label", "description"):
        value = str(properties.get(key) or "").strip()
        if value:
            return value
    return ""


def _local_name(tag: str) -> str:
    return str(tag or "").rsplit("}", 1)[-1]


def _elements_named(
    root: ET.Element,
    name: str,
) -> Iterable[ET.Element]:
    wanted = str(name)
    for element in root.iter():
        if _local_name(element.tag) == wanted:
            yield element


def _direct_children_named(
    root: ET.Element,
    name: str,
) -> Iterable[ET.Element]:
    wanted = str(name)
    for element in list(root):
        if _local_name(element.tag) == wanted:
            yield element


def _first_child_text(
    root: ET.Element,
    name: str,
) -> str:
    for element in _direct_children_named(root, name):
        return str(element.text or "").strip()
    for element in _elements_named(root, name):
        return str(element.text or "").strip()
    return ""


def _coordinate_count(value: Any) -> int:
    if (
        isinstance(value, list)
        and len(value) >= 2
        and all(isinstance(item, (int, float)) for item in value[:2])
    ):
        return 1
    if isinstance(value, list):
        return sum(_coordinate_count(item) for item in value)
    return 0


def _features_bounds(features: list[dict[str, Any]]) -> list[float]:
    points: list[list[float]] = []

    def collect(value: Any) -> None:
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            points.append([float(value[0]), float(value[1])])
            return
        if isinstance(value, list):
            for child in value:
                collect(child)

    for feature in features:
        collect(feature.get("coordinates"))

    if not points:
        return []

    longitudes = [point[0] for point in points]
    latitudes = [point[1] for point in points]
    return [
        min(longitudes),
        min(latitudes),
        max(longitudes),
        max(latitudes),
    ]


def _normalize_id(value: str) -> str:
    normalized = re.sub(
        r"[^a-z0-9_]+",
        "_",
        str(value or "").strip().casefold(),
    )
    return normalized.strip("_")[:96]
