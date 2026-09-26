pragma ComponentBehavior: Bound
import QtQuick
import QtWebEngine

Item {
    id: root

    property var markers: []
    property string selectedMarkerId: ""
    property string selectedMarkerKind: ""
    property string baseMode: "streets"
    property var satelliteScene: ({})
    property var mapState: ({})
    property bool pageReady: false
    signal markerSelected(string kind, string markerId)
    signal comparePositionRequested(real position)
    signal mapUnavailable(string message)

    function selectedKey() {
        return root.selectedMarkerKind + ":" + root.selectedMarkerId
    }

    function syncState() {
        if (!root.pageReady)
            return
        var payload = {
            markers: root.markers || [],
            selectedKey: root.selectedKey(),
            baseMode: root.baseMode,
            satelliteScene: root.satelliteScene || ({}),
            mapState: root.mapState || ({})
        }
        webView.runJavaScript(
            "window.osintxzMap && window.osintxzMap.setState("
            + JSON.stringify(payload)
            + ");"
        )
    }

    function fitMarkers() {
        if (root.pageReady)
            webView.runJavaScript("window.osintxzMap && window.osintxzMap.fitMarkers();")
    }

    function focusMarker(kind, markerId) {
        if (!root.pageReady)
            return
        webView.runJavaScript(
            "window.osintxzMap && window.osintxzMap.focusMarker("
            + JSON.stringify(String(kind || ""))
            + ","
            + JSON.stringify(String(markerId || ""))
            + ");"
        )
    }

    onMarkersChanged: Qt.callLater(root.syncState)
    onSelectedMarkerIdChanged: Qt.callLater(root.syncState)
    onSelectedMarkerKindChanged: Qt.callLater(root.syncState)
    onBaseModeChanged: Qt.callLater(root.syncState)
    onSatelliteSceneChanged: Qt.callLater(root.syncState)
    onMapStateChanged: Qt.callLater(root.syncState)

    WebEngineProfile {
        id: mapProfile
        storageName: "osintxz-map"
        offTheRecord: false
        httpCacheType: WebEngineProfile.DiskHttpCache
        httpCacheMaximumSize: 268435456
        persistentCookiesPolicy: WebEngineProfile.NoPersistentCookies
        httpUserAgent: "OSINTXZ/0.1 InteractiveMap"
    }

    WebEngineView {
        id: webView
        anchors.fill: parent
        profile: mapProfile
        url: Qt.resolvedUrl("../map/map_engine.html")

        settings.javascriptEnabled: true
        settings.javascriptCanOpenWindows: false
        settings.localContentCanAccessRemoteUrls: true
        settings.localContentCanAccessFileUrls: true
        settings.unknownUrlSchemePolicy: WebEngineSettings.AllowUnknownUrlSchemesFromUserInteraction
        settings.webRTCPublicInterfacesOnly: true

        onLoadingChanged: function(loadRequest) {
            if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                root.pageReady = true
                Qt.callLater(root.syncState)
            } else if (loadRequest.status === WebEngineView.LoadFailedStatus) {
                var failedUrl = String(loadRequest.url || "")
                if (failedUrl.indexOf("osintxz://") !== 0) {
                    root.pageReady = false
                    root.mapUnavailable(String(loadRequest.errorString || "Interactive map failed to load."))
                }
            }
        }

        onNavigationRequested: function(request) {
            var target = String(request.url || "")
            if (target.indexOf("osintxz://external?") === 0) {
                request.reject()
                var externalQuery = target.substring(target.indexOf("?") + 1).split("&")
                for (var e = 0; e < externalQuery.length; ++e) {
                    var externalPair = externalQuery[e].split("=")
                    if (decodeURIComponent(externalPair[0] || "") === "url") {
                        desktopBridge.openExternalUrl(
                            decodeURIComponent(externalPair.slice(1).join("=") || "")
                        )
                        return
                    }
                }
                return
            }
            if (target.indexOf("osintxz://compare?") === 0) {
                request.reject()
                var compareQuery = target.substring(target.indexOf("?") + 1).split("&")
                for (var c = 0; c < compareQuery.length; ++c) {
                    var comparePair = compareQuery[c].split("=")
                    if (decodeURIComponent(comparePair[0] || "") === "position") {
                        var position = Number(
                            decodeURIComponent(comparePair.slice(1).join("=") || "0.5")
                        )
                        if (isFinite(position))
                            root.comparePositionRequested(position)
                        return
                    }
                }
                return
            }
            if (target.indexOf("osintxz://select?") === 0) {
                request.reject()
                var query = target.substring(target.indexOf("?") + 1).split("&")
                var kind = ""
                var markerId = ""
                for (var i = 0; i < query.length; ++i) {
                    var pair = query[i].split("=")
                    var key = decodeURIComponent(pair[0] || "")
                    var value = decodeURIComponent(pair.slice(1).join("=") || "")
                    if (key === "kind")
                        kind = value
                    else if (key === "id")
                        markerId = value
                }
                root.markerSelected(kind, markerId)
            }
        }
    }
}
