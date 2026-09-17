(function () {
    const COLOR_A = "#ffd400";
    const COLOR_B = "#ff2f92";
    const COLOR_NONE = "#2a2e42";

    const list = document.getElementById("ca-list");
    const script = document.currentScript;
    const selectedDate = script.dataset.date;
    const apiUrl = "/api/comunidades" + (selectedDate ? "?date=" + encodeURIComponent(selectedDate) : "");

    const caImagesEl = document.getElementById("ca-images-data");
    const CA_IMAGES = caImagesEl ? JSON.parse(caImagesEl.textContent) : {};

    function slugify(name) {
        return "ca-" + name.replace(/\s+/g, "-");
    }

    function imageFor(caName) {
        const slug = CA_IMAGES[caName];
        return slug ? "/static/images/ca/" + slug + ".jpg" : null;
    }

    function renderTotals(question, totals) {
        const bar = document.getElementById("totals-bar");
        if (!bar) return;
        const total = totals.A + totals.B;
        if (!question || total === 0) {
            bar.innerHTML = "";
            return;
        }
        const pctA = Math.round((totals.A / total) * 100);
        const pctB = 100 - pctA;
        bar.innerHTML =
            '<div class="side-a" style="width:' + pctA + '%">' + pctA + "% " + question.option_a + "</div>" +
            '<div class="side-b" style="width:' + pctB + '%">' + pctB + "% " + question.option_b + "</div>";
    }

    function renderList(question, comunidadesData) {
        if (!list) return;
        list.innerHTML = "";

        const dataByName = {};
        comunidadesData.forEach((c) => { dataByName[c.ca] = c; });

        const allNames = Object.keys(CA_IMAGES);
        const rows = allNames.map((name) => {
            const d = dataByName[name] || { ca: name, A: 0, B: 0 };
            return { ca: name, A: d.A, B: d.B, total: d.A + d.B };
        });
        rows.sort((a, b) => b.total - a.total);

        rows.forEach((c) => {
            const row = document.createElement("div");
            row.className = "ca-row";
            row.id = slugify(c.ca);
            const img = imageFor(c.ca);
            const thumb = img ? '<img class="ca-thumb" src="' + img + '" alt="' + c.ca + '">' : "";

            if (c.total === 0) {
                row.innerHTML =
                    thumb +
                    '<div class="ca-row-body"><div class="ca-name">' + c.ca + '<span class="fine-print"> &middot; sin votos todavia</span></div></div>';
            } else {
                const pctA = Math.round((c.A / c.total) * 100);
                const pctB = 100 - pctA;
                row.innerHTML =
                    thumb +
                    '<div class="ca-row-body">' +
                    '<div class="ca-name">' + c.ca + '<span class="fine-print"> &middot; ' + c.total + " votos</span></div>" +
                    '<div class="split-bar">' +
                    '<div class="part-a" style="width:' + pctA + '%"></div>' +
                    '<div class="part-b" style="width:' + pctB + '%"></div>' +
                    "</div>" +
                    '<div class="split-labels"><span>' + pctA + "% " + question.option_a + "</span><span>" + pctB + "% " + question.option_b + "</span></div>" +
                    "</div>";
            }
            list.appendChild(row);
        });
    }

    function highlightRow(caName) {
        const row = document.getElementById(slugify(caName));
        if (!row) return;
        row.scrollIntoView({ behavior: "smooth", block: "center" });
        row.classList.add("highlighted");
        setTimeout(() => row.classList.remove("highlighted"), 1500);
    }

    function styleFeatureLayer(featureLayer, dataByName, question) {
        const caName = featureLayer.feature.properties.ca;
        const d = dataByName[caName];
        const total = d ? d.A + d.B : 0;

        let fillColor = COLOR_NONE;
        if (total > 0 && question) {
            fillColor = d.A >= d.B ? COLOR_A : COLOR_B;
        }
        featureLayer.setStyle({ fillColor: fillColor, fillOpacity: total > 0 ? 0.75 : 0.35 });

        if (total > 0 && question) {
            const pctA = Math.round((d.A / total) * 100);
            const pctB = 100 - pctA;
            featureLayer.bindTooltip(
                "<strong>" + caName + "</strong><br>" + pctA + "% " + question.option_a +
                " &middot; " + pctB + "% " + question.option_b,
                { sticky: true }
            );
        } else {
            featureLayer.bindTooltip(caName + " &middot; sin votos", { sticky: true });
        }

        featureLayer.on("mouseover", () => featureLayer.setStyle({ weight: 2.5, color: "#ffffff" }));
        featureLayer.on("mouseout", () => featureLayer.setStyle({ weight: 1.5, color: "rgba(255,255,255,0.45)" }));
        featureLayer.on("click", () => highlightRow(caName));
    }

    const { ready: mapReady } = createSpainMap("map");

    Promise.all([mapReady, fetch(apiUrl).then((r) => r.json())]).then(([mapParts, data]) => {
        renderTotals(data.question, data.totals);
        renderList(data.question, data.comunidades || []);

        const dataByName = {};
        (data.comunidades || []).forEach((c) => { dataByName[c.ca] = c; });

        mapParts.layer.eachLayer((featureLayer) => styleFeatureLayer(featureLayer, dataByName, data.question));
        if (mapParts.canaryLayer) {
            mapParts.canaryLayer.eachLayer((featureLayer) => styleFeatureLayer(featureLayer, dataByName, data.question));
        }
    });
})();
