(function () {
  function bySelector(selector, scope) {
    return Array.from((scope || document).querySelectorAll(selector));
  }

  function debounce(callback, delay) {
    let timer;
    return function debounced(...args) {
      clearTimeout(timer);
      timer = setTimeout(() => callback.apply(this, args), delay);
    };
  }

  function setLoadingState(enabled) {
    document.body.classList.toggle("is-loading", Boolean(enabled));
  }

  function setupThemeToggle() {
    const button = document.querySelector(".js-theme-toggle");
    if (!button) {
      return;
    }

    const storageKey = "wf_theme_mode";

    function applyTheme(mode) {
      const isStormTheme = mode === "storm";
      document.body.classList.toggle("storm-cloud-theme", isStormTheme);
      button.setAttribute("aria-pressed", isStormTheme ? "true" : "false");
      button.classList.toggle("is-storm", isStormTheme);
    }

    const savedMode = localStorage.getItem(storageKey) || "default";
    applyTheme(savedMode);

    button.addEventListener("click", () => {
      const nextMode = document.body.classList.contains("storm-cloud-theme") ? "default" : "storm";
      localStorage.setItem(storageKey, nextMode);
      applyTheme(nextMode);
    });
  }

  function setupAutocomplete(form) {
    const input = form.querySelector(".js-location-input");
    const list = form.querySelector(".js-suggestion-list");
    const latField = form.querySelector(".js-lat-field");
    const lonField = form.querySelector(".js-lon-field");

    if (!input || !list) {
      return;
    }

    function hideList() {
      list.classList.add("d-none");
      list.innerHTML = "";
    }

    const fetchSuggestions = debounce(async function fetchSuggestions() {
      const query = input.value.trim();
      if (query.length < 2) {
        hideList();
        return;
      }

      try {
        const response = await fetch(`/autocomplete/?q=${encodeURIComponent(query)}`);
        const payload = await response.json();
        const results = Array.isArray(payload.results) ? payload.results : [];

        if (!results.length) {
          hideList();
          return;
        }

        list.innerHTML = "";
        results.forEach((item) => {
          const li = document.createElement("li");
          const button = document.createElement("button");
          button.type = "button";
          button.className = "suggestion-item";
          button.textContent = item.label;
          button.dataset.label = item.label;
          button.dataset.lat = item.lat;
          button.dataset.lon = item.lon;

          button.addEventListener("click", function onSelect() {
            input.value = this.dataset.label || "";
            if (latField && lonField) {
              latField.value = this.dataset.lat || "";
              lonField.value = this.dataset.lon || "";
            }
            hideList();
          });

          li.appendChild(button);
          list.appendChild(li);
        });

        list.classList.remove("d-none");
      } catch (error) {
        hideList();
      }
    }, 280);

    input.addEventListener("input", function onInput() {
      if (latField && lonField) {
        latField.value = "";
        lonField.value = "";
      }
      fetchSuggestions();
    });

    document.addEventListener("click", (event) => {
      if (!form.contains(event.target)) {
        hideList();
      }
    });
  }

  function resetLocationButton(button) {
    if (!button) {
      return;
    }
    button.disabled = false;
    button.textContent = "Use my location";
  }

  function resetAllLocationButtons() {
    bySelector(".js-location-btn").forEach((button) => resetLocationButton(button));
  }

  function resetUseLocationFlags() {
    bySelector(".js-use-location").forEach((field) => {
      field.value = "0";
    });
  }

  function setupGeolocation(form) {
    const button = form.querySelector(".js-location-btn");
    const latField = form.querySelector(".js-lat-field");
    const lonField = form.querySelector(".js-lon-field");
    const useLocationField = form.querySelector(".js-use-location");

    if (!button || !latField || !lonField) {
      return;
    }

    button.addEventListener("click", async () => {
      if (!navigator.geolocation) {
        alert("Geolocation is not supported in this browser.");
        return;
      }

      button.disabled = true;
      button.textContent = "Locating...";
      if (useLocationField) {
        useLocationField.value = "1";
      }

      navigator.geolocation.getCurrentPosition(
        (position) => {
          latField.value = position.coords.latitude.toString();
          lonField.value = position.coords.longitude.toString();
          resetLocationButton(button);
          form.requestSubmit();
        },
        () => {
          if (useLocationField) {
            useLocationField.value = "0";
          }
          resetLocationButton(button);
          alert("Could not get your location. Please allow location access and try again.");
        },
        { timeout: 10000 }
      );
    });
  }

  function setupFormState(form) {
    const queryInput = form.querySelector(".js-location-input");
    const useLocationField = form.querySelector(".js-use-location");

    // Keep submit interactions always responsive; avoid sticky loading state on browser back.
    const clear = () => setLoadingState(false);
    form.addEventListener("submit", (event) => {
      const wantsLocation = useLocationField ? useLocationField.value === "1" : false;
      const query = queryInput ? queryInput.value.trim() : "";

      if (!wantsLocation && !query) {
        event.preventDefault();
        clear();
        if (queryInput) {
          queryInput.setCustomValidity("Type place");
          queryInput.reportValidity();
        }
        return;
      }

      if (queryInput) {
        queryInput.setCustomValidity("");
      }

      clear();
    });
    form.addEventListener("input", () => {
      if (queryInput) {
        queryInput.setCustomValidity("");
      }
      if (useLocationField) {
        useLocationField.value = "0";
      }
      clear();
    });
    form.addEventListener("change", clear);
    form.addEventListener("click", clear);
  }

  function setupFeatureIdeas() {
    const wrappers = bySelector(".js-feature-ideas");
    wrappers.forEach((wrapper) => {
      const cards = bySelector(".feature-idea-card", wrapper);
      const panelRoot = wrapper.closest(".mini-stats");
      if (!cards.length || !panelRoot) {
        return;
      }

      const output = panelRoot.querySelector(".js-feature-output");
      const compareInput = panelRoot.querySelector(".js-compare-city");
      const contextHeading = panelRoot.querySelector(".js-feature-context");
      const todayTemp = panelRoot.querySelector(".js-feature-today");
      const homeForm = document.querySelector(".js-search-form");
      const queryInput = homeForm ? homeForm.querySelector(".js-location-input") : null;
      const latField = homeForm ? homeForm.querySelector(".js-lat-field") : null;
      const lonField = homeForm ? homeForm.querySelector(".js-lon-field") : null;
      const unitSelect = homeForm ? homeForm.querySelector(".unit-select") : null;

      function updateCompareVisibility(featureKey) {
        if (!compareInput) {
          return;
        }
        compareInput.classList.toggle("d-none", featureKey !== "city-compare");
      }

      function setContextText(lat, lon, cityLabel) {
        if (!contextHeading) {
          return;
        }

        if (lat && lon) {
          if (cityLabel) {
            contextHeading.textContent = `Insights are currently using your current location (${cityLabel}).`;
          } else {
            contextHeading.textContent = "Insights are currently using your current location.";
          }
          return;
        }

        contextHeading.textContent = "Allow location access to use home insights.";
      }

      if (!output) {
        return;
      }

      function setActiveCard(activeCard) {
        cards.forEach((card) => card.classList.toggle("is-active", card === activeCard));
      }

      function renderTodayCard(value, meta) {
        if (!todayTemp) {
          return;
        }
        todayTemp.innerHTML =
          `<span class="feature-temp-label">Today's temperature</span>` +
          `<span class="feature-temp-value">${value}</span>` +
          `<span class="feature-temp-meta">${meta}</span>`;
      }

      function renderCachedSummary() {
        const raw = localStorage.getItem("wf_home_summary");
        if (!raw) {
          return false;
        }

        try {
          const payload = JSON.parse(raw);
          const ageMs = Date.now() - Number(payload.at || 0);
          if (!payload.data || ageMs > 15 * 60 * 1000) {
            return false;
          }

          const item = payload.data;
          const cityLabel = item.country ? `${item.city}, ${item.country}` : item.city;
          renderTodayCard(`${item.temperature}°${item.unit_symbol}`, `${item.description} in ${cityLabel}`);
          setContextText("1", "1", cityLabel);
          return true;
        } catch (error) {
          return false;
        }
      }

      async function loadCurrentSummary(lat, lon, displayAreaLabel) {
        if (!todayTemp) {
          return;
        }

        try {
          const params = new URLSearchParams();
          params.set("lat", lat);
          params.set("lon", lon);
          params.set("unit", unitSelect ? unitSelect.value : "celsius");
          const response = await fetch(`/current-summary/?${params.toString()}`);
          const payload = await response.json();

          if (!response.ok) {
            throw new Error(payload.error || "Unable to load current temperature.");
          }

          const cityLabel = payload.country ? `${payload.city}, ${payload.country}` : payload.city;
          const shownArea = displayAreaLabel || cityLabel;
          renderTodayCard(
            `${payload.temperature}°${payload.unit_symbol}`,
            `${payload.description} in ${shownArea}`
          );
          localStorage.setItem(
            "wf_home_summary",
            JSON.stringify({
              at: Date.now(),
              data: {
                city: payload.city,
                country: payload.country,
                temperature: payload.temperature,
                unit_symbol: payload.unit_symbol,
                description: payload.description,
              },
            })
          );
          localStorage.setItem(
            "wf_last_coords",
            JSON.stringify({
              at: Date.now(),
              lat,
              lon,
            })
          );
          setContextText(lat, lon, shownArea);
        } catch (error) {
          renderTodayCard("--", error.message || "Unable to load current temperature.");
          setContextText("", "", "");
        }
      }

      function requestCurrentLocation(showLoadingState) {
        if (!latField || !lonField) {
          return;
        }

        if (!navigator.geolocation) {
          renderTodayCard("--", "Geolocation is not supported in this browser.");
          setContextText("", "", "");
          return;
        }

        const savedCoordsRaw = localStorage.getItem("wf_last_coords");
        if (savedCoordsRaw) {
          try {
            const saved = JSON.parse(savedCoordsRaw);
            const isFresh = Date.now() - Number(saved.at || 0) < 24 * 60 * 60 * 1000;
            if (isFresh && saved.lat && saved.lon) {
              latField.value = String(saved.lat);
              lonField.value = String(saved.lon);
              loadCurrentSummary(String(saved.lat), String(saved.lon), "");
            }
          } catch (error) {
            // Ignore cached coordinate parsing issues.
          }
        }

        if (showLoadingState) {
          renderTodayCard("--", "Detecting current location...");
        }

        navigator.geolocation.getCurrentPosition(
          async (position) => {
            const lat = position.coords.latitude.toString();
            const lon = position.coords.longitude.toString();
            latField.value = lat;
            lonField.value = lon;
            loadCurrentSummary(lat, lon, "");
          },
          () => {
            renderTodayCard("--", "Location access denied. Enable location to use home insights.");
            setContextText("", "", "");
          },
          {
            timeout: 7000,
            maximumAge: 300000,
            enableHighAccuracy: false,
          }
        );
      }

      async function runFeature(featureKey) {
        const query = queryInput ? queryInput.value.trim() : "";
        const lat = latField ? latField.value.trim() : "";
        const lon = lonField ? lonField.value.trim() : "";

        if (!(lat && lon)) {
          output.textContent = "Current location is required on home page. Enable location access first.";
          return;
        }

        const compareCity = compareInput ? compareInput.value.trim() : "";
        if (featureKey === "city-compare" && !compareCity) {
          output.textContent = "Enter a second city to run City Weather Compare.";
          return;
        }

        output.textContent = "Loading insight...";

        try {
          const params = new URLSearchParams();
          if (query) {
            params.set("q", query);
          }
          if (lat && lon) {
            params.set("lat", lat);
            params.set("lon", lon);
          }
          if (compareCity) {
            params.set("compare", compareCity);
          }

          const response = await fetch(`/insights/?${params.toString()}`);
          const payload = await response.json();
          if (!response.ok) {
            throw new Error(payload.error || "Unable to generate insights right now.");
          }

          const result = payload.results ? payload.results[featureKey] : null;
          if (!result) {
            throw new Error("Feature response is missing.");
          }

          output.innerHTML = `<strong>${result.title}</strong><br>${result.body}`;
        } catch (error) {
          output.textContent = error.message || "Unable to run this feature right now.";
        }
      }

      cards.forEach((card) => {
        const featureKey = card.dataset.feature;
        const mainButton = card.querySelector(".feature-main-btn");
        const arrowButton = card.querySelector(".js-feature-arrow");

        if (mainButton) {
          mainButton.addEventListener("click", () => {
            setActiveCard(card);
            updateCompareVisibility(featureKey);
            runFeature(featureKey);
          });
        }

        if (arrowButton) {
          arrowButton.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            card.classList.toggle("desc-open");
          });
        }
      });

      if (compareInput) {
        compareInput.addEventListener("keydown", (event) => {
          if (event.key !== "Enter") {
            return;
          }
          event.preventDefault();
          const activeCard = cards.find((card) => card.classList.contains("is-active"));
          if (activeCard && activeCard.dataset.feature === "city-compare") {
            runFeature("city-compare");
          }
        });
      }

      const activeCard = cards.find((card) => card.classList.contains("is-active")) || cards[0];
      if (activeCard) {
        updateCompareVisibility(activeCard.dataset.feature);
      }

      const hasCachedSummary = renderCachedSummary();
      requestCurrentLocation(!hasCachedSummary);
    });
  }

  function drawTempTrend() {
    const svg = document.getElementById("temp-trend-chart");
    const labelsNode = document.getElementById("trend-labels");
    const highsNode = document.getElementById("trend-highs");
    const lowsNode = document.getElementById("trend-lows");

    if (!svg || !labelsNode || !highsNode || !lowsNode) {
      return;
    }

    const labels = JSON.parse(labelsNode.textContent || "[]");
    const highs = JSON.parse(highsNode.textContent || "[]");
    const lows = JSON.parse(lowsNode.textContent || "[]");

    if (!labels.length || !highs.length || !lows.length) {
      return;
    }

    const width = 680;
    const height = 190;
    const padX = 28;
    const padTop = 22;
    const padBottom = 34;

    const maxTemp = Math.max(...highs, ...lows);
    const minTemp = Math.min(...highs, ...lows);
    const range = Math.max(1, maxTemp - minTemp);

    const xStep = (width - padX * 2) / Math.max(1, labels.length - 1);
    const scaleY = (temp) => {
      const normalized = (temp - minTemp) / range;
      return height - padBottom - normalized * (height - padTop - padBottom);
    };

    function makePath(values) {
      return values
        .map((temp, idx) => {
          const x = padX + idx * xStep;
          const y = scaleY(temp);
          return `${idx === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
        })
        .join(" ");
    }

    const highPath = makePath(highs);
    const lowPath = makePath(lows);

    svg.innerHTML = `
      <path d="${lowPath}" fill="none" stroke="rgba(183,225,255,0.9)" stroke-width="2.5" stroke-linecap="round" />
      <path d="${highPath}" fill="none" stroke="rgba(255,255,255,0.95)" stroke-width="3.5" stroke-linecap="round" />
    `;

    labels.forEach((label, idx) => {
      const x = padX + idx * xStep;
      const y = height - 10;
      const pointY = scaleY(highs[idx]);

      const point = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      point.setAttribute("cx", x.toFixed(1));
      point.setAttribute("cy", pointY.toFixed(1));
      point.setAttribute("r", "4");
      point.setAttribute("fill", "#ffffff");
      svg.appendChild(point);

      const tempText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      tempText.setAttribute("x", x.toFixed(1));
      tempText.setAttribute("y", (pointY - 9).toFixed(1));
      tempText.setAttribute("text-anchor", "middle");
      tempText.setAttribute("fill", "#eef9ff");
      tempText.setAttribute("font-size", "10");
      tempText.textContent = `${highs[idx]}°`;
      svg.appendChild(tempText);

      const labelText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      labelText.setAttribute("x", x.toFixed(1));
      labelText.setAttribute("y", y.toFixed(1));
      labelText.setAttribute("text-anchor", "middle");
      labelText.setAttribute("fill", "rgba(238,249,255,0.85)");
      labelText.setAttribute("font-size", "10");
      labelText.textContent = label;
      svg.appendChild(labelText);
    });
  }

  setupThemeToggle();
  setLoadingState(false);
  resetAllLocationButtons();
  resetUseLocationFlags();
  window.addEventListener("pageshow", () => {
    setLoadingState(false);
    resetAllLocationButtons();
    resetUseLocationFlags();
  });
  window.addEventListener("focus", () => {
    setLoadingState(false);
    resetUseLocationFlags();
  });

  bySelector(".js-search-form").forEach((form) => {
    setupAutocomplete(form);
    setupGeolocation(form);
    setupFormState(form);
  });

  setupFeatureIdeas();
  drawTempTrend();
})();
