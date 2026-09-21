(function () {
    const COLOR_A = "#ffd400";
    const COLOR_B = "#ff2f92";
    const COLOR_NONE = "#2a2e42";

    const mapEl = document.getElementById("map");
    if (!mapEl) return;

    const { map, ready: mapReady } = createSpainMap("map");

    const markersByCity = {};
    const cityMarkersLayer = L.layerGroup();
    const canaryMarkersLayer = L.layerGroup();
    let lastQuestion = null;
    let lastTotals = { A: 0, B: 0 };
    let canaryMapRef = null;
    let caGroups = {};

    function renderTotals(question, totals) {
        const bar = document.getElementById("totals-bar");
        const totalLabel = document.getElementById("total-votes-label");
        const total = totals.A + totals.B;

        if (!question || total === 0) {
            bar.innerHTML = "";
            if (totalLabel) totalLabel.textContent = "Todavia no hay votos hoy";
            return;
        }

        const pctA = Math.round((totals.A / total) * 100);
        const pctB = 100 - pctA;
        bar.innerHTML =
            '<div class="side-a" style="width:' + pctA + '%">' + pctA + "% " + question.option_a + "</div>" +
            '<div class="side-b" style="width:' + pctB + '%">' + pctB + "% " + question.option_b + "</div>";
        if (totalLabel) totalLabel.textContent = total.toLocaleString("es-ES") + " votos hasta ahora";
    }

    function groupByCa(cities) {
        const groups = {};
        cities.forEach((c) => {
            const total = c.A + c.B;
            if (total === 0) return;
            const caName = c.ca || "Otros";
            if (!groups[caName]) {
                groups[caName] = { ca: caName, image: c.image, A: 0, B: 0, cities: [] };
            }
            groups[caName].A += c.A;
            groups[caName].B += c.B;
            groups[caName].cities.push({ ...c, total });
        });
        return groups;
    }

    function renderCityMarkers(question, cities) {
        cities.forEach((c) => {
            const total = c.A + c.B;
            if (total === 0) return;
            const pctA = c.A / total;
            const color = pctA >= 0.5 ? COLOR_A : COLOR_B;
            const textColor = pctA >= 0.5 ? "#1a1400" : "#2a0016";
            const winner = pctA >= 0.5 ? question.option_a : question.option_b;
            const isCanary = c.ca === "Canarias";
            const radius = Math.min(3 + Math.sqrt(total) * (isCanary ? 0.5 : 1.1), isCanary ? 7 : 15);

            const targetLayer = isCanary ? canaryMarkersLayer : cityMarkersLayer;
            const marker = L.circleMarker([c.lat, c.lon], {
                radius: radius,
                color: color,
                fillColor: color,
                fillOpacity: 0.55,
                weight: 1,
            })
                .addTo(targetLayer)
                .bindPopup(
                    "<strong style='color:" + textColor + "'>" + c.city + "</strong><br>" +
                    question.option_a + ": " + c.A + "<br>" +
                    question.option_b + ": " + c.B + "<br>" +
                    "Gana: " + winner
                );
            markersByCity[c.city.toLowerCase()] = { marker: marker, isCanary: isCanary };
        });

        cityMarkersLayer.addTo(map);
    }

    function slugifyCa(name) {
        return "ca-" + name.replace(/\s+/g, "-");
    }

    function openAndHighlightGroup(caName) {
        const group = document.getElementById(slugifyCa(caName));
        if (!group) return;
        group.open = true;
        group.scrollIntoView({ behavior: "smooth", block: "center" });
        group.classList.add("highlighted");
        setTimeout(() => group.classList.remove("highlighted"), 1500);
    }

    function styleRegionLayer(featureLayer, question, interactive) {
        const caName = featureLayer.feature.properties.ca;
        const g = caGroups[caName];
        const total = g ? g.A + g.B : 0;

        let fillColor = COLOR_NONE;
        if (total > 0 && question) {
            fillColor = g.A >= g.B ? COLOR_A : COLOR_B;
        }
        featureLayer.setStyle({ fillColor: fillColor, fillOpacity: total > 0 ? 0.75 : 0.35 });

        featureLayer.unbindTooltip();
        if (total > 0 && question) {
            const pctA = Math.round((g.A / total) * 100);
            const pctB = 100 - pctA;
            featureLayer.bindTooltip(
                "<strong>" + caName + "</strong><br>" + pctA + "% " + question.option_a +
                " &middot; " + pctB + "% " + question.option_b,
                { sticky: true }
            );
        } else {
            featureLayer.bindTooltip(caName + " &middot; sin votos", { sticky: true });
        }

        featureLayer.off("click mouseover mouseout");
        if (interactive) {
            featureLayer.on("mouseover", () => featureLayer.setStyle({ weight: 2.5, color: "#ffffff" }));
            featureLayer.on("mouseout", () => featureLayer.setStyle({ weight: 1.5, color: "rgba(255,255,255,0.45)" }));
            featureLayer.on("click", () => openAndHighlightGroup(caName));
        }
    }

    function resetRegionLayer(featureLayer) {
        featureLayer.setStyle({ fillColor: "#333a56", fillOpacity: 1, weight: 1.5, color: "rgba(255,255,255,0.45)" });
        featureLayer.unbindTooltip();
        featureLayer.off("click mouseover mouseout");
    }

    function setupMapModeToggle(mapParts, question) {
        const select = document.getElementById("map-view-select");
        if (!select) return;
        const legendNone = document.getElementById("legend-none");

        function applyMode(mode) {
            const isComunidades = mode === "comunidades";

            if (isComunidades) {
                map.removeLayer(cityMarkersLayer);
                if (canaryMapRef) canaryMarkersLayer.remove();
            } else {
                cityMarkersLayer.addTo(map);
                if (canaryMapRef) canaryMarkersLayer.addTo(canaryMapRef);
            }

            mapParts.layer.eachLayer((fl) => {
                if (isComunidades) styleRegionLayer(fl, question, true);
                else resetRegionLayer(fl);
            });
            if (mapParts.canaryLayer) {
                mapParts.canaryLayer.eachLayer((fl) => {
                    if (isComunidades) styleRegionLayer(fl, question, true);
                    else resetRegionLayer(fl);
                });
            }

            if (legendNone) legendNone.classList.toggle("visible", isComunidades);
        }

        select.addEventListener("change", () => applyMode(select.value));
        applyMode(select.value);
    }

    function renderCityGrid(question) {
        const grid = document.getElementById("city-results-grid");
        if (!grid) return;
        grid.innerHTML = "";

        const sortedGroups = Object.values(caGroups).sort((a, b) => (b.A + b.B) - (a.A + a.B));

        sortedGroups.forEach((group) => {
            const total = group.A + group.B;
            group.cities.sort((a, b) => b.total - a.total);

            const section = document.createElement("details");
            section.className = "ca-group";
            section.id = slugifyCa(group.ca);
            section.dataset.ca = group.ca.toLowerCase();

            const header = document.createElement("summary");
            header.className = "ca-group-header";
            const pctA = Math.round((group.A / total) * 100);
            const pctB = 100 - pctA;
            header.innerHTML =
                (group.image ? '<img src="' + group.image + '" alt="' + group.ca + '">' : "") +
                "<span>" + group.ca + "<em>" + pctA + "% / " + pctB + "%</em></span>" +
                '<div class="ca-group-bar">' +
                '<div class="part-a" style="width:' + pctA + '%"></div>' +
                '<div class="part-b" style="width:' + pctB + '%"></div>' +
                "</div>";
            section.appendChild(header);

            const cityList = document.createElement("div");
            cityList.className = "ca-group-cities";

            group.cities.forEach((c) => {
                const cPctA = Math.round((c.A / c.total) * 100);
                const cPctB = 100 - cPctA;
                const row = document.createElement("div");
                row.className = "city-row";
                row.dataset.city = c.city.toLowerCase();
                row.innerHTML =
                    '<div class="city-name">' + c.city + "</div>" +
                    '<div class="split-bar">' +
                    '<div class="part-a" style="width:' + cPctA + '%"></div>' +
                    '<div class="part-b" style="width:' + cPctB + '%"></div>' +
                    "</div>" +
                    '<div class="split-labels"><span>' + cPctA + "%</span><span>" + cPctB + "%</span></div>";
                cityList.appendChild(row);
            });

            section.appendChild(cityList);
            grid.appendChild(section);
        });
    }

    function setupSearch() {
        const searchInput = document.getElementById("city-search");
        if (!searchInput) return;
        const emptyMsg = document.getElementById("search-empty");

        searchInput.addEventListener("input", () => {
            const term = searchInput.value.trim().toLowerCase();
            const groups = document.querySelectorAll("#city-results-grid .ca-group");
            let anyVisible = false;

            groups.forEach((group) => {
                const rows = group.querySelectorAll(".city-row");
                let groupHasMatch = false;
                rows.forEach((row) => {
                    const matches = !term || row.dataset.city.includes(term);
                    row.style.display = matches ? "" : "none";
                    if (matches) groupHasMatch = true;
                });
                group.style.display = groupHasMatch ? "" : "none";
                if (term) group.open = groupHasMatch;
                if (groupHasMatch) anyVisible = true;
            });

            if (emptyMsg) emptyMsg.classList.toggle("hidden", anyVisible || !term);

            if (term && markersByCity[term]) {
                const entry = markersByCity[term];
                if (!entry.isCanary) {
                    map.flyTo(entry.marker.getLatLng(), 9);
                }
                entry.marker.openPopup();
            }
        });
    }

    function setupShare() {
        const shareBtn = document.getElementById("share-button");
        if (!shareBtn) return;

        shareBtn.addEventListener("click", async () => {
            if (!lastQuestion) return;
            const total = lastTotals.A + lastTotals.B;
            const pctA = total ? Math.round((lastTotals.A / total) * 100) : 50;
            const pctB = 100 - pctA;
            const text =
                "Hoy Espana vota: " + pctA + "% " + lastQuestion.option_a +
                " vs " + pctB + "% " + lastQuestion.option_b +
                " en La Pregunta del Dia";
            const imageUrl = "/share-image.png" + (lastQuestion.date ? "?date=" + encodeURIComponent(lastQuestion.date) : "");

            try {
                const imgResp = await fetch(imageUrl);
                const blob = await imgResp.blob();
                const file = new File([blob], "resultado.png", { type: "image/png" });

                if (navigator.canShare && navigator.canShare({ files: [file] })) {
                    await navigator.share({ files: [file], text: text, url: window.location.href });
                    return;
                }
            } catch (err) {
                // sigue a los siguientes metodos si falla la carga/comparticion de la imagen
            }

            if (navigator.share) {
                try {
                    await navigator.share({ text: text, url: window.location.href });
                    return;
                } catch (err) {
                    return;
                }
            }

            const link = document.createElement("a");
            link.href = imageUrl;
            link.download = "resultado.png";
            document.body.appendChild(link);
            link.click();
            link.remove();

            try {
                await navigator.clipboard.writeText(text + " - " + window.location.href);
                shareBtn.textContent = "Imagen descargada y texto copiado!";
                setTimeout(() => { shareBtn.textContent = "Compartir resultado"; }, 2500);
            } catch (err) {
                shareBtn.textContent = "Imagen descargada";
                setTimeout(() => { shareBtn.textContent = "Compartir resultado"; }, 2500);
            }
        });
    }

    const params = new URLSearchParams(window.location.search);
    const dateParam = params.get("date");
    const apiUrl = "/api/resultados" + (dateParam ? "?date=" + encodeURIComponent(dateParam) : "");

    Promise.all([mapReady, fetch(apiUrl).then((r) => r.json())])
        .then(([mapParts, data]) => {
            canaryMapRef = mapParts.canaryMap;
            lastQuestion = data.question;
            lastTotals = data.totals;
            renderTotals(data.question, data.totals);
            if (data.question) {
                caGroups = groupByCa(data.cities);
                renderCityMarkers(data.question, data.cities);
                renderCityGrid(data.question);
                setupMapModeToggle(mapParts, data.question);
            }
            setupSearch();
            setupShare();
        });
})();
