(function () {
    function resortProposals() {
        const list = document.querySelector(".proposal-list");
        if (!list) return;
        const rows = Array.from(list.querySelectorAll(".proposal-row"));
        rows.sort((a, b) => {
            const av = parseInt(a.querySelector(".vote-count").textContent, 10) || 0;
            const bv = parseInt(b.querySelector(".vote-count").textContent, 10) || 0;
            return bv - av;
        });
        rows.forEach((row) => list.appendChild(row));
    }

    document.querySelectorAll(".vote-proposal-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            if (btn.disabled) return;
            const row = btn.closest(".proposal-row");
            const proposalId = row.dataset.proposalId;

            btn.disabled = true;
            fetch("/propuestas/" + proposalId + "/votar", { method: "POST" })
                .then((r) => r.json().then((data) => ({ ok: r.ok, data })))
                .then(({ ok, data }) => {
                    if (!ok) {
                        btn.disabled = false;
                        return;
                    }
                    btn.classList.add("voted");
                    btn.querySelector(".vote-count").textContent = data.votes;
                    btn.querySelector(".vote-label").textContent = "Votado";
                    resortProposals();
                });
        });
    });
})();
