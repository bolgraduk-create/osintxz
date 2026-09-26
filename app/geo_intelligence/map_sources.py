from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from app.core.config import DATA_DIR


SUPPORTED_MAP_SOURCE_KINDS = frozenset({
    "xyz",
    "wms",
    "wmts",
    "schematic",
    "satellite_dynamic",
})


def _normalize_source_id(value: str) -> str:
    normalized = re.sub(
        r"[^a-z0-9_]+",
        "_",
        str(value or "").strip().casefold(),
    )
    return normalized.strip("_")[:80]


def _validate_remote_map_url(value: str) -> None:
    url = str(value or "").strip()
    if not url:
        raise ValueError("Map source URL is required.")

    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise ValueError("Map source URL is invalid.") from exc

    if parsed.scheme not in {"https", "http"}:
        raise ValueError("Map source URL must use http or https.")
    if not parsed.hostname:
        raise ValueError("Map source URL must include a host.")
    if parsed.username or parsed.password:
        raise ValueError(
            "Credentials must not be embedded in a map source URL."
        )


@dataclass(frozen=True, slots=True)
class MapSourceDescriptor:
    id: str
    name: str
    kind: str
    category: str = "base"
    region: str = "World"
    provider: str = ""
    tags: tuple[str, ...] = ()
    url: str = ""
    attribution: str = ""
    terms_url: str = ""
    min_zoom: int = 0
    max_zoom: int = 19
    opacity: float = 1.0
    user_defined: bool = False
    enabled: bool = True
    compare_supported: bool = True
    overlay_supported: bool = True
    primary_supported: bool = True
    requires_api_key: bool = False
    requires_opt_in: bool = False
    wms_layers: str = ""
    wms_styles: str = ""
    wms_format: str = "image/png"
    wms_version: str = "1.3.0"
    wms_transparent: bool = True
    wmts_layer: str = ""
    wmts_style: str = "default"
    wmts_format: str = "image/png"
    wmts_matrix_set: str = ""
    wmts_matrix_prefix: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        source_id = _normalize_source_id(self.id)
        if not source_id:
            raise ValueError("Map source id is required.")

        name = str(self.name or "").strip()
        if not name:
            raise ValueError("Map source name is required.")

        kind = str(self.kind or "").strip().lower()
        if kind not in SUPPORTED_MAP_SOURCE_KINDS:
            raise ValueError(f"Unsupported map source kind: {kind}")

        min_zoom = int(self.min_zoom)
        max_zoom = int(self.max_zoom)
        if not 0 <= min_zoom <= 22:
            raise ValueError("min_zoom must be 0..22.")
        if not min_zoom <= max_zoom <= 22:
            raise ValueError("max_zoom must be between min_zoom and 22.")

        opacity = float(self.opacity)
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be 0..1.")

        url = str(self.url or "").strip()
        if kind in {"xyz", "wms", "wmts"}:
            _validate_remote_map_url(url)
        if kind == "xyz":
            for token in ("{z}", "{x}", "{y}"):
                if token not in url:
                    raise ValueError(
                        "XYZ URL must contain {z}, {x}, and {y} placeholders."
                    )
        if kind == "wms" and not str(self.wms_layers or "").strip():
            raise ValueError("WMS source requires at least one layer name.")
        if kind == "wmts":
            if not str(self.wmts_layer or "").strip():
                raise ValueError("WMTS source requires a layer name.")
            if not str(self.wmts_matrix_set or "").strip():
                raise ValueError("WMTS source requires a tile matrix set.")

        terms_url = str(self.terms_url or "").strip()
        if terms_url:
            _validate_remote_map_url(terms_url)

        object.__setattr__(self, "id", source_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "category", str(self.category or "base").strip().lower())
        object.__setattr__(self, "region", str(self.region or "World").strip() or "World")
        object.__setattr__(self, "provider", str(self.provider or "").strip())
        object.__setattr__(
            self,
            "tags",
            tuple(
                dict.fromkeys(
                    str(tag or "").strip().lower()
                    for tag in self.tags
                    if str(tag or "").strip()
                )
            ),
        )
        object.__setattr__(self, "url", url)
        object.__setattr__(self, "terms_url", terms_url)
        object.__setattr__(self, "min_zoom", min_zoom)
        object.__setattr__(self, "max_zoom", max_zoom)
        object.__setattr__(self, "opacity", opacity)
        object.__setattr__(self, "wms_layers", str(self.wms_layers or "").strip())
        object.__setattr__(self, "wms_styles", str(self.wms_styles or "").strip())
        object.__setattr__(self, "wms_format", str(self.wms_format or "image/png").strip())
        object.__setattr__(self, "wms_version", str(self.wms_version or "1.3.0").strip())
        object.__setattr__(self, "wmts_layer", str(self.wmts_layer or "").strip())
        object.__setattr__(self, "wmts_style", str(self.wmts_style or "default").strip())
        object.__setattr__(self, "wmts_format", str(self.wmts_format or "image/png").strip())
        object.__setattr__(self, "wmts_matrix_set", str(self.wmts_matrix_set or "").strip())
        object.__setattr__(self, "wmts_matrix_prefix", str(self.wmts_matrix_prefix or "").strip())

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "category": self.category,
            "region": self.region,
            "provider": self.provider,
            "tags": list(self.tags),
            "url": self.url,
            "attribution": self.attribution,
            "termsUrl": self.terms_url,
            "minZoom": self.min_zoom,
            "maxZoom": self.max_zoom,
            "opacity": self.opacity,
            "userDefined": self.user_defined,
            "enabled": self.enabled,
            "compareSupported": self.compare_supported,
            "overlaySupported": self.overlay_supported,
            "primarySupported": self.primary_supported,
            "requiresApiKey": self.requires_api_key,
            "requiresOptIn": self.requires_opt_in,
            "wmsLayers": self.wms_layers,
            "wmsStyles": self.wms_styles,
            "wmsFormat": self.wms_format,
            "wmsVersion": self.wms_version,
            "wmsTransparent": self.wms_transparent,
            "wmtsLayer": self.wmts_layer,
            "wmtsStyle": self.wmts_style,
            "wmtsFormat": self.wmts_format,
            "wmtsMatrixSet": self.wmts_matrix_set,
            "wmtsMatrixPrefix": self.wmts_matrix_prefix,
            "metadata": dict(self.metadata),
        }


BUILTIN_MAP_SOURCES: tuple[MapSourceDescriptor, ...] = (
    MapSourceDescriptor(
        id="osm_standard",
        name="OpenStreetMap",
        kind="xyz",
        category="streets",
        region="World",
        provider="OpenStreetMap Foundation",
        tags=("street", "roads", "osm", "world"),
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution="© OpenStreetMap contributors",
        terms_url="https://www.openstreetmap.org/copyright",
        min_zoom=0,
        max_zoom=19,
        metadata={
            "provider": "OpenStreetMap Foundation",
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "darkFilter": True,
        },
    ),
    MapSourceDescriptor(
        id="opentopomap",
        name="OpenTopoMap",
        kind="xyz",
        category="terrain",
        region="World",
        provider="OpenTopoMap",
        tags=("topographic", "terrain", "contours", "hiking", "osm"),
        url="https://a.tile.opentopomap.org/{z}/{x}/{y}.png",
        attribution="Map data: © OpenStreetMap contributors, SRTM | Map style: © OpenTopoMap (CC-BY-SA)",
        terms_url="https://wiki.opentopomap.org/about",
        min_zoom=0,
        max_zoom=17,
        metadata={
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "darkFilter": False,
            "catalogPack": "world",
        },
    ),
    MapSourceDescriptor(
        id="openseamap_seamarks",
        name="OpenSeaMap · Seamarks",
        kind="xyz",
        category="marine",
        region="World",
        provider="OpenSeaMap",
        tags=("marine", "nautical", "seamarks", "ports", "navigation"),
        url="https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png",
        attribution="© OpenSeaMap contributors · © OpenStreetMap contributors",
        terms_url="https://www.openseamap.org/",
        min_zoom=0,
        max_zoom=18,
        primary_supported=False,
        metadata={
            "overlayOnly": True,
            "transparentTiles": True,
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "catalogPack": "world",
        },
    ),
    MapSourceDescriptor(
        id="openrailwaymap_standard",
        name="OpenRailwayMap · Standard",
        kind="xyz",
        category="transport",
        region="World",
        provider="OpenRailwayMap",
        tags=("railway", "rail", "transport", "infrastructure", "osm"),
        url="https://tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png",
        attribution="© OpenStreetMap contributors · OpenRailwayMap style CC-BY-SA 2.0",
        terms_url="https://wiki.openstreetmap.org/wiki/OpenRailwayMap/API",
        min_zoom=2,
        max_zoom=19,
        primary_supported=False,
        metadata={
            "overlayOnly": True,
            "transparentTiles": True,
            "tilePixelRatio": 2,
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "catalogPack": "world",
        },
    ),
    MapSourceDescriptor(
        id="nasa_blue_marble",
        name="NASA GIBS · Blue Marble",
        kind="xyz",
        category="satellite",
        region="World",
        provider="NASA GIBS",
        tags=("satellite", "imagery", "blue marble", "earth", "global"),
        url="https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
        attribution="NASA Global Imagery Browse Services (GIBS)",
        terms_url="https://earthdata.nasa.gov/eosdis/science-system-description/eosdis-components/gibs",
        min_zoom=0,
        max_zoom=8,
        metadata={
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "darkFilter": False,
            "catalogPack": "nasa",
        },
    ),
    MapSourceDescriptor(
        id="nasa_blue_marble_relief",
        name="NASA GIBS · Blue Marble Relief",
        kind="xyz",
        category="terrain",
        region="World",
        provider="NASA GIBS",
        tags=("terrain", "relief", "bathymetry", "blue marble", "earth"),
        url="https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
        attribution="NASA Global Imagery Browse Services (GIBS)",
        terms_url="https://earthdata.nasa.gov/eosdis/science-system-description/eosdis-components/gibs",
        min_zoom=0,
        max_zoom=8,
        metadata={
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "darkFilter": False,
            "catalogPack": "nasa",
        },
    ),
    MapSourceDescriptor(
        id="usgs_topo",
        name="USGS · Topographic",
        kind="xyz",
        category="terrain",
        region="United States",
        provider="U.S. Geological Survey",
        tags=("usa", "usgs", "topographic", "terrain", "contours"),
        url="https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}",
        attribution="U.S. Geological Survey · The National Map",
        terms_url="https://www.usgs.gov/programs/national-geospatial-program/national-map",
        min_zoom=0,
        max_zoom=16,
        metadata={
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "darkFilter": False,
            "catalogPack": "usa",
        },
    ),
    MapSourceDescriptor(
        id="usgs_imagery",
        name="USGS · Imagery",
        kind="xyz",
        category="satellite",
        region="United States",
        provider="U.S. Geological Survey",
        tags=("usa", "usgs", "imagery", "aerial", "orthophoto"),
        url="https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}",
        attribution="U.S. Geological Survey · The National Map",
        terms_url="https://www.usgs.gov/programs/national-geospatial-program/national-map",
        min_zoom=0,
        max_zoom=20,
        metadata={
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "darkFilter": False,
            "catalogPack": "usa",
        },
    ),
    MapSourceDescriptor(
        id="usgs_shaded_relief",
        name="USGS · Shaded Relief",
        kind="xyz",
        category="terrain",
        region="United States",
        provider="U.S. Geological Survey",
        tags=("usa", "usgs", "hillshade", "relief", "elevation"),
        url="https://basemap.nationalmap.gov/arcgis/rest/services/USGSShadedReliefOnly/MapServer/tile/{z}/{y}/{x}",
        attribution="U.S. Geological Survey · 3D Elevation Program",
        terms_url="https://www.usgs.gov/3d-elevation-program",
        min_zoom=1,
        max_zoom=7,
        metadata={
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "darkFilter": False,
            "catalogPack": "usa",
        },
    ),
    MapSourceDescriptor(
        id="usgs_hydro",
        name="USGS · Hydrography",
        kind="xyz",
        category="hydrography",
        region="United States",
        provider="U.S. Geological Survey",
        tags=("usa", "usgs", "hydrography", "water", "rivers", "lakes"),
        url="https://basemap.nationalmap.gov/arcgis/rest/services/USGSHydroCached/MapServer/tile/{z}/{y}/{x}",
        attribution="U.S. Geological Survey · The National Map",
        terms_url="https://www.usgs.gov/programs/national-geospatial-program/national-map",
        min_zoom=0,
        max_zoom=16,
        primary_supported=False,
        metadata={
            "overlayOnly": True,
            "transparentTiles": True,
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "catalogPack": "usa",
        },
    ),
    MapSourceDescriptor(
        id="pl_geoportal_ortho",
        name="Poland Geoportal · Orthophotomap",
        kind="xyz",
        category="satellite",
        region="Poland",
        provider="Główny Urząd Geodezji i Kartografii",
        tags=("poland", "ortho", "orthophoto", "aerial", "geoportal", "gugik"),
        url="https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMTS/StandardResolution?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTOFOTOMAPA&STYLE=default&FORMAT=image/jpeg&TILEMATRIXSET=EPSG:3857&TILEMATRIX=EPSG:3857:{z}&TILEROW={y}&TILECOL={x}",
        attribution="Główny Urząd Geodezji i Kartografii · Geoportal.gov.pl",
        terms_url="https://www.geoportal.gov.pl/en/data/orthophotomap-orto/",
        min_zoom=5,
        max_zoom=22,
        metadata={
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "darkFilter": False,
            "catalogPack": "poland",
            "coverage": "Poland",
        },
    ),
    MapSourceDescriptor(
        id="de_basemap_raster_color",
        name="Germany · basemap.de Raster",
        kind="xyz",
        category="streets",
        region="Germany",
        provider="BKG / GeoBasis-DE",
        tags=("germany", "basemap", "official", "streets", "topographic"),
        url="https://sgx.geodatenzentrum.de/wmts_basemapde/tile/1.0.0/de_basemapde_web_raster_farbe/default/GLOBAL_WEBMERCATOR/{z}/{y}/{x}.png",
        attribution="© basemap.de / BKG · © GeoBasis-DE",
        terms_url="https://basemap.de/produkte-und-dienste/web-raster/",
        min_zoom=0,
        max_zoom=18,
        metadata={
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "darkFilter": False,
            "catalogPack": "germany",
            "coverage": "Germany",
        },
    ),
    MapSourceDescriptor(
        id="fr_ign_plan_v2",
        name="France · Plan IGN v2",
        kind="xyz",
        category="streets",
        region="France",
        provider="IGN France / Géoplateforme",
        tags=("france", "ign", "plan", "official", "topographic", "streets"),
        url="https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&FORMAT=image/png&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}",
        attribution="© IGN France",
        terms_url="https://geoservices.ign.fr/cgu-licences",
        min_zoom=0,
        max_zoom=19,
        metadata={
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "darkFilter": False,
            "catalogPack": "france",
            "coverage": "France",
        },
    ),
    MapSourceDescriptor(
        id="fr_ign_ortho",
        name="France · IGN Orthophotos",
        kind="xyz",
        category="satellite",
        region="France",
        provider="IGN France / Géoplateforme",
        tags=("france", "ign", "ortho", "orthophoto", "aerial", "imagery"),
        url="https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&FORMAT=image/jpeg&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}",
        attribution="© IGN France",
        terms_url="https://geoservices.ign.fr/cgu-licences",
        min_zoom=0,
        max_zoom=19,
        metadata={
            "cachePolicy": "http_headers",
            "prefetchAllowed": False,
            "darkFilter": False,
            "catalogPack": "france",
            "coverage": "France",
        },
    ),
    MapSourceDescriptor(
        id="local_schematic",
        name="Local Schematic",
        kind="schematic",
        category="offline",
        region="Local",
        provider="OSINTXZ",
        tags=("offline", "fallback", "schematic"),
        attribution="OSINTXZ local schematic",
        min_zoom=0,
        max_zoom=4,
        compare_supported=False,
        overlay_supported=False,
        metadata={
            "offline": True,
            "fallback": True,
        },
    ),
    MapSourceDescriptor(
        id="sentinel_selected",
        name="Sentinel-2 Selected Scene",
        kind="satellite_dynamic",
        category="satellite",
        region="World",
        provider="Copernicus Data Space Ecosystem",
        tags=("satellite", "sentinel", "imagery", "earth observation"),
        attribution="Copernicus Data Space Ecosystem",
        terms_url="https://dataspace.copernicus.eu/",
        min_zoom=0,
        max_zoom=18,
        metadata={
            "dynamic": True,
            "requiresScene": True,
        },
    ),
)


class MapSourceRegistry:
    """Small persistent registry for built-in and analyst-added map sources."""

    def __init__(
        self,
        *,
        storage_path: Path | None = None,
    ) -> None:
        self.storage_path = Path(
            storage_path
            or (DATA_DIR / "map_sources.json")
        )
        self._builtins = {
            source.id: source
            for source in BUILTIN_MAP_SOURCES
        }
        self._custom: dict[str, MapSourceDescriptor] = {}
        self._load_custom_sources()

    def all(self) -> tuple[MapSourceDescriptor, ...]:
        rows = [
            *self._builtins.values(),
            *self._custom.values(),
        ]
        rows.sort(
            key=lambda item: (
                item.category,
                item.name.casefold(),
                item.id,
            )
        )
        return tuple(rows)

    def payload(self) -> list[dict[str, Any]]:
        return [
            source.to_payload()
            for source in self.all()
            if source.enabled
        ]

    def get(self, source_id: str) -> MapSourceDescriptor | None:
        key = _normalize_source_id(source_id)
        return self._custom.get(key) or self._builtins.get(key)

    def add_custom(
        self,
        *,
        name: str,
        kind: str,
        url: str,
        attribution: str = "",
        terms_url: str = "",
        min_zoom: int = 0,
        max_zoom: int = 19,
        wms_layers: str = "",
        wms_styles: str = "",
        wms_format: str = "image/png",
        wms_version: str = "1.3.0",
        wms_transparent: bool = True,
        wmts_layer: str = "",
        wmts_style: str = "default",
        wmts_format: str = "image/png",
        wmts_matrix_set: str = "",
        wmts_matrix_prefix: str = "",
    ) -> MapSourceDescriptor:
        normalized_name = str(name or "").strip()
        source_id = self._next_custom_id(normalized_name)
        source = MapSourceDescriptor(
            id=source_id,
            name=normalized_name,
            kind=kind,
            category="custom",
            url=url,
            attribution=str(attribution or "").strip(),
            terms_url=terms_url,
            min_zoom=min_zoom,
            max_zoom=max_zoom,
            user_defined=True,
            wms_layers=wms_layers,
            wms_styles=wms_styles,
            wms_format=wms_format,
            wms_version=wms_version,
            wms_transparent=bool(wms_transparent),
            wmts_layer=wmts_layer,
            wmts_style=wmts_style,
            wmts_format=wmts_format,
            wmts_matrix_set=wmts_matrix_set,
            wmts_matrix_prefix=wmts_matrix_prefix,
            metadata={
                "persistedLocally": True,
            },
        )
        self._custom[source.id] = source
        self._save_custom_sources()
        return source

    def remove_custom(self, source_id: str) -> bool:
        key = _normalize_source_id(source_id)
        if key not in self._custom:
            return False
        self._custom.pop(key, None)
        self._save_custom_sources()
        return True

    def _next_custom_id(self, name: str) -> str:
        base = _normalize_source_id(name)
        if not base:
            base = "custom_map"
        if not base.startswith("custom_"):
            base = "custom_" + base

        existing = set(self._builtins) | set(self._custom)
        if base not in existing:
            return base

        suffix = 2
        while f"{base}_{suffix}" in existing:
            suffix += 1
        return f"{base}_{suffix}"

    def _load_custom_sources(self) -> None:
        try:
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return

        rows = raw.get("sources") if isinstance(raw, dict) else None
        if not isinstance(rows, list):
            return

        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                source = MapSourceDescriptor(
                    id=str(row.get("id") or ""),
                    name=str(row.get("name") or ""),
                    kind=str(row.get("kind") or ""),
                    category="custom",
                    region=str(row.get("region") or "Custom"),
                    provider=str(row.get("provider") or "Analyst"),
                    tags=tuple(row.get("tags") or ()),
                    url=str(row.get("url") or ""),
                    attribution=str(row.get("attribution") or ""),
                    terms_url=str(row.get("termsUrl") or ""),
                    min_zoom=int(row.get("minZoom", 0)),
                    max_zoom=int(row.get("maxZoom", 19)),
                    opacity=float(row.get("opacity", 1.0)),
                    user_defined=True,
                    enabled=bool(row.get("enabled", True)),
                    compare_supported=bool(row.get("compareSupported", True)),
                    overlay_supported=bool(row.get("overlaySupported", True)),
                    primary_supported=bool(row.get("primarySupported", True)),
                    requires_api_key=bool(row.get("requiresApiKey", False)),
                    requires_opt_in=bool(row.get("requiresOptIn", False)),
                    wms_layers=str(row.get("wmsLayers") or ""),
                    wms_styles=str(row.get("wmsStyles") or ""),
                    wms_format=str(row.get("wmsFormat") or "image/png"),
                    wms_version=str(row.get("wmsVersion") or "1.3.0"),
                    wms_transparent=bool(row.get("wmsTransparent", True)),
                    wmts_layer=str(row.get("wmtsLayer") or ""),
                    wmts_style=str(row.get("wmtsStyle") or "default"),
                    wmts_format=str(row.get("wmtsFormat") or "image/png"),
                    wmts_matrix_set=str(row.get("wmtsMatrixSet") or ""),
                    wmts_matrix_prefix=str(row.get("wmtsMatrixPrefix") or ""),
                    metadata={
                        "persistedLocally": True,
                    },
                )
            except (TypeError, ValueError):
                continue
            if source.id in self._builtins:
                continue
            self._custom[source.id] = source

    def _save_custom_sources(self) -> None:
        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        payload = {
            "version": 1,
            "sources": [
                source.to_payload()
                for source in sorted(
                    self._custom.values(),
                    key=lambda item: item.id,
                )
            ],
        }
        temporary = self.storage_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.storage_path)


