const API_URL = "";
const REFRESH_MS = 5000;


// =====================================================
// AUTHENTICATED FETCH
// =====================================================

async function authFetch(url, options = {}) {

    const {
        data: { session },
        error
    } = await supabaseClient.auth.getSession();


    if (error || !session?.access_token) {

        throw new Error(
            "Authorization token required"
        );

    }


    const headers =
        new Headers(
            options.headers || {}
        );


    headers.set(
        "Authorization",
        `Bearer ${session.access_token}`
    );


    return fetch(
        url,
        {
            ...options,
            headers,
            cache:
                options.cache ||
                "no-store"
        }
    );
}


// =====================================================
// TEMPLE ID
// =====================================================

const urlParams =
    new URLSearchParams(
        window.location.search
    );


const TEMPLE_ID =
    urlParams.get("temple_id");


let zones = [];

let crowdChart = null;


const $ = (id) =>
    document.getElementById(id);


// =====================================================
// API STATUS
// =====================================================

function setApiStatus(online) {

    const el =
        $("apiStatus");


    if (!el) return;


    el.classList.toggle(
        "offline",
        !online
    );


    el.querySelector(
        "span:last-child"
    ).textContent =
        online
            ? "Connected"
            : "Offline";
}


// =====================================================
// TOAST
// =====================================================

function showToast(message) {

    const toast =
        $("toast");


    if (!toast) return;


    toast.textContent =
        message;


    toast.classList.add(
        "show"
    );


    clearTimeout(
        showToast.timer
    );


    showToast.timer =
        setTimeout(
            () =>
                toast.classList.remove(
                    "show"
                ),
            2600
        );
}


// =====================================================
// TIME
// =====================================================

function updateTime() {

    $("lastUpdated").textContent =
        new Date().toLocaleTimeString();
}


// =====================================================
// RISK CLASS
// =====================================================

function riskClass(risk) {

    return String(
        risk || "LOW"
    ).toLowerCase();
}


// =====================================================
// OCCUPANCY
// =====================================================

function getOccupancy(zone) {

    const capacity =
        Number(
            zone.capacity
        ) || 0;


    const crowd =
        Number(
            zone.crowd_count
        ) || 0;


    return capacity > 0
        ? (crowd / capacity) * 100
        : 0;
}


// =====================================================
// RENDER ZONES
// =====================================================

function renderZones(data) {

    const container =
        $("zonesContainer");


    if (!data.length) {

        container.innerHTML = `

            <div class="loading-card">

                No zones configured
                for this temple yet.

            </div>

        `;

        return;
    }


    container.innerHTML =
        data.map(
            zone => {

                const capacity =
                    Number(
                        zone.capacity
                    ) || 0;


                const crowd =
                    Number(
                        zone.crowd_count
                    ) || 0;


                const occupancy =
                    Math.min(
                        getOccupancy(zone),
                        100
                    );


                return `

                    <article class="zone-card">

                        <div class="zone-head">

                            <div>

                                <div class="zone-name">

                                    ${escapeHtml(
                                        zone.name
                                    )}

                                </div>


                                <div class="zone-id">

                                    ${
                                        zone.type
                                            ? escapeHtml(
                                                formatType(
                                                    zone.type
                                                )
                                            )
                                            : `ZONE ${String(
                                                zone.id
                                            ).padStart(
                                                2,
                                                "0"
                                            )}`
                                    }

                                </div>

                            </div>


                            <span
                                class="risk ${riskClass(
                                    zone.risk
                                )}"
                            >

                                ${escapeHtml(
                                    zone.risk ||
                                    "LOW"
                                )}

                            </span>

                        </div>


                        <div class="count-row">

                            <strong>

                                ${crowd.toLocaleString()}

                            </strong>


                            <span>

                                of
                                ${capacity.toLocaleString()}
                                capacity

                            </span>

                        </div>


                        <div class="progress">

                            <div
                                class="progress-bar"
                                style="width:${occupancy.toFixed(
                                    1
                                )}%"
                            ></div>

                        </div>


                        <div class="zone-foot">

                            <span>
                                Occupancy
                            </span>


                            <strong>

                                ${occupancy.toFixed(
                                    1
                                )}%

                            </strong>

                        </div>

                    </article>

                `;

            }
        ).join("");
}


// =====================================================
// UPDATE STATISTICS
// =====================================================

function updateStatistics(data) {

    const totalCapacity =
        data.reduce(
            (sum, z) =>
                sum +
                (
                    Number(
                        z.capacity
                    ) || 0
                ),
            0
        );


    const totalCrowd =
        data.reduce(
            (sum, z) =>
                sum +
                (
                    Number(
                        z.crowd_count
                    ) || 0
                ),
            0
        );


    const avg =
        totalCapacity
            ? (
                totalCrowd /
                totalCapacity
            ) * 100
            : 0;


    const highRisk =
        data.filter(
            z => {

                const risk =
                    String(
                        z.risk || ""
                    ).toUpperCase();


                return (
                    risk === "HIGH" ||
                    risk === "CRITICAL"
                );

            }
        ).length;


    $("totalCrowd").textContent =
        totalCrowd.toLocaleString();


    $("avgOccupancy").textContent =
        `${avg.toFixed(1)}%`;


    $("highRisk").textContent =
        highRisk;


    $("activeZones").textContent =
        data.length;
}


// =====================================================
// RISK SUMMARY
// =====================================================

function renderRiskSummary(data) {

    const counts = {

        LOW: 0,

        MODERATE: 0,

        HIGH: 0,

        CRITICAL: 0

    };


    data.forEach(
        z => {

            const risk =
                String(
                    z.risk || "LOW"
                ).toUpperCase();


            if (
                counts[risk] !== undefined
            ) {

                counts[risk]++;

            }

        }
    );


    $("riskSummary").innerHTML =

        Object.entries(
            counts
        )

        .map(
            ([risk, count]) => `

                <div class="risk-row">

                    <div class="risk-left">

                        <span
                            class="risk-dot ${risk.toLowerCase()}"
                        ></span>


                        <span>

                            ${risk}

                        </span>

                    </div>


                    <span class="risk-count">

                        ${count}

                    </span>

                </div>

            `
        )

        .join("");
}


// =====================================================
// CHART
// =====================================================

function updateChart(data) {

    const canvas =
        $("crowdChart");


    if (
        !canvas ||
        typeof Chart === "undefined"
    ) {

        return;

    }


    const labels =
        data.map(
            z => z.name
        );


    const crowd =
        data.map(
            z =>
                Number(
                    z.crowd_count
                ) || 0
        );


    const capacity =
        data.map(
            z =>
                Number(
                    z.capacity
                ) || 0
        );


    if (crowdChart) {

        crowdChart.destroy();

    }


    crowdChart =
        new Chart(
            canvas,
            {

                type: "bar",


                data: {

                    labels,


                    datasets: [

                        {

                            label:
                                "Current Crowd",

                            data:
                                crowd,

                            backgroundColor:
                                "#1769e0",

                            borderRadius:
                                7,

                            borderSkipped:
                                false

                        },


                        {

                            label:
                                "Capacity",

                            data:
                                capacity,

                            backgroundColor:
                                "#c7ddf8",

                            borderRadius:
                                7,

                            borderSkipped:
                                false

                        }

                    ]

                },


                options: {

                    responsive:
                        true,


                    maintainAspectRatio:
                        false,


                    interaction: {

                        mode:
                            "index",

                        intersect:
                            false

                    },


                    plugins: {

                        legend: {

                            position:
                                "bottom",


                            labels: {

                                usePointStyle:
                                    true,

                                boxWidth:
                                    7,

                                font: {

                                    size:
                                        10

                                }

                            }

                        },


                        tooltip: {

                            backgroundColor:
                                "#071a33",

                            padding:
                                10,

                            titleFont: {

                                size:
                                    11

                            },

                            bodyFont: {

                                size:
                                    10

                            }

                        }

                    },


                    scales: {

                        y: {

                            beginAtZero:
                                true,


                            grid: {

                                color:
                                    "#edf2f7"

                            },


                            ticks: {

                                font: {

                                    size:
                                        9

                                },


                                color:
                                    "#718096"

                            }

                        },


                        x: {

                            grid: {

                                display:
                                    false

                            },


                            ticks: {

                                font: {

                                    size:
                                        9

                                },


                                color:
                                    "#718096"

                            }

                        }

                    }

                }

            }
        );
}


// =====================================================
// ZONE SELECT
// =====================================================

function populateZoneSelect(data) {

    const select =
        $("zoneSelect");


    const current =
        select.value;


    select.innerHTML =

        data.map(
            z => `

                <option value="${z.id}">

                    ${escapeHtml(
                        z.name
                    )}

                    — Capacity

                    ${Number(
                        z.capacity
                    ).toLocaleString()}

                </option>

            `
        )

        .join("");


    if (
        data.some(
            z =>
                String(z.id) ===
                current
        )
    ) {

        select.value =
            current;

    }
}


// =====================================================
// FORMAT TYPE
// =====================================================

function formatType(type) {

    const types = {

        ENTRANCE:
            "Entrance",

        QUEUE:
            "Queue",

        DARSHAN:
            "Darshan Area",

        PARKING:
            "Parking",

        EXIT:
            "Exit",

        OTHER:
            "Other"

    };


    return (
        types[type] ||
        "Other"
    );
}


// =====================================================
// LOAD TEMPLE
// =====================================================

async function loadTemple() {

    if (!TEMPLE_ID) {

        throw new Error(
            "Temple ID is missing from the dashboard URL."
        );

    }


    const response =
        await authFetch(
            `${API_URL}/api/temples/${TEMPLE_ID}`,
            {
                cache:
                    "no-store"
            }
        );


    const data =
        await response.json();


    if (!response.ok) {

        throw new Error(
            data.detail ||
            "Unable to load temple."
        );

    }


    $("dashboardTitle").textContent =
        `${data.name} Dashboard`;


    $("templeName").textContent =
        data.name;


    $("templeLocation").textContent =
        `${data.location} • Monitor crowd density, safety and pilgrimage zones in real time.`;
}


// =====================================================
// LOAD ZONES
// =====================================================

async function loadZones() {

    if (!TEMPLE_ID) {

        setApiStatus(false);


        $("zonesContainer").innerHTML = `

            <div class="loading-card">

                Temple ID is missing.

                Please open the dashboard
                through Zone Setup.

            </div>

        `;

        return;

    }


    try {

        const response =
            await authFetch(
                `${API_URL}/api/temples/${TEMPLE_ID}/zones`,
                {
                    cache:
                        "no-store"
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                `API returned ${response.status}`
            );

        }


        zones =
            Array.isArray(data)
                ? data
                : [];


        renderZones(
            zones
        );


        updateStatistics(
            zones
        );


        renderRiskSummary(
            zones
        );


        updateChart(
            zones
        );


        populateZoneSelect(
            zones
        );


        updateTime();


        setApiStatus(
            true
        );


    } catch (error) {

        console.error(
            "YatraSetu API:",
            error
        );


        setApiStatus(
            false
        );


        $("zonesContainer").innerHTML = `

            <div class="loading-card">

                ${escapeHtml(
                    error.message
                )}

            </div>

        `;

    }

}


// =====================================================
// LOAD DASHBOARD
// =====================================================

async function loadDashboard() {

    if (!TEMPLE_ID) {

        setApiStatus(false);


        $("zonesContainer").innerHTML = `

            <div class="loading-card">

                Temple ID is missing.

                Please open the dashboard
                from Zone Setup.

            </div>

        `;

        return;

    }


    try {

        await loadTemple();

        await loadZones();

    } catch (error) {

        console.error(
            "YatraSetu Dashboard:",
            error
        );


        setApiStatus(
            false
        );


        $("zonesContainer").innerHTML = `

            <div class="loading-card">

                ${escapeHtml(
                    error.message
                )}

            </div>

        `;

    }

}


// =====================================================
// UPDATE CROWD
// =====================================================

async function updateCrowd(event) {

    event.preventDefault();


    const zoneId =
        Number(
            $("zoneSelect").value
        );


    const peopleCount =
        Number(
            $("peopleCount").value
        );


    const button =
        event.submitter;


    if (
        !zoneId ||
        peopleCount < 0 ||
        !Number.isFinite(
            peopleCount
        )
    ) {

        showToast(
            "Enter valid crowd data."
        );

        return;

    }


    button.disabled =
        true;


    button.querySelector(
        "span:first-child"
    ).textContent =
        "Updating...";


    try {

        const params =
            new URLSearchParams({

                zone_id:
                    zoneId,

                people_count:
                    peopleCount

            });


        const response =
            await authFetch(
                `${API_URL}/api/crowd/update?${params.toString()}`,
                {
                    method:
                        "POST"
                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            throw new Error(
                result.detail ||
                result.error ||
                "Update failed"
            );

        }


        $("formMessage").textContent =
            `Updated successfully • ${
                result.zone ||
                "Zone"
            } • Risk: ${
                result.risk ||
                "LOW"
            }`;


        $("peopleCount").value =
            "";


        showToast(
            "Crowd data updated successfully."
        );


        await loadZones();


    } catch (error) {

        console.error(
            error
        );


        $("formMessage").textContent =
            error.message;


        showToast(
            "Could not update crowd data."
        );


    } finally {

        button.disabled =
            false;


        button.querySelector(
            "span:first-child"
        ).textContent =
            "Update Crowd";

    }

}


// =====================================================
// ESCAPE HTML
// =====================================================

function escapeHtml(value) {

    return String(
        value
    )

    .replaceAll(
        "&",
        "&amp;"
    )

    .replaceAll(
        "<",
        "&lt;"
    )

    .replaceAll(
        ">",
        "&gt;"
    )

    .replaceAll(
        '"',
        "&quot;"
    )

    .replaceAll(
        "'",
        "&#039;"
    );
}


// =====================================================
// EVENT LISTENERS
// =====================================================

$("crowdForm")
    .addEventListener(
        "submit",
        updateCrowd
    );


$("refreshBtn")
    .addEventListener(
        "click",
        () => {

            loadDashboard();


            showToast(
                "Dashboard refreshed."
            );

        }
    );


$("mobileMenu")
    .addEventListener(
        "click",
        () => {

            $("sidebar")
                .classList
                .toggle(
                    "open"
                );

        }
    );


document
    .querySelectorAll(
        ".nav-link"
    )
    .forEach(
        link => {

            link.addEventListener(
                "click",
                () => {

                    $("sidebar")
                        .classList
                        .remove(
                            "open"
                        );

                }
            );

        }
    );


// =====================================================
// START
// =====================================================

loadDashboard();


setInterval(
    loadDashboard,
    REFRESH_MS
);