from __future__ import annotations

import ast
from pathlib import Path


QML_ROOT = Path("app/interface/desktop/qml")
BRIDGE = Path("app/interface/desktop/bridges/desktop_bridge.py")
PAYLOADS = Path("app/interface/desktop/analysis_workspace_payloads.py")


def _qml(name: str) -> str:
    return (QML_ROOT / "pages" / name).read_text(encoding="utf-8")


def _bridge() -> str:
    return BRIDGE.read_text(encoding="utf-8")


def _payloads() -> str:
    return PAYLOADS.read_text(encoding="utf-8")


def test_ui_r4_bridge_python_remains_syntactically_valid():
    ast.parse(_bridge())
    ast.parse(_payloads())


def test_ui_r4_analysis_workspace_routes_map_and_media_to_real_pages():
    qml = _qml("AnalysisWorkspace.qml")

    assert 'return "MapWorkspace.qml"' in qml
    assert 'return "MediaWorkspace.qml"' in qml
    assert '{ key: "map", label: "Map", icon: "pin_purple.svg", ready: true }' in qml
    assert '{ key: "media", label: "Media", icon: "document_blue.svg", ready: true }' in qml
    assert "FOUNDATION READY · DATA CONNECTION NEXT" not in qml


def test_ui_r4_media_workspace_is_case_level_and_uses_real_evidence_payload():
    qml = _qml("MediaWorkspace.qml")

    assert "desktopBridge.analysisMediaWorkspace" in qml
    assert 'property string mediaFilter: "all"' in qml
    assert '{ key: "image", label: "Images"' in qml
    assert '{ key: "video", label: "Video"' in qml
    assert '{ key: "audio", label: "Audio"' in qml
    assert "model: root.filteredMediaItems()" in qml
    assert "root.selectedItem.ocrText" in qml
    assert "root.selectedItem.faceCount" in qml
    assert "root.selectedItem.transcript" in qml
    assert "(root.selectedItem.gps || {}).available" in qml
    assert 'desktopBridge.focusWorkspaceRecord(' in qml
    assert '"evidence",' in qml


def test_ui_r4_media_workspace_prepares_external_osint_without_faking_it():
    qml = _qml("MediaWorkspace.qml")

    assert 'text: "EXTERNAL MEDIA OSINT"' in qml
    assert "Reverse-image discovery" in qml
    assert "connector stage" in qml
    assert "reverseImageResults" not in qml
    assert "fake" not in qml.lower()


def test_ui_r4_map_workspace_uses_real_markers_and_local_projection():
    qml = _qml("MapWorkspace.qml")

    assert "desktopBridge.analysisMapWorkspace" in qml
    assert "model: root.visibleMarkers()" in qml
    assert "function markerX(item, canvasWidth)" in qml
    assert "function markerY(item, canvasHeight)" in qml
    assert "((Number(item.longitude) + 180.0) / 360.0)" in qml
    assert "((90.0 - Number(item.latitude)) / 180.0)" in qml
    assert "id: projection" in qml
    assert "width / 2" in qml
    assert 'source: "../../assets/images/world_map_dots.svg"' in qml


def test_ui_r4_map_layers_distinguish_locations_photo_gps_and_future_satellite():
    qml = _qml("MapWorkspace.qml")

    assert 'text: "Locations"' in qml
    assert 'text: "Photo GPS"' in qml
    assert 'text: "Satellite · next"' in qml
    assert "Satellite imagery is not connected yet." in qml
    assert "Copernicus/Sentinel" in qml
    assert "satelliteImageUrl" not in qml


def test_ui_r4_bridge_stays_thin_and_payload_module_is_read_only():
    bridge = _bridge()
    payloads = _payloads()

    assert "def analysisMediaWorkspace(self)" in bridge
    assert "def analysisMapWorkspace(self)" in bridge
    assert "build_media_workspace_payload(" in bridge
    assert "build_map_workspace_payload(" in bridge
    assert "def _analysis_case_evidence(" not in bridge
    assert "WORKSPACE_LIMIT = 300" in payloads
    assert "def build_media_workspace_payload(" in payloads
    assert "def build_map_workspace_payload(" in payloads

    for forbidden in (
        ".create_entity(",
        ".create_evidence(",
        ".update_metadata(",
        ".commit(",
        ".delete_",
    ):
        assert forbidden not in payloads


def test_ui_r4_bridge_understands_supported_image_gps_metadata_layouts():
    from app.interface.desktop.analysis_workspace_payloads import extract_gps

    nested = {
        "processing_metadata": {
            "exif": {
                "normalized": {
                    "gps": {
                        "latitude": 46.4825,
                        "longitude": 30.7233,
                        "altitude": 42.0,
                    }
                }
            }
        }
    }
    gps = extract_gps(nested)

    assert gps == {
        "available": True,
        "latitude": 46.4825,
        "longitude": 30.7233,
        "altitude": 42.0,
    }

    compatibility = {
        "processing": {
            "metadata": {
                "gps_latitude": "50.4501",
                "gps_longitude": "30.5234",
            }
        }
    }
    fallback = extract_gps(compatibility)

    assert fallback["available"] is True
    assert fallback["latitude"] == 50.4501
    assert fallback["longitude"] == 30.5234


def test_ui_r4_payload_rejects_invalid_coordinates_in_presentation_layer():
    from app.interface.desktop.analysis_workspace_payloads import extract_gps

    gps = extract_gps(
        {
            "processing_metadata": {
                "gps_latitude": 120,
                "gps_longitude": 300,
            }
        }
    )

    assert gps["available"] is False
    assert gps["latitude"] is None
    assert gps["longitude"] is None
