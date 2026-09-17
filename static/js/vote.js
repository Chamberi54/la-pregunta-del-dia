(function () {
    const form = document.getElementById("vote-form");
    if (!form) return;

    const choiceButtons = document.querySelectorAll(".choice-btn");
    const errorEl = document.getElementById("vote-error");
    let selectedChoice = null;

    choiceButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
            choiceButtons.forEach((b) => b.classList.remove("selected"));
            btn.classList.add("selected");
            selectedChoice = btn.dataset.choice;
            errorEl.textContent = "";
        });
    });

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        const city = document.getElementById("city-input").value;
        errorEl.textContent = "";

        if (!city) {
            errorEl.textContent = "Elige tu ciudad o pueblo primero.";
            return;
        }
        if (!selectedChoice) {
            errorEl.textContent = "Elige una opcion antes de votar.";
            return;
        }

        const formData = new FormData();
        formData.append("city", city);
        formData.append("choice", selectedChoice);

        fetch("/vote", { method: "POST", body: formData })
            .then((r) => r.json().then((data) => ({ ok: r.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) {
                    errorEl.textContent = data.error || "No se pudo registrar el voto.";
                    return;
                }
                window.location.reload();
            })
            .catch(() => {
                errorEl.textContent = "Error de conexion. Intentalo de nuevo.";
            });
    });
})();
