/**
 * app.js - WeatherGPT Client Application Logic (Phase 1 Web MVP)
 * 
 * Modular Vanilla ES6 implementation handling:
 * - Real-time atmospheric chat interaction
 * - Location management (predefined hubs, Open-Meteo geocoding, browser GPS)
 * - Interactive telemetry cards (current metrics + 7-day forecast)
 * - Session persistence and ChatGPT-style interface states
 */

// ============================================================================
// 1. CONFIGURATION & STATE MANAGEMENT
// ============================================================================

const CONFIG = {
  API_BASE: "/api",
  DEFAULT_LOCATION: {
    name: "Chennai",
    country: "IN",
    admin1: "Tamil Nadu",
    latitude: 13.0827,
    longitude: 80.2707,
    display_name: "Chennai, Tamil Nadu, India"
  },
  WEATHER_ICONS: {
    "clear": "☀️",
    "mainly clear": "🌤️",
    "partly cloudy": "⛅",
    "overcast": "☁️",
    "foggy": "🌫️",
    "depositing rime fog": "🌫️",
    "light drizzle": "🌦️",
    "moderate drizzle": "🌦️",
    "dense drizzle": "🌧️",
    "slight rain": "🌧️",
    "moderate rain": "🌧️",
    "heavy rain": "⛈️",
    "thunderstorm": "⛈️",
    "thunderstorm with slight hail": "⛈️",
    "thunderstorm with heavy hail": "⛈️",
    "slight snowfall": "🌨️",
    "moderate snowfall": "❄️",
    "heavy snowfall": "❄️",
    "snow grains": "🌨️"
  }
};

const AppState = {
  activeLocation: { ...CONFIG.DEFAULT_LOCATION },
  currentChatId: null,
  currentMessages: [],
  chatHistory: [],
  isWaitingForResponse: false,
  suggestedHubs: []
};

// ============================================================================
// 2. API CLIENT SERVICE
// ============================================================================

const ApiClient = {
  async fetchHealth() {
    try {
      const res = await fetch(`${CONFIG.API_BASE}/health`);
      return await res.json();
    } catch (e) {
      console.warn("Health check failed:", e);
      return null;
    }
  },

  async geocodeQuery(query) {
    if (!query || !query.trim()) return [];
    try {
      const res = await fetch(`${CONFIG.API_BASE}/geocode?query=${encodeURIComponent(query.trim())}&limit=6`);
      if (!res.ok) throw new Error("Geocoding failed");
      return await res.json();
    } catch (e) {
      console.error("Geocode error:", e);
      return [];
    }
  },

  async reverseGeocode(lat, lon) {
    try {
      const res = await fetch(`${CONFIG.API_BASE}/reverse-geocode?latitude=${lat}&longitude=${lon}`);
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      console.warn("Reverse geocode error:", e);
      return null;
    }
  },

  async fetchWeather(lat, lon, name = "") {
    try {
      const url = `${CONFIG.API_BASE}/weather?latitude=${lat}&longitude=${lon}&name=${encodeURIComponent(name)}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Weather error: ${res.statusText}`);
      return await res.json();
    } catch (e) {
      console.error("Fetch weather error:", e);
      throw e;
    }
  },

  async sendChatMessage(message, location) {
    try {
      const res = await fetch(`${CONFIG.API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          location,
          session_id: AppState.currentChatId
        })
      });
      if (!res.ok) throw new Error(`Chat API error: ${res.statusText}`);
      return await res.json();
    } catch (e) {
      console.error("Chat request failed:", e);
      throw e;
    }
  }
};

// ============================================================================
// 3. UI HELPER & RENDER FUNCTIONS
// ============================================================================

function getWeatherEmoji(condition = "") {
  const lower = condition.toLowerCase();
  for (const [key, emoji] of Object.entries(CONFIG.WEATHER_ICONS)) {
    if (lower.includes(key)) return emoji;
  }
  if (lower.includes("rain") || lower.includes("drizzle")) return "🌧️";
  if (lower.includes("snow") || lower.includes("ice")) return "❄️";
  if (lower.includes("thunder") || lower.includes("storm")) return "⛈️";
  if (lower.includes("cloud")) return "⛅";
  return "🌤️";
}

function formatMarkdown(text = "") {
  // Safe simple markdown formatting for bold, bullets, code, links
  let formatted = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");

  return formatted;
}

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(20px)";
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

// ============================================================================
// 4. CHAT & MESSAGE MANAGEMENT
// ============================================================================

function createChatSession() {
  const newId = "chat_" + Date.now();
  AppState.currentChatId = newId;
  AppState.currentMessages = [];
  
  const chatMessages = document.getElementById("chatMessages");
  const welcomeScreen = document.getElementById("welcomeScreen");
  
  if (chatMessages) chatMessages.innerHTML = "";
  if (welcomeScreen) welcomeScreen.classList.remove("hidden");

  saveSessionsToStorage();
  renderHistoryList();
}

function appendUserMessage(text) {
  const chatMessages = document.getElementById("chatMessages");
  const welcomeScreen = document.getElementById("welcomeScreen");
  if (welcomeScreen) welcomeScreen.classList.add("hidden");

  const row = document.createElement("div");
  row.className = "message-row user";
  row.innerHTML = `
    <div class="message-bubble">
      <div>${formatMarkdown(text)}</div>
    </div>
  `;
  chatMessages.appendChild(row);
  scrollToBottom();

  AppState.currentMessages.push({ role: "user", text, timestamp: new Date().toISOString() });
  saveCurrentSession();
}

function appendBotMessage(replyText, weatherReport = null, cardType = null, verification = null, intent = null) {
  const chatMessages = document.getElementById("chatMessages");
  const welcomeScreen = document.getElementById("welcomeScreen");
  if (welcomeScreen) welcomeScreen.classList.add("hidden");

  const row = document.createElement("div");
  row.className = "message-row bot";

  let weatherCardHtml = "";
  // Only render the weather telemetry card when explicitly requested by the backend
  if (weatherReport && weatherReport.current && (cardType === "forecast" || cardType === "overview")) {
    weatherCardHtml = buildWeatherCardHtml(weatherReport);
  }

  // Show a credibility indicator on EVERY weather-related answer.
  // A dedicated explanation card is used only when the user asks about confidence.
  const verificationHtml = verification
    ? (intent === "forecast_confidence"
        ? buildVerificationCardHtml(verification)
        : buildVerificationBadgeHtml(verification))
    : "";

  row.innerHTML = `
    <div class="bot-avatar" title="WeatherGPT">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>
      </svg>
    </div>
    <div class="message-bubble">
      <div class="bot-text">${formatMarkdown(replyText)}</div>
      ${weatherCardHtml}
      ${verificationHtml}
    </div>
  `;

  chatMessages.appendChild(row);
  scrollToBottom();

  AppState.currentMessages.push({
    role: "bot",
    text: replyText,
    weather: weatherReport,
    verification: verification,
    timestamp: new Date().toISOString()
  });
  saveCurrentSession();
}

function buildVerificationBadgeHtml(verification) {
  const level = verification.level || "UNVERIFIED";
  const icon = level === "HIGH" ? "🟢" : (level === "MEDIUM" ? "🟡" : (level === "LOW" ? "🔴" : "⚪"));
  const modeLabel = verification.mode === "forecast" ? "Forecast confidence" : "Data confidence";
  const agreement = (verification.agreement_total > 0)
    ? `${verification.agreement_count}/${verification.agreement_total} signals agree`
    : "not cross-checked";
  const sources = (verification.sources || []).join(" + ");
  const label = level === "UNVERIFIED" ? "Verification unavailable" : `${modeLabel}: ${level}`;

  return `
    <div class="verification-badge" title="Confidence is based on agreement between available weather providers, not historical forecast accuracy.">
      <span class="verification-badge-icon">${icon}</span>
      <span><strong>${label}</strong> · ${agreement}</span>
      ${sources ? `<span class="verification-badge-sources">· ${sources}</span>` : ""}
    </div>
  `;
}

function buildVerificationCardHtml(verification) {
  const level = verification.level || "UNVERIFIED";
  const icon = level === "HIGH" ? "🟢" : (level === "MEDIUM" ? "🟡" : (level === "LOW" ? "🔴" : "⚪"));
  const title = level === "UNVERIFIED" ? "Verification unavailable" : `Forecast confidence: ${level}`;
  const sources = (verification.sources || []).join(" + ");
  const reasons = (verification.reasons || []).slice(0, 3);

  return `
    <div class="verification-card">
      <div class="verification-header">
        <div>
          <div class="verification-title">${icon} ${title}</div>
          <div class="verification-subtitle">${verification.summary || "No cross-provider comparison available."}</div>
        </div>
        <span class="verification-sources">${sources || "Primary source only"}</span>
      </div>
      ${reasons.length ? `
        <div class="verification-reasons">
          ${reasons.map(reason => `<div class="verification-reason">✓ ${reason}</div>`).join("")}
        </div>
      ` : ""}
      <div class="verification-note">
        Confidence is based on source agreement for this request — it is not a historical accuracy percentage.
        Ask <strong>"Why this confidence?"</strong> for an explanation.
      </div>
    </div>
  `;
}

function buildWeatherCardHtml(report) {
  const cur = report.current;
  const loc = report.location;
  const forecast = report.forecast || [];
  const icon = getWeatherEmoji(cur.condition);

  // Region label
  const regionParts = [loc.admin1, loc.country].filter(Boolean);
  const regionLabel = regionParts.length ? regionParts.join(", ") : "Real-Time Telemetry";

  // Precipitation probability string
  const precipProb = cur.precipitation_probability ? `${cur.precipitation_probability}%` : "0%";

  // 7-day forecast cards
  let forecastCardsHtml = "";
  forecast.slice(0, 7).forEach((dayItem, index) => {
    const dayLabel = index === 0 ? "Today" : dayItem.day.split(",")[0];
    const dayIcon = getWeatherEmoji(dayItem.condition);
    const rainProb = dayItem.precipitation_probability_max > 0 ? `💧 ${dayItem.precipitation_probability_max}%` : "";

    forecastCardsHtml += `
      <div class="wc-forecast-day-card">
        <span class="wc-fc-day">${dayLabel}</span>
        <span class="wc-fc-icon">${dayIcon}</span>
        <div class="wc-fc-temps">
          <span class="wc-fc-high">${dayItem.temp_max}°</span>
          <span class="wc-fc-low">${dayItem.temp_min}°</span>
        </div>
        ${rainProb ? `<span class="wc-fc-rain">${rainProb}</span>` : ""}
      </div>
    `;
  });

  return `
    <div class="weather-card-container">
      <div class="wc-header">
        <div class="wc-loc-info">
          <span class="wc-city">📍 ${loc.name}</span>
          <span class="wc-region">${regionLabel}</span>
        </div>
        <span class="wc-condition-tag">${icon} ${cur.condition}</span>
      </div>

      <div class="wc-current-row">
        <div class="wc-temp-block">
          <span class="wc-temp-value">${cur.temperature}°C</span>
          <span class="wc-feels-like">Feels like ${cur.feels_like}°C</span>
        </div>
        <span class="wc-weather-icon">${icon}</span>
      </div>

      <div class="wc-metrics-grid">
        <div class="wc-metric-tile">
          <span class="wc-metric-label">Humidity</span>
          <span class="wc-metric-val">${cur.humidity}%</span>
        </div>
        <div class="wc-metric-tile">
          <span class="wc-metric-label">Wind</span>
          <span class="wc-metric-val">${cur.wind_speed} km/h ${cur.wind_direction_compass}</span>
        </div>
        <div class="wc-metric-tile">
          <span class="wc-metric-label">Precipitation</span>
          <span class="wc-metric-val">${cur.precipitation} mm (${precipProb})</span>
        </div>
        <div class="wc-metric-tile">
          <span class="wc-metric-label">Sunrise</span>
          <span class="wc-metric-val">${cur.sunrise || "--"}</span>
        </div>
        <div class="wc-metric-tile">
          <span class="wc-metric-label">Sunset</span>
          <span class="wc-metric-val">${cur.sunset || "--"}</span>
        </div>
        <div class="wc-metric-tile">
          <span class="wc-metric-label">Atmosphere</span>
          <span class="wc-metric-val">${cur.is_raining ? "Rain Active ☔" : "No Rain"}</span>
        </div>
      </div>

      ${forecast.length > 0 ? `
        <div class="wc-forecast-section">
          <div class="wc-forecast-title">7-Day Forecast Outlook</div>
          <div class="wc-forecast-grid">
            ${forecastCardsHtml}
          </div>
        </div>
      ` : ""}
    </div>
  `;
}

function setTyping(isTyping) {
  AppState.isWaitingForResponse = isTyping;
  const indicator = document.getElementById("typingIndicator");
  const sendBtn = document.getElementById("sendBtn");
  const input = document.getElementById("chatInput");

  if (indicator) {
    indicator.classList.toggle("hidden", !isTyping);
  }
  if (sendBtn) {
    sendBtn.disabled = isTyping || !input.value.trim();
  }
  if (isTyping) {
    scrollToBottom();
  }
}

function scrollToBottom() {
  const container = document.getElementById("chatContainer");
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

async function handleSendMessage(messageText) {
  const cleanMsg = (messageText || "").trim();
  if (!cleanMsg || AppState.isWaitingForResponse) return;

  const input = document.getElementById("chatInput");
  if (input) {
    input.value = "";
    input.style.height = "auto";
  }

  // Display user message in UI
  appendUserMessage(cleanMsg);
  setTyping(true);

  try {
    const response = await ApiClient.sendChatMessage(cleanMsg, AppState.activeLocation);

    // If query was resolved for a new city or location changed, update active location
    if (response.location && (
      response.location.name.toLowerCase() !== AppState.activeLocation.name.toLowerCase() ||
      Math.abs(response.location.latitude - AppState.activeLocation.latitude) > 0.1
    )) {
      updateActiveLocation(response.location, false);
    }

    appendBotMessage(response.reply, response.weather_data, response.card_type || null, response.verification || null, response.intent || null);

    // Update header pill only when a weather card is being shown (overview or forecast)
    if (response.weather_data && response.weather_data.current) {
      updateLocationPillDisplay(response.weather_data.location, response.weather_data.current);
    } else if (response.location) {
      // Still update location context even without a full card (e.g. "Will it rain in London?")
      const nameEl = document.getElementById("currentLocationName");
      if (nameEl && response.location.name !== AppState.activeLocation.name) {
        // Do not update the pill display without fresh telemetry data
      }
    }
  } catch (err) {
    console.error("Chat error:", err);
    appendBotMessage(`⚠️ **Connection Error:** Could not reach the WeatherGPT backend (${err.message}). Please check if the server is running.`);
    showToast("Failed to retrieve weather response", "error");
  } finally {
    setTyping(false);
  }
}

// ============================================================================
// 5. LOCATION MANAGEMENT & TELEMETRY
// ============================================================================

async function updateActiveLocation(location, fetchWeatherNow = true) {
  AppState.activeLocation = { ...location };

  // Update Top Nav display
  const nameEl = document.getElementById("currentLocationName");
  const metricsEl = document.getElementById("currentLocationMetrics");
  if (nameEl) nameEl.textContent = `${location.name}, ${location.country || "IN"}`;
  if (metricsEl) metricsEl.textContent = "Updating...";

  if (fetchWeatherNow) {
    try {
      const data = await ApiClient.fetchWeather(location.latitude, location.longitude, location.name);
      if (data && data.current) {
        updateLocationPillDisplay(location, data.current);
      }
      showToast(`Location set to ${location.name}`, "success");
    } catch (e) {
      console.warn("Could not fetch weather telemetry for new location:", e);
      if (metricsEl) metricsEl.textContent = "Offline";
    }
  }
}

function updateLocationPillDisplay(location, current) {
  const metricsEl = document.getElementById("currentLocationMetrics");
  if (metricsEl) {
    metricsEl.textContent = `${current.temperature}°C · ${current.condition}`;
  }
}

// Geolocation Handling
function requestBrowserLocation() {
  const statusEl = document.getElementById("geoStatus");
  if (!navigator.geolocation) {
    if (statusEl) statusEl.textContent = "Unsupported";
    showToast("Geolocation is not supported by your browser.", "error");
    return;
  }

  if (statusEl) statusEl.textContent = "Locating...";

  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      if (statusEl) statusEl.textContent = "Found!";

      try {
        const resolved = await ApiClient.reverseGeocode(lat, lon);
        const locObj = resolved || {
          name: "My Location",
          country: "",
          latitude: roundTo(lat, 4),
          longitude: roundTo(lon, 4),
          display_name: `${roundTo(lat, 2)}°, ${roundTo(lon, 2)}°`
        };
        const report = await ApiClient.fetchWeather(lat, lon, locObj.name);
        await updateActiveLocation(locObj, false);
        updateLocationPillDisplay(locObj, report.current);
        closeLocationModal();
        showToast("Switched to your current GPS coordinates", "success");
      } catch (e) {
        showToast("Error retrieving weather for your coordinates", "error");
      } finally {
        if (statusEl) statusEl.textContent = "";
      }
    },
    (err) => {
      console.warn("Geolocation denied or failed:", err);
      if (statusEl) statusEl.textContent = "Permission denied";
      showToast("Location access was denied or timed out.", "error");
      setTimeout(() => { if (statusEl) statusEl.textContent = ""; }, 2500);
    },
    { timeout: 10000, enableHighAccuracy: true }
  );
}

function roundTo(num, dec) {
  const factor = Math.pow(10, dec);
  return Math.round(num * factor) / factor;
}

// Modal Search Logic
let searchDebounceTimer = null;

function setupSearchInput() {
  const searchInput = document.getElementById("citySearchInput");
  const clearBtn = document.getElementById("clearSearchBtn");
  const resultsContainer = document.getElementById("searchResultsList");

  if (!searchInput) return;

  searchInput.addEventListener("input", (e) => {
    const val = e.target.value.trim();
    if (clearBtn) clearBtn.classList.toggle("hidden", !val);

    clearTimeout(searchDebounceTimer);
    if (!val) {
      if (resultsContainer) {
        resultsContainer.classList.add("hidden");
        resultsContainer.innerHTML = "";
      }
      return;
    }

    searchDebounceTimer = setTimeout(async () => {
      if (resultsContainer) {
        resultsContainer.classList.remove("hidden");
        resultsContainer.innerHTML = `<div class="search-result-item"><span class="sr-name">Searching locations...</span></div>`;
      }

      const results = await ApiClient.geocodeQuery(val);
      renderSearchResults(results);
    }, 280);
  });

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      searchInput.value = "";
      clearBtn.classList.add("hidden");
      if (resultsContainer) {
        resultsContainer.classList.add("hidden");
        resultsContainer.innerHTML = "";
      }
      searchInput.focus();
    });
  }
}

function renderSearchResults(results) {
  const container = document.getElementById("searchResultsList");
  if (!container) return;

  if (!results || results.length === 0) {
    container.innerHTML = `<div class="search-result-item"><span class="sr-detail">No matching cities found. Try another spelling.</span></div>`;
    return;
  }

  container.innerHTML = "";
  results.forEach(loc => {
    const item = document.createElement("button");
    item.className = "search-result-item";
    item.innerHTML = `
      <span class="sr-name">${loc.name}</span>
      <span class="sr-detail">${loc.display_name || `${loc.latitude}, ${loc.longitude}`}</span>
    `;
    item.addEventListener("click", () => {
      updateActiveLocation(loc, true);
      closeLocationModal();
    });
    container.appendChild(item);
  });
}

function openLocationModal() {
  const modal = document.getElementById("locationModal");
  if (modal) {
    modal.classList.remove("hidden");
    const input = document.getElementById("citySearchInput");
    if (input) {
      input.value = "";
      input.focus();
    }
  }
}

function closeLocationModal() {
  const modal = document.getElementById("locationModal");
  if (modal) modal.classList.add("hidden");
}

// ============================================================================
// 6. SESSION STORAGE & PERSISTENCE
// ============================================================================

function saveCurrentSession() {
  if (!AppState.currentChatId) return;

  const firstMsg = AppState.currentMessages.find(m => m.role === "user");
  const title = firstMsg ? firstMsg.text.slice(0, 32) : "Weather Session";

  const sessionObj = {
    id: AppState.currentChatId,
    title,
    location: AppState.activeLocation,
    messages: AppState.currentMessages,
    updatedAt: new Date().toISOString()
  };

  const existingIdx = AppState.chatHistory.findIndex(h => h.id === AppState.currentChatId);
  if (existingIdx >= 0) {
    AppState.chatHistory[existingIdx] = sessionObj;
  } else {
    AppState.chatHistory.unshift(sessionObj);
  }

  saveSessionsToStorage();
  renderHistoryList();
}

function saveSessionsToStorage() {
  try {
    localStorage.setItem("weathergpt_sessions", JSON.stringify(AppState.chatHistory.slice(0, 20)));
  } catch (e) {
    console.warn("Could not write to localStorage:", e);
  }
}

function loadSessionsFromStorage() {
  try {
    const stored = localStorage.getItem("weathergpt_sessions");
    if (stored) {
      AppState.chatHistory = JSON.parse(stored);
      renderHistoryList();
    }
  } catch (e) {
    AppState.chatHistory = [];
  }
}

function renderHistoryList() {
  const list = document.getElementById("historyList");
  if (!list) return;

  if (AppState.chatHistory.length === 0) {
    list.innerHTML = `<div class="history-empty">No saved chats yet</div>`;
    return;
  }

  list.innerHTML = "";
  AppState.chatHistory.forEach(sess => {
    const item = document.createElement("button");
    item.className = `history-item ${sess.id === AppState.currentChatId ? "active" : ""}`;
    item.title = sess.title;
    item.textContent = sess.title;
    item.addEventListener("click", () => restoreChatSession(sess.id));
    list.appendChild(item);
  });
}

function restoreChatSession(sessionId) {
  const sess = AppState.chatHistory.find(s => s.id === sessionId);
  if (!sess) return;

  AppState.currentChatId = sess.id;
  AppState.currentMessages = sess.messages || [];
  if (sess.location) {
    updateActiveLocation(sess.location, false);
  }

  const chatMessages = document.getElementById("chatMessages");
  const welcomeScreen = document.getElementById("welcomeScreen");

  if (welcomeScreen) {
    welcomeScreen.classList.toggle("hidden", AppState.currentMessages.length > 0);
  }

  if (chatMessages) {
    chatMessages.innerHTML = "";
    AppState.currentMessages.forEach(msg => {
      if (msg.role === "user") {
        const row = document.createElement("div");
        row.className = "message-row user";
        row.innerHTML = `<div class="message-bubble"><div>${formatMarkdown(msg.text)}</div></div>`;
        chatMessages.appendChild(row);
      } else {
        const row = document.createElement("div");
        row.className = "message-row bot";
        let cardHtml = msg.weather ? buildWeatherCardHtml(msg.weather) : "";
        row.innerHTML = `
          <div class="bot-avatar"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg></div>
          <div class="message-bubble"><div class="bot-text">${formatMarkdown(msg.text)}</div>${cardHtml}</div>
        `;
        chatMessages.appendChild(row);
      }
    });
  }

  renderHistoryList();
  scrollToBottom();
}

function clearAllHistory() {
  if (confirm("Are you sure you want to clear your chat history?")) {
    AppState.chatHistory = [];
    localStorage.removeItem("weathergpt_sessions");
    createChatSession();
    showToast("Chat history cleared", "info");
  }
}

// ============================================================================

// ============================================================================
// 6.5 VOICE INPUT (Browser-native, no external speech API required)
// ============================================================================

function setupVoiceInput() {
  const voiceBtn = document.getElementById("voiceBtn");
  const input = document.getElementById("chatInput");
  if (!voiceBtn || !input) return;

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    voiceBtn.title = "Voice input is not supported in this browser";
    voiceBtn.addEventListener("click", () => {
      showToast("Voice input is not supported by this browser. Try Chrome or Edge.", "info");
    });
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = navigator.language || "en-IN";

  let listening = false;

  recognition.onstart = () => {
    listening = true;
    voiceBtn.classList.add("listening");
    voiceBtn.title = "Listening...";
    showToast("Listening… speak your weather question.", "info");
  };

  recognition.onresult = (event) => {
    let transcript = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    input.value = transcript;
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
    const sendBtn = document.getElementById("sendBtn");
    if (sendBtn) sendBtn.disabled = !transcript.trim() || AppState.isWaitingForResponse;
  };

  recognition.onerror = (event) => {
    console.warn("Speech recognition error:", event.error);
    if (event.error !== "no-speech") {
      showToast("Voice input could not be completed.", "error");
    }
  };

  recognition.onend = () => {
    listening = false;
    voiceBtn.classList.remove("listening");
    voiceBtn.title = "Use voice input";
  };

  voiceBtn.addEventListener("click", () => {
    if (AppState.isWaitingForResponse) return;
    if (listening) {
      recognition.stop();
    } else {
      try {
        recognition.start();
      } catch (e) {
        console.warn("Could not start speech recognition:", e);
      }
    }
  });
}

// 7. EVENT LISTENERS & APPLICATION BOOTSTRAP
// ============================================================================

document.addEventListener("DOMContentLoaded", async () => {
  // 1. Initialize Default Session & Storage
  loadSessionsFromStorage();
  createChatSession();

  // 2. Fetch Initial Weather for Default Location (Chennai)
  await updateActiveLocation(CONFIG.DEFAULT_LOCATION, true);

  // 4. Form and Chat Input Handling
  const chatForm = document.getElementById("chatForm");
  const chatInput = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");

  if (chatInput) {
    // Auto-resize input
    chatInput.addEventListener("input", () => {
      chatInput.style.height = "auto";
      chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + "px";
      if (sendBtn) {
        sendBtn.disabled = !chatInput.value.trim() || AppState.isWaitingForResponse;
      }
    });

    // Enter to send, Shift+Enter for newline
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (chatInput.value.trim() && !AppState.isWaitingForResponse) {
          handleSendMessage(chatInput.value);
        }
      }
    });
  }

  setupVoiceInput();

  if (chatForm) {
    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      if (chatInput && chatInput.value.trim() && !AppState.isWaitingForResponse) {
        handleSendMessage(chatInput.value);
      }
    });
  }

  // 5. Suggested Prompt Cards
  document.querySelectorAll(".prompt-card").forEach(card => {
    card.addEventListener("click", () => {
      const prompt = card.dataset.prompt;
      if (prompt) handleSendMessage(prompt);
    });
  });

  // 6. New Chat Buttons
  const newChatBtn = document.getElementById("newChatBtn");
  if (newChatBtn) {
    newChatBtn.addEventListener("click", () => {
      createChatSession();
      showToast("Started new chat session", "info");
      // On mobile, close sidebar after clicking
      closeMobileSidebar();
    });
  }

  const clearHistoryBtn = document.getElementById("clearHistoryBtn");
  if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener("click", clearAllHistory);
  }

  // 7. Location Modal & Selector Trigger
  const locSelectorBtn = document.getElementById("locationSelectorBtn");
  const modalCloseBtn = document.getElementById("modalCloseBtn");
  const locModal = document.getElementById("locationModal");

  if (locSelectorBtn) locSelectorBtn.addEventListener("click", openLocationModal);
  if (modalCloseBtn) modalCloseBtn.addEventListener("click", closeLocationModal);

  if (locModal) {
    locModal.addEventListener("click", (e) => {
      if (e.target === locModal) closeLocationModal();
    });
  }

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeLocationModal();
  });

  // Hub chips inside modal
  document.querySelectorAll(".hub-chip").forEach(chip => {
    chip.addEventListener("click", async () => {
      const city = chip.dataset.city;
      const res = await ApiClient.geocodeQuery(city);
      if (res && res.length > 0) {
        updateActiveLocation(res[0], true);
        closeLocationModal();
      }
    });
  });

  // GPS Geolocation button
  const useGeoBtn = document.getElementById("useMyLocationBtn");
  if (useGeoBtn) useGeoBtn.addEventListener("click", requestBrowserLocation);

  // Search input inside modal
  setupSearchInput();

  // 9. Mobile Sidebar Navigation
  const sidebar = document.getElementById("sidebar");
  const sidebarToggleBtn = document.getElementById("sidebarToggleBtn");
  const sidebarCloseBtn = document.getElementById("sidebarCloseBtn");
  const sidebarOverlay = document.getElementById("sidebarOverlay");

  function openMobileSidebar() {
    if (sidebar) sidebar.classList.add("open");
    if (sidebarOverlay) sidebarOverlay.classList.add("active");
  }

  function closeMobileSidebar() {
    if (sidebar) sidebar.classList.remove("open");
    if (sidebarOverlay) sidebarOverlay.classList.remove("active");
  }

  if (sidebarToggleBtn) sidebarToggleBtn.addEventListener("click", openMobileSidebar);
  if (sidebarCloseBtn) sidebarCloseBtn.addEventListener("click", closeMobileSidebar);
  if (sidebarOverlay) sidebarOverlay.addEventListener("click", closeMobileSidebar);

  console.log("🌤️ WeatherGPT Phase 1 MVP initialized successfully.");
});
