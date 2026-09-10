const API =
    window.location.protocol === "file:"
        ? "http://127.0.0.1:8000"
        : window.location.origin;

let map = null;
let selectedFile = null;
let latitude = null;
let longitude = null;

let mapLayers = [];


// =====================================================
// PAGE LOAD
// =====================================================

document.addEventListener("DOMContentLoaded", function () {

    console.log("ResQAI frontend loaded");

    initMap();
    loadDashboard();


    // =================================================
    // REFRESH
    // =================================================

    const refreshBtn =
        document.getElementById("refresh-btn");

    if (refreshBtn) {

        refreshBtn.addEventListener("click", function (e) {

            e.preventDefault();

            refreshData();

        });

    }


    // =================================================
    // IMAGE UPLOAD
    // =================================================

    const imageInput =
        document.getElementById("risk-image");

    const chooseImageBtn =
        document.getElementById("choose-image-btn");

    const predictBtn =
        document.getElementById("predict-btn");


    if (chooseImageBtn && imageInput) {

        chooseImageBtn.addEventListener(
            "click",
            function (e) {

                e.preventDefault();

                imageInput.click();

            }
        );

    }


    if (imageInput) {

        imageInput.addEventListener(
            "change",
            function () {

                selectedFile =
                    imageInput.files[0] || null;


                const fileName =
                    document.getElementById("file-name");


                if (fileName) {

                    fileName.textContent =
                        selectedFile
                            ? selectedFile.name
                            : "No image selected";

                }


                if (predictBtn) {

                    predictBtn.disabled =
                        !selectedFile;

                }


                console.log(
                    "Selected image:",
                    selectedFile
                );

            }
        );

    }


    // =================================================
    // PREDICT
    // =================================================

    if (predictBtn) {

        predictBtn.addEventListener(
            "click",
            function (e) {

                e.preventDefault();
                e.stopPropagation();

                predictRisk();

            }
        );

    }


    // =================================================
    // GPS
    // =================================================

    const locationBtn =
        document.getElementById("location-btn");


    if (locationBtn) {

        locationBtn.addEventListener(
            "click",
            function (e) {

                e.preventDefault();

                getLocation();

            }
        );

    }


    // =================================================
    // FIELD REPORT
    // =================================================

    const submitReportBtn =
        document.getElementById(
            "submit-report-btn"
        );


    if (submitReportBtn) {

        submitReportBtn.addEventListener(
            "click",
            function (e) {

                e.preventDefault();

                submitReport();

            }
        );

    }

    restorePredictionResult();

});


// =====================================================
// MAP
// =====================================================

function initMap() {

    const mapElement =
        document.getElementById("risk-map");


    if (!mapElement) {

        console.error("Risk map element not found");

        return;

    }


    map = L.map("risk-map").setView(
        [25.8, 93.9],
        6
    );


    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            attribution:
                "&copy; OpenStreetMap contributors"
        }
    ).addTo(map);

}


// =====================================================
// DASHBOARD
// =====================================================

async function loadDashboard() {

    if (!map) {
        return;
    }


    // -------------------------------------------------
    // Remove old map layers
    // -------------------------------------------------

    mapLayers.forEach(function (layer) {

        map.removeLayer(layer);

    });

    mapLayers = [];


    // -------------------------------------------------
    // RISK ZONES
    // -------------------------------------------------

    try {

        const response =
            await fetch(
                API + "/risk-zones",
                {
                    cache: "no-store"
                }
            );


        if (!response.ok) {

            throw new Error(
                "Risk zones request failed"
            );

        }


        const data =
            await response.json();


        const zones =
            Array.isArray(data.zones)
                ? data.zones
                : [];


        zones.forEach(function (z) {

            const color =
                z.risk === "HIGH"
                    ? "#ff5f67"
                    : z.risk === "MODERATE"
                        ? "#f4a847"
                        : "#31c99f";


            // Circle

            const circle =
                L.circle(
                    [z.lat, z.lng],
                    {
                        radius: 28000,
                        color: color,
                        fillColor: color,
                        fillOpacity: 0.16,
                        weight: 2
                    }
                )
                .addTo(map)
                .bindPopup(`
                    <b>${z.state}</b><br>
                    Risk: ${z.risk}<br>
                    Rainfall: ${z.rainfall} mm<br>
                    Soil moisture: ${z.moisture}%
                `);


            mapLayers.push(circle);


            // Marker

            const marker =
                L.marker(
                    [z.lat, z.lng]
                )
                .addTo(map)
                .bindTooltip(z.state);


            mapLayers.push(marker);

        });

    }

    catch (error) {

        console.warn(
            "Risk zones unavailable:",
            error
        );

    }


    // -------------------------------------------------
    // DASHBOARD
    // -------------------------------------------------

    try {

        const response =
            await fetch(
                API + "/dashboard",
                {
                    cache: "no-store"
                }
            );


        if (!response.ok) {

            throw new Error(
                "Dashboard request failed"
            );

        }


        const data =
            await response.json();


        const overallRisk =
            document.getElementById(
                "overall-risk"
            );


        if (
            overallRisk &&
            data.overall_risk
        ) {

            overallRisk.textContent =
                data.overall_risk;

        }


        const riskZones =
            document.getElementById(
                "risk-zones"
            );


        if (
            riskZones &&
            data.high_risk_zones != null
        ) {

            riskZones.textContent =
                String(
                    data.high_risk_zones
                ).padStart(2, "0");

        }


        const activeAlerts =
            document.getElementById(
                "active-alerts"
            );


        if (
            activeAlerts &&
            data.active_alerts != null
        ) {

            activeAlerts.textContent =
                String(
                    data.active_alerts
                ).padStart(2, "0");

        }


        // Weather

        const weatherStatus =
            document.getElementById(
                "weather-status"
            );


        const weatherDescription =
            document.getElementById(
                "weather-description"
            );


        if (
            weatherStatus &&
            data.weather
        ) {

            weatherStatus.textContent =
                data.weather.status ||
                "UNKNOWN";

        }


        if (
            weatherDescription &&
            data.weather
        ) {

            weatherDescription.textContent =
                data.weather.forecast ||
                "No forecast available";

        }


        const lastUpdate =
            document.getElementById(
                "last-update"
            );


        if (lastUpdate) {

            lastUpdate.textContent =
                new Date().toLocaleTimeString();

        }

    }

    catch (error) {

        console.warn(
            "Dashboard unavailable:",
            error
        );

    }

}


// =====================================================
// REFRESH DATA
// =====================================================

function refreshData() {

    const lastUpdate =
        document.getElementById(
            "last-update"
        );


    if (lastUpdate) {

        lastUpdate.textContent =
            "refreshing...";

    }


    loadDashboard();

}


// =====================================================
// PREDICT RISK
// =====================================================

function restorePredictionResult() {

    const savedResult =
        localStorage.getItem("resqai-last-prediction");

    if (!savedResult) {
        return;
    }

    try {
        const parsedResult = JSON.parse(savedResult);
        const status = document.getElementById("prediction-status");
        const details = document.getElementById("prediction-details");
        const result = document.getElementById("prediction-result");

        if (status && details && result) {
            status.innerHTML = parsedResult.status;
            details.innerHTML = parsedResult.details;
            result.style.display = "block";
        }
    }
    catch (error) {
        localStorage.removeItem("resqai-last-prediction");
        console.error("Could not restore prediction result:", error);
    }
}

async function predictRisk() {

    const status =
        document.getElementById(
            "prediction-status"
        );


    const result =
        document.getElementById(
            "prediction-result"
        );


    const details =
        document.getElementById(
            "prediction-details"
        );


    // -------------------------------------------------
    // CHECK ELEMENTS
    // -------------------------------------------------

    if (!status || !result || !details) {

        console.error(
            "Prediction result elements missing"
        );

        return;

    }


    // -------------------------------------------------
    // CHECK IMAGE
    // -------------------------------------------------

    if (!selectedFile) {

        status.innerHTML = `
            <strong style="color:#ff666d;">
                Please select an image first.
            </strong>
        `;

        details.innerHTML = "";

        result.style.display = "block";

        return;

    }


    // -------------------------------------------------
    // SHOW LOADING
    // -------------------------------------------------

    result.style.display = "block";


    status.innerHTML = `
        <strong>Analyzing...</strong>
        <br>
        Processing image and environmental signals.
    `;


    details.innerHTML = `
        <p>
            Please wait...
        </p>
    `;


    // -------------------------------------------------
    // READ INPUTS
    // -------------------------------------------------

    const rainfall =
        document.getElementById(
            "rainfall-input"
        ).value;


    const moisture =
        document.getElementById(
            "moisture-input"
        ).value;


    const slope =
        document.getElementById(
            "slope-input"
        ).value;


    // -------------------------------------------------
    // FORM DATA
    // -------------------------------------------------

    const formData =
        new FormData();


    formData.append(
        "file",
        selectedFile
    );


    formData.append(
        "rainfall",
        rainfall
    );


    formData.append(
        "moisture",
        moisture
    );


    formData.append(
        "slope",
        slope
    );


    console.log(
        "Sending prediction request..."
    );


    console.log({
        file: selectedFile.name,
        rainfall: rainfall,
        moisture: moisture,
        slope: slope
    });


    // -------------------------------------------------
    // API REQUEST
    // -------------------------------------------------

    try {

        const response =
            await fetch(
                API + "/predict",
                {
                    method: "POST",
                    body: formData,
                    cache: "no-store"
                }
            );


        console.log(
            "Prediction HTTP status:",
            response.status
        );


        if (!response.ok) {

            const errorText =
                await response.text();


            throw new Error(
                `Server error ${response.status}: ${errorText}`
            );

        }


        // -------------------------------------------------
        // JSON
        // -------------------------------------------------

        const data =
            await response.json();


        console.log(
            "Prediction response:",
            data
        );


        // -------------------------------------------------
        // RISK STYLE
        // -------------------------------------------------

        let riskClass =
            "risk-low";


        if (data.risk === "HIGH") {

            riskClass =
                "risk-high";

        }
        else if (
            data.risk === "MODERATE"
        ) {

            riskClass =
                "risk-moderate";

        }


        // -------------------------------------------------
        // SUCCESS
        // -------------------------------------------------

        status.innerHTML = `
            <strong>
                ✓ Prediction Complete
            </strong>
        `;


        details.innerHTML = `

            <h4 class="${riskClass}">
                ${data.risk} RISK
            </h4>

            <p>
                <strong>Risk Score:</strong>
                ${data.score}/100
            </p>

            <p>
                <strong>Confidence:</strong>
                ${data.confidence}%
            </p>

            <p>
                <strong>Rainfall:</strong>
                ${data.rainfall} mm
            </p>

            <p>
                <strong>Soil Moisture:</strong>
                ${data.soil_moisture}%
            </p>

            <p>
                <strong>Slope:</strong>
                ${data.slope}°
            </p>

            <p>
                <strong>Risk Factors:</strong>
            </p>

            <ul>
                ${
                    Array.isArray(data.reasons)
                        ? data.reasons
                            .map(
                                reason =>
                                    `<li>${reason}</li>`
                            )
                            .join("")
                        : "<li>No major factors detected</li>"
                }
            </ul>

            <p>
                <strong>Recommendation:</strong>
                <br>
                ${
                    data.recommendation ||
                    "No recommendation available."
                }
            </p>

            <hr>

            <p>
                <strong>Image Analysis</strong>
            </p>

            <p>
                <strong>Image Model:</strong>
                ${
                    data.image_prediction &&
                    data.image_prediction.available
                        ? `${data.image_prediction.class} (${data.image_prediction.confidence}% confidence)`
                        : "Not trained yet"
                }
            </p>

            ${
                data.image_prediction &&
                !data.image_prediction.available
                    ? `<p>${data.image_prediction.message}</p>`
                    : ""
            }

            <p>
                Image:
                ${
                    data.image_analysis &&
                    data.image_analysis.image_valid
                        ? "Valid"
                        : "Invalid"
                }
            </p>

            ${
                data.image_analysis
                    ? `
                        <p>
                            Brightness:
                            ${data.image_analysis.brightness}
                        </p>

                        <p>
                            Green Ratio:
                            ${data.image_analysis.green_ratio}
                        </p>

                        <p>
                            Blue Ratio:
                            ${data.image_analysis.blue_ratio}
                        </p>
                    `
                    : ""
            }

        `;

        localStorage.setItem(
            "resqai-last-prediction",
            JSON.stringify({
                status: status.innerHTML,
                details: details.innerHTML
            })
        );


        // -------------------------------------------------
        // KEEP RESULT
        // -------------------------------------------------

        result.style.display = "block";


        console.log(
            "Prediction displayed successfully."
        );

    }

    catch (error) {

        console.error(
            "PREDICTION ERROR:",
            error
        );


        status.innerHTML = `
            <strong style="color:#ff666d;">
                Prediction Error
            </strong>
        `;


        details.innerHTML = `
            <p style="color:#ff666d;">
                ${error.message}
            </p>
        `;


        result.style.display = "block";

    }

}


// =====================================================
// GET LOCATION
// =====================================================

function getLocation() {

    const status =
        document.getElementById(
            "location-status"
        );


    if (!navigator.geolocation) {

        status.textContent =
            "GPS not supported";

        return;

    }


    status.textContent =
        "Getting location...";


    navigator.geolocation.getCurrentPosition(

        function (position) {

            latitude =
                position.coords.latitude;


            longitude =
                position.coords.longitude;


            status.textContent =
                `GPS captured (${latitude.toFixed(4)}, ${longitude.toFixed(4)})`;

        },


        function () {

            status.textContent =
                "Location permission denied";

        }

    );

}


// =====================================================
// FIELD REPORT
// =====================================================

async function submitReport() {

    const status =
        document.getElementById(
            "location-status"
        );


    const formData =
        new FormData();


    formData.append(
        "issue_type",
        document.getElementById(
            "issue-type"
        ).value
    );


    formData.append(
        "description",
        document.getElementById(
            "report-description"
        ).value
    );


    formData.append(
        "latitude",
        latitude ?? 0
    );


    formData.append(
        "longitude",
        longitude ?? 0
    );


    try {

        const response =
            await fetch(
                API + "/field-report",
                {
                    method: "POST",
                    body: formData
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                "Report submission failed"
            );

        }


        status.textContent =
            `✓ Report submitted • ID ${
                data.report_id ||
                "generated"
            }`;

    }

    catch (error) {

        console.error(
            "REPORT ERROR:",
            error
        );


        status.textContent =
            "Report submission failed. Check backend.";

    }

}