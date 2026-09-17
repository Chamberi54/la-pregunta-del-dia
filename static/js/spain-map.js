function createSpainMap(containerId) {
    const map = L.map(containerId, { attributionControl: false, zoomSnap: 0.25 }).setView([40.2, -3.7], 5);

    const baseStyle = {
        color: "rgba(255,255,255,0.45)",
        weight: 1.5,
        fillColor: "#333a56",
        fillOpacity: 1,
    };

    const ready = fetch("/static/data/spain-comunidades.geojson")
        .then((r) => r.json())
        .then((geojson) => {
            const mainFeatures = geojson.features.filter((f) => f.properties.ca !== "Canarias");
            const canaryFeature = geojson.features.find((f) => f.properties.ca === "Canarias");

            const layer = L.geoJSON({ type: "FeatureCollection", features: mainFeatures }, { style: baseStyle }).addTo(map);
            const bounds = layer.getBounds();
            map.fitBounds(bounds, { padding: [24, 24] });
            map.setMaxBounds(bounds.pad(0.25));
            map.setMinZoom(map.getZoom() - 0.5);

            let canaryMap = null;
            let canaryLayer = null;

            if (canaryFeature) {
                const container = document.getElementById(containerId);
                const insetEl = document.createElement("div");
                insetEl.className = "spain-map-inset";
                container.appendChild(insetEl);

                canaryMap = L.map(insetEl, {
                    attributionControl: false,
                    zoomControl: false,
                    dragging: false,
                    scrollWheelZoom: false,
                    doubleClickZoom: false,
                    boxZoom: false,
                    keyboard: false,
                    tap: false,
                    zoomSnap: 0.1,
                });
                canaryLayer = L.geoJSON(canaryFeature, { style: baseStyle }).addTo(canaryMap);
                canaryMap.fitBounds(canaryLayer.getBounds(), { padding: [6, 6] });
            }

            return { map, layer, canaryMap, canaryLayer, geojson };
        });

    return { map, ready };
}
