/* ────────────────────────────────────────────────────────────────────────
   Customer Churn Predictor — client logic
   ────────────────────────────────────────────────────────────────────────
   - On page load, GET /api/model-info → fills the banner
   - On form submit, POST /api/predict → shows the result card

   The API base path is configurable so this same JS works:
     • locally (set API_BASE to "http://localhost:8000")
     • behind ALB ingress (API_BASE = "/api"; ingress rewrites correctly)
*/

const API_BASE = "/api";   // change to "http://localhost:8000" for local dev


// ─── On page load: fetch model info ──────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
    await loadModelInfo();
    document.getElementById("predict-form").addEventListener("submit", onSubmit);
});

async function loadModelInfo() {
    const banner = document.getElementById("model-banner");
    const text   = document.getElementById("model-text");
    const dot    = banner.querySelector(".dot");

    try {
        const resp = await fetch(`${API_BASE}/model-info`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const info = await resp.json();
        text.textContent = `Model: ${info.name} @${info.alias} (v${info.version}, ${info.flavor})`;
        dot.classList.remove("pending");
        dot.classList.add("ready");
    } catch (err) {
        text.textContent = `⚠️ Could not load model info (${err.message})`;
        dot.classList.remove("pending");
        dot.classList.add("error");
    }
}


// ─── Convert form values to the JSON shape the backend expects ──────────
function buildPayload(form) {
    const data = new FormData(form);
    const v    = (name) => data.get(name);
    const num  = (name) => Number(v(name));

    // Derived numeric features (must match Gold pipeline logic in 03_gold_features.py)
    const tenure = num("tenure_months");
    const monthly = num("monthly_charges");
    const total  = num("total_charges");
    const avgPerMonth = tenure > 0 ? total / tenure : monthly;

    // One-hot expansion for the multi-class fields
    const internet = v("internet_service");
    const contract = v("contract_type");
    const payment  = v("payment_method");

    return {
        tenure_months:         tenure,
        monthly_charges:       monthly,
        total_charges:         total,
        avg_charge_per_month:  Number(avgPerMonth.toFixed(2)),

        senior_citizen:        num("senior_citizen"),
        partner:               num("partner"),
        dependents:            num("dependents"),
        phone_service:         num("phone_service"),
        paperless_billing:     num("paperless_billing"),
        gender_male:           num("gender_male"),
        is_long_tenure:        tenure >= 24 ? 1 : 0,
        is_high_spender:       monthly >= 75 ? 1 : 0,

        internet_service_dsl:         internet === "dsl"         ? 1 : 0,
        internet_service_fiber_optic: internet === "fiber optic" ? 1 : 0,
        internet_service_no:          internet === "no"          ? 1 : 0,

        contract_type_month_to_month: contract === "month-to-month" ? 1 : 0,
        contract_type_one_year:       contract === "one year"       ? 1 : 0,
        contract_type_two_year:       contract === "two year"       ? 1 : 0,

        payment_method_electronic_check: payment === "electronic check" ? 1 : 0,
        payment_method_mailed_check:     payment === "mailed check"     ? 1 : 0,
        payment_method_bank_transfer:    payment === "bank transfer"    ? 1 : 0,
        payment_method_credit_card:      payment === "credit card"      ? 1 : 0,
    };
}


// ─── Submit handler ──────────────────────────────────────────────────────
async function onSubmit(event) {
    event.preventDefault();
    const form    = event.target;
    const btn     = document.getElementById("predict-btn");
    const card    = document.getElementById("result-card");
    const headline = document.getElementById("result-headline");
    const probEl   = document.getElementById("result-prob");
    const rawEl    = document.getElementById("result-raw");

    btn.disabled    = true;
    btn.textContent = "Predicting…";

    const payload = buildPayload(form);

    try {
        const resp = await fetch(`${API_BASE}/predict`, {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify(payload),
        });

        const body = await resp.json();
        if (!resp.ok) {
            throw new Error(body.detail || body.error || `HTTP ${resp.status}`);
        }

        // Render result
        headline.classList.remove("churn", "stay");
        if (body.prediction === 1) {
            headline.textContent = "⚠️  Likely to CHURN";
            headline.classList.add("churn");
        } else {
            headline.textContent = "✅  Likely to STAY";
            headline.classList.add("stay");
        }
        probEl.textContent = `${(body.probability * 100).toFixed(1)} %`;
        rawEl.textContent  = JSON.stringify(body, null, 2);
        card.classList.remove("hidden");
        card.scrollIntoView({ behavior: "smooth", block: "nearest" });

    } catch (err) {
        headline.classList.remove("churn", "stay");
        headline.textContent = `❌ Error: ${err.message}`;
        probEl.textContent = "—";
        rawEl.textContent  = String(err);
        card.classList.remove("hidden");
    } finally {
        btn.disabled    = false;
        btn.textContent = "Predict churn →";
    }
}
