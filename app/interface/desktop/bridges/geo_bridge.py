from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, QThread, QUrl, Signal, Slot

from app.core.config import settings
from app.geo_intelligence.contracts import GeoEnrichmentRequest, GeoPoint
from app.geo_intelligence.map_layers import MapLayerRegistry
from app.geo_intelligence.map_sources import MapSourceRegistry
from app.geo_intelligence.service import GeoIntelligenceService
from app.interface.desktop.workers.geo_enrichment_worker import (
    GeoEnrichmentWorker,
)
from app.interface.desktop.workers.satellite_scene_search_worker import (
    SatelliteSceneSearchWorker,
)
from app.interface.desktop.workers.satellite_scene_render_worker import (
    SatelliteSceneRenderWorker,
)


class GeoBridge(QObject):
    """Transient QML bridge for live, read-only GEO enrichment."""

    changed = Signal()
    messageChanged = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._run: dict[str, Any] = {}
        self._busy = False
        self._message = ""
        self._thread: QThread | None = None
        self._worker: GeoEnrichmentWorker | None = None
        self._satellite: dict[str, Any] = {}
        self._satellite_busy = False
        self._satellite_message = ""
        self._satellite_thread: QThread | None = None
        self._satellite_worker: SatelliteSceneSearchWorker | None = None
        self._satellite_render_busy = False
        self._satellite_render_thread: QThread | None = None
        self._satellite_render_worker: SatelliteSceneRenderWorker | None = None
        self._map_source_registry = MapSourceRegistry()
        self._map_source_message = ""
        self._map_layer_registry = MapLayerRegistry()
        self._map_layer_message = ""

    @Property("QVariantMap", notify=changed)
    def runData(self) -> dict[str, Any]:
        return dict(self._run)

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=messageChanged)
    def message(self) -> str:
        return self._message

    @Property("QVariantMap", notify=changed)
    def satelliteData(self) -> dict[str, Any]:
        return dict(self._satellite)

    @Property(bool, notify=changed)
    def satelliteBusy(self) -> bool:
        return self._satellite_busy

    @Property(str, notify=messageChanged)
    def satelliteMessage(self) -> str:
        return self._satellite_message

    @Property(bool, notify=changed)
    def satelliteRenderBusy(self) -> bool:
        return self._satellite_render_busy

    @Property(bool, notify=changed)
    def satelliteRenderingAvailable(self) -> bool:
        return bool(
            str(settings.cdse_client_id or "").strip()
            and settings.cdse_client_secret is not None
            and settings.cdse_client_secret.get_secret_value().strip()
        )

    @Property("QVariantList", notify=changed)
    def mapSources(self) -> list[dict[str, Any]]:
        return self._map_source_registry.payload()

    @Property(str, notify=messageChanged)
    def mapSourceMessage(self) -> str:
        return self._map_source_message

    @Property("QVariantList", notify=changed)
    def mapLayers(self) -> list[dict[str, Any]]:
        return self._map_layer_registry.all(include_features=True)

    @Property(str, notify=messageChanged)
    def mapLayerMessage(self) -> str:
        return self._map_layer_message

    @Slot(str, result=bool)
    def importMapLayer(
        self,
        file_url: str,
    ) -> bool:
        normalized = str(file_url or "").strip()
        if not normalized:
            self._set_map_layer_message("Select a GeoJSON, KML, or GPX file.")
            return False

        qurl = QUrl(normalized)
        local_path = (
            qurl.toLocalFile()
            if qurl.isLocalFile()
            else normalized
        )

        try:
            layer = self._map_layer_registry.import_file(local_path)
        except (OSError, TypeError, ValueError) as exc:
            self._set_map_layer_message(str(exc))
            return False

        self._set_map_layer_message(
            "Map layer imported: "
            + layer.name
            + f" ({len(layer.features)} feature(s))."
        )
        self.changed.emit()
        return True

    @Slot(str, bool, result=bool)
    def setMapLayerVisibility(
        self,
        layer_id: str,
        visible: bool,
    ) -> bool:
        try:
            changed = self._map_layer_registry.set_visibility(
                layer_id,
                visible,
            )
        except (OSError, TypeError, ValueError) as exc:
            self._set_map_layer_message(str(exc))
            return False

        if not changed:
            self._set_map_layer_message("Map layer is unavailable.")
            return False

        self._set_map_layer_message("")
        self.changed.emit()
        return True

    @Slot(str, float, result=bool)
    def setMapLayerOpacity(
        self,
        layer_id: str,
        opacity: float,
    ) -> bool:
        try:
            changed = self._map_layer_registry.set_opacity(
                layer_id,
                opacity,
            )
        except (OSError, TypeError, ValueError) as exc:
            self._set_map_layer_message(str(exc))
            return False

        if not changed:
            self._set_map_layer_message("Map layer is unavailable.")
            return False

        self._set_map_layer_message("")
        self.changed.emit()
        return True

    @Slot(str, result=bool)
    def removeMapLayer(
        self,
        layer_id: str,
    ) -> bool:
        try:
            removed = self._map_layer_registry.remove(layer_id)
        except OSError as exc:
            self._set_map_layer_message(str(exc))
            return False

        if not removed:
            self._set_map_layer_message("Map layer is unavailable.")
            return False

        self._set_map_layer_message("Map layer removed.")
        self.changed.emit()
        return True

    @Slot("QVariantMap", result=bool)
    def addMapSource(
        self,
        payload: object,
    ) -> bool:
        data = dict(payload) if isinstance(payload, dict) else {}
        try:
            source = self._map_source_registry.add_custom(
                name=str(data.get("name") or ""),
                kind=str(data.get("kind") or ""),
                url=str(data.get("url") or ""),
                attribution=str(data.get("attribution") or ""),
                terms_url=str(data.get("termsUrl") or ""),
                min_zoom=int(data.get("minZoom", 0)),
                max_zoom=int(data.get("maxZoom", 19)),
                wms_layers=str(data.get("wmsLayers") or ""),
                wms_styles=str(data.get("wmsStyles") or ""),
                wms_format=str(data.get("wmsFormat") or "image/png"),
                wms_version=str(data.get("wmsVersion") or "1.3.0"),
                wms_transparent=bool(data.get("wmsTransparent", True)),
                wmts_layer=str(data.get("wmtsLayer") or ""),
                wmts_style=str(data.get("wmtsStyle") or "default"),
                wmts_format=str(data.get("wmtsFormat") or "image/png"),
                wmts_matrix_set=str(data.get("wmtsMatrixSet") or ""),
                wmts_matrix_prefix=str(data.get("wmtsMatrixPrefix") or ""),
            )
        except (TypeError, ValueError, OSError) as exc:
            self._set_map_source_message(str(exc))
            return False

        self._set_map_source_message(
            "Map source added: " + source.name
        )
        self.changed.emit()
        return True

    @Slot(str, result=bool)
    def removeMapSource(
        self,
        source_id: str,
    ) -> bool:
        normalized = str(source_id or "").strip()
        try:
            removed = self._map_source_registry.remove_custom(normalized)
        except OSError as exc:
            self._set_map_source_message(str(exc))
            return False

        if not removed:
            self._set_map_source_message(
                "Only analyst-added map sources can be removed."
            )
            return False

        self._set_map_source_message("Map source removed.")
        self.changed.emit()
        return True

    @Slot(float, float, str, int, result=bool)
    def runEnrichment(
        self,
        latitude: float,
        longitude: float,
        historical_date: str,
        radius_m: int,
    ) -> bool:
        if self._busy:
            self._set_message("GEO enrichment is already running.")
            return False

        normalized_date = str(historical_date or "").strip()

        try:
            request = GeoEnrichmentRequest(
                point=GeoPoint(
                    latitude=float(latitude),
                    longitude=float(longitude),
                ),
                radius_m=int(radius_m),
                historical_date=GeoIntelligenceService._parse_date(
                    normalized_date
                ),
            )
        except (TypeError, ValueError) as exc:
            self._set_message(str(exc))
            return False

        self._run = {
            "hasRun": True,
            "status": "running",
            "latitude": request.point.latitude,
            "longitude": request.point.longitude,
            "historicalDate": normalized_date,
            "radiusMeters": request.radius_m,
            "nearbyPlaces": [],
            "weather": {
                "available": False,
                "summary": {},
                "hourly": [],
            },
            "providers": [],
            "summary": {
                "nearbyPlaces": 0,
                "weatherAvailable": False,
                "providerFailures": 0,
                "providerPartials": 0,
            },
            "transient": True,
            "persisted": False,
        }
        self._busy = True
        self._set_message("Running live GEO enrichment…")
        self.changed.emit()

        try:
            thread = QThread(self)
            worker = GeoEnrichmentWorker(
                latitude=request.point.latitude,
                longitude=request.point.longitude,
                historical_date=normalized_date,
                radius_m=request.radius_m,
            )
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.succeeded.connect(self._on_succeeded)
            worker.failed.connect(self._on_failed)
            worker.succeeded.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.succeeded.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(self._on_thread_finished)
            thread.finished.connect(thread.deleteLater)

            self._thread = thread
            self._worker = worker
            thread.start()
            return True
        except Exception as exc:
            self._busy = False
            self._thread = None
            self._worker = None
            self._run.update(
                {
                    "status": "failed",
                    "error": str(exc),
                }
            )
            self._set_message(
                "Unable to start GEO enrichment: " + str(exc)
            )
            self.changed.emit()
            return False

    @Slot(float, float, str, int, int, result=bool)
    def runSatelliteSearch(
        self,
        latitude: float,
        longitude: float,
        target_date: str,
        window_days: int,
        max_cloud_cover: int,
    ) -> bool:
        if self._satellite_busy:
            self._set_satellite_message("Satellite scene search is already running.")
            return False

        normalized_date = str(target_date or "").strip()

        try:
            from datetime import date

            if normalized_date:
                parsed_date = date.fromisoformat(normalized_date)
                if parsed_date > date.today():
                    raise ValueError("Satellite target date cannot be in the future.")

            latitude_value = float(latitude)
            longitude_value = float(longitude)
            if not -90.0 <= latitude_value <= 90.0:
                raise ValueError("latitude must be between -90 and 90.")
            if not -180.0 <= longitude_value <= 180.0:
                raise ValueError("longitude must be between -180 and 180.")

            window_value = int(window_days)
            cloud_value = int(max_cloud_cover)
            if not 0 <= window_value <= 30:
                raise ValueError("Satellite date window must be 0..30 days.")
            if not 0 <= cloud_value <= 100:
                raise ValueError("Maximum cloud cover must be 0..100.")
        except (TypeError, ValueError) as exc:
            self._set_satellite_message(str(exc))
            return False

        self._satellite = {
            "hasRun": True,
            "status": "running",
            "query": {
                "latitude": latitude_value,
                "longitude": longitude_value,
                "targetDate": normalized_date,
                "windowDays": window_value,
                "maxCloudCover": cloud_value,
            },
            "scenes": [],
            "selectedScene": {},
            "summary": {
                "sceneCount": 0,
                "quicklookCount": 0,
            },
            "transient": True,
            "persisted": False,
        }
        self._satellite_busy = True
        self._set_satellite_message("Searching Copernicus Sentinel-2 scenes…")
        self.changed.emit()

        try:
            thread = QThread(self)
            worker = SatelliteSceneSearchWorker(
                latitude=latitude_value,
                longitude=longitude_value,
                target_date=normalized_date,
                window_days=window_value,
                max_cloud_cover=cloud_value,
            )
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.succeeded.connect(self._on_satellite_succeeded)
            worker.failed.connect(self._on_satellite_failed)
            worker.succeeded.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.succeeded.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(self._on_satellite_thread_finished)
            thread.finished.connect(thread.deleteLater)

            self._satellite_thread = thread
            self._satellite_worker = worker
            thread.start()
            return True
        except Exception as exc:
            self._satellite_busy = False
            self._satellite_thread = None
            self._satellite_worker = None
            self._satellite.update(
                {
                    "status": "failed",
                    "error": str(exc),
                }
            )
            self._set_satellite_message(
                "Unable to start satellite scene search: " + str(exc)
            )
            self.changed.emit()
            return False

    @Slot(str, result=bool)
    def selectSatelliteScene(self, scene_id: str) -> bool:
        wanted = str(scene_id or "").strip()
        scenes = self._satellite.get("scenes")
        if not wanted or not isinstance(scenes, list):
            return False

        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            if str(scene.get("id") or "") == wanted:
                self._satellite["selectedScene"] = dict(scene)
                self.changed.emit()
                return True

        return False

    @Slot(str, int, result=bool)
    def renderSatelliteScene(
        self,
        scene_id: str,
        radius_m: int,
    ) -> bool:
        if self._satellite_render_busy:
            self._set_satellite_message("Satellite image rendering is already running.")
            return False

        wanted = str(scene_id or "").strip()
        scenes = self._satellite.get("scenes")
        query = self._satellite.get("query")
        if not wanted or not isinstance(scenes, list) or not isinstance(query, dict):
            self._set_satellite_message("Search Sentinel-2 scenes before rendering.")
            return False

        selected: dict[str, Any] | None = None
        for scene in scenes:
            if isinstance(scene, dict) and str(scene.get("id") or "") == wanted:
                selected = dict(scene)
                break
        if selected is None:
            self._set_satellite_message("Selected Sentinel-2 scene is unavailable.")
            return False

        try:
            latitude = float(query.get("latitude"))
            longitude = float(query.get("longitude"))
            radius = max(500, min(20_000, int(radius_m)))
        except (TypeError, ValueError):
            self._set_satellite_message("Satellite rendering coordinates are invalid.")
            return False

        if not self.satelliteRenderingAvailable:
            self._set_satellite_message(
                "True Color rendering needs CDSE_CLIENT_ID and CDSE_CLIENT_SECRET."
            )
            return False

        selected["renderStatus"] = "running"
        selected["renderError"] = ""
        self._satellite["selectedScene"] = selected
        self._satellite_render_busy = True
        self._set_satellite_message("Rendering Sentinel-2 True Color image…")
        self.changed.emit()

        try:
            thread = QThread(self)
            worker = SatelliteSceneRenderWorker(
                scene=selected,
                latitude=latitude,
                longitude=longitude,
                radius_m=radius,
            )
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.succeeded.connect(self._on_satellite_render_succeeded)
            worker.failed.connect(self._on_satellite_render_failed)
            worker.succeeded.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.succeeded.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(self._on_satellite_render_thread_finished)
            thread.finished.connect(thread.deleteLater)

            self._satellite_render_thread = thread
            self._satellite_render_worker = worker
            thread.start()
            return True
        except Exception as exc:
            self._satellite_render_busy = False
            self._satellite_render_thread = None
            self._satellite_render_worker = None
            selected["renderStatus"] = "failed"
            selected["renderError"] = str(exc)
            self._satellite["selectedScene"] = selected
            self._set_satellite_message(
                "Unable to start satellite rendering: " + str(exc)
            )
            self.changed.emit()
            return False

    @Slot()
    def clearSatellite(self) -> None:
        if self._satellite_busy or self._satellite_render_busy:
            return
        self._satellite = {}
        self._set_satellite_message("")
        self.changed.emit()

    @Slot()
    def clear(self) -> None:
        if self._busy:
            return
        self._run = {}
        self._set_message("")
        self.changed.emit()

    @Slot(object)
    def _on_succeeded(self, payload: object) -> None:
        self._busy = False
        self._run = (
            dict(payload)
            if isinstance(payload, dict)
            else {
                "hasRun": True,
                "status": "failed",
                "error": "GEO provider returned an invalid result.",
            }
        )

        status = str(self._run.get("status") or "")
        summary = self._run.get("summary")
        if not isinstance(summary, dict):
            summary = {}

        if status == "failed":
            self._set_message("GEO enrichment failed.")
        elif status == "partial":
            self._set_message(
                "GEO enrichment completed with provider warnings: "
                + str(int(summary.get("nearbyPlaces") or 0))
                + " nearby place(s)."
            )
        else:
            self._set_message(
                "GEO enrichment complete: "
                + str(int(summary.get("nearbyPlaces") or 0))
                + " nearby place(s)."
            )
        self.changed.emit()

    @Slot(object)
    def _on_failed(self, payload: object) -> None:
        self._busy = False
        data = dict(payload) if isinstance(payload, dict) else {}
        error = str(data.get("error") or "Unknown GEO enrichment failure.")
        self._run = {
            "hasRun": True,
            "status": "failed",
            "error": error,
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "historicalDate": data.get("historicalDate") or "",
            "radiusMeters": data.get("radiusMeters") or 0,
            "nearbyPlaces": [],
            "weather": {
                "available": False,
                "summary": {},
                "hourly": [],
            },
            "providers": [],
            "summary": {
                "nearbyPlaces": 0,
                "weatherAvailable": False,
                "providerFailures": 1,
                "providerPartials": 0,
            },
            "transient": True,
            "persisted": False,
        }
        self._set_message("GEO enrichment failed: " + error)
        self.changed.emit()

    @Slot(object)
    def _on_satellite_succeeded(self, payload: object) -> None:
        self._satellite_busy = False
        data = dict(payload) if isinstance(payload, dict) else {
            "status": "failed",
            "error": "Copernicus provider returned an invalid result.",
            "scenes": [],
        }

        scenes = data.get("scenes")
        if not isinstance(scenes, list):
            scenes = []
            data["scenes"] = scenes

        selected = (
            dict(scenes[0])
            if scenes and isinstance(scenes[0], dict)
            else {}
        )

        data["selectedScene"] = selected
        self._satellite = data

        status = str(data.get("status") or "")
        if status == "failed":
            self._set_satellite_message(
                "Copernicus Sentinel-2 scene search failed."
            )
        elif status == "partial":
            self._set_satellite_message(
                "Copernicus scene search completed with a provider warning."
            )
        else:
            self._set_satellite_message(
                "Copernicus scene search complete: "
                + str(len(scenes))
                + " scene(s)."
            )
        self.changed.emit()

    @Slot(object)
    def _on_satellite_failed(self, payload: object) -> None:
        self._satellite_busy = False
        data = dict(payload) if isinstance(payload, dict) else {}
        error = str(data.get("error") or "Unknown satellite scene search failure.")
        self._satellite = {
            "hasRun": True,
            "status": "failed",
            "error": error,
            "query": {
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "targetDate": data.get("targetDate") or "",
                "windowDays": data.get("windowDays") or 0,
                "maxCloudCover": data.get("maxCloudCover") or 0,
            },
            "scenes": [],
            "selectedScene": {},
            "summary": {
                "sceneCount": 0,
                "quicklookCount": 0,
            },
            "transient": True,
            "persisted": False,
        }
        self._set_satellite_message("Satellite scene search failed: " + error)
        self.changed.emit()

    @Slot(object)
    def _on_satellite_render_succeeded(self, payload: object) -> None:
        self._satellite_render_busy = False
        data = dict(payload) if isinstance(payload, dict) else {}
        selected = self._satellite.get("selectedScene")
        if not isinstance(selected, dict):
            selected = {}

        render_path = str(data.get("renderPath") or "").strip()
        selected["renderStatus"] = str(data.get("status") or "completed")
        selected["renderError"] = str(data.get("error") or "")
        selected["renderMode"] = str(data.get("renderMode") or "true_color")
        selected["renderBbox"] = data.get("renderBbox") or []
        selected["renderUrl"] = (
            QUrl.fromLocalFile(render_path).toString()
            if render_path
            else ""
        )
        selected["renderedBytes"] = int(data.get("imageBytes") or 0)
        self._satellite["selectedScene"] = selected

        if selected["renderUrl"]:
            self._set_satellite_message("Sentinel-2 True Color image ready.")
        else:
            self._set_satellite_message(
                str(data.get("error") or "Sentinel-2 rendering returned no image.")
            )
        self.changed.emit()

    @Slot(object)
    def _on_satellite_render_failed(self, payload: object) -> None:
        self._satellite_render_busy = False
        data = dict(payload) if isinstance(payload, dict) else {}
        selected = self._satellite.get("selectedScene")
        if not isinstance(selected, dict):
            selected = {}
        error = str(data.get("error") or "Unknown Sentinel-2 rendering failure.")
        selected["renderStatus"] = "failed"
        selected["renderError"] = error
        self._satellite["selectedScene"] = selected
        self._set_satellite_message("Satellite rendering failed: " + error)
        self.changed.emit()

    @Slot()
    def _on_satellite_render_thread_finished(self) -> None:
        self._satellite_render_busy = False
        self._satellite_render_thread = None
        self._satellite_render_worker = None
        self.changed.emit()

    @Slot()
    def _on_satellite_thread_finished(self) -> None:
        self._satellite_busy = False
        self._satellite_thread = None
        self._satellite_worker = None
        self.changed.emit()

    @Slot()
    def _on_thread_finished(self) -> None:
        self._busy = False
        self._thread = None
        self._worker = None
        self.changed.emit()

    def _set_satellite_message(self, value: str) -> None:
        normalized = str(value or "")
        if normalized == self._satellite_message:
            return
        self._satellite_message = normalized
        self.messageChanged.emit()

    def _set_map_source_message(self, value: str) -> None:
        normalized = str(value or "")
        if normalized == self._map_source_message:
            return
        self._map_source_message = normalized
        self.messageChanged.emit()

    def _set_map_layer_message(self, value: str) -> None:
        normalized = str(value or "")
        if normalized == self._map_layer_message:
            return
        self._map_layer_message = normalized
        self.messageChanged.emit()

    def _set_message(self, value: str) -> None:
        normalized = str(value or "")
        if normalized == self._message:
            return
        self._message = normalized
        self.messageChanged.emit()
