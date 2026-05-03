const PAGE_SIZE = 20;
const THEME_STORAGE_KEY = "three-positives-theme";
const DARK_THEME = "dark";
const LIGHT_THEME = "light";
const API_BASE = window.location.protocol === "file:" ? "http://localhost:8080" : "";
const DEFAULT_REMINDER_TIME = "20:00";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

const elements = {
  themeToggleButton: document.querySelector("#theme-toggle"),
  themeColorMeta: document.querySelector('meta[name="theme-color"]'),
  logoutButton: document.querySelector("#logout-button"),
  userChip: document.querySelector("#user-chip"),

  authPanel: document.querySelector("#auth-panel"),
  authStatus: document.querySelector("#auth-status"),
  showLoginButton: document.querySelector("#show-login"),
  showRegisterButton: document.querySelector("#show-register"),
  loginForm: document.querySelector("#login-form"),
  registerForm: document.querySelector("#register-form"),
  authEmail: document.querySelector("#auth-email"),
  authPassword: document.querySelector("#auth-password"),
  registerEmail: document.querySelector("#register-email"),
  registerPassword: document.querySelector("#register-password"),

  appNav: document.querySelector("#app-nav"),
  navLinks: Array.from(document.querySelectorAll(".nav-link")),
  entryPanel: document.querySelector("#entry-panel"),
  historyPanel: document.querySelector("#history-panel"),
  calendarPanel: document.querySelector("#calendar-panel"),
  reminderPanel: document.querySelector("#reminder-panel"),

  form: document.querySelector("#daily-form"),
  dateInput: document.querySelector("#entry-date"),
  textareas: [
    document.querySelector("#positive-1"),
    document.querySelector("#positive-2"),
    document.querySelector("#positive-3"),
  ],
  status: document.querySelector("#status"),

  searchInput: document.querySelector("#search"),
  historyList: document.querySelector("#history-list"),
  historyStatus: document.querySelector("#history-status"),
  loadMoreButton: document.querySelector("#load-more"),
  deleteDayButton: document.querySelector("#delete-day"),

  calendarMonth: document.querySelector("#calendar-month"),
  calendarGrid: document.querySelector("#calendar-grid"),
  calendarStatus: document.querySelector("#calendar-status"),

  reminderEnabled: document.querySelector("#reminder-enabled"),
  reminderTime: document.querySelector("#reminder-time"),
  saveReminderButton: document.querySelector("#save-reminder"),
  reminderStatus: document.querySelector("#reminder-status"),
};

const state = {
  user: null,
  entriesByDate: {},
  historyEntries: [],
  historyOffset: 0,
  hasMoreHistory: true,
  isLoadingHistory: false,
  searchDebounceTimer: null,
  reminder: {
    enabled: false,
    time: DEFAULT_REMINDER_TIME,
  },
  reminderIntervalId: null,
  activeView: "entry",
};

function setStatus(element, message, isError = false) {
  if (!element) {
    return;
  }
  element.textContent = message;
  element.classList.toggle("error", isError);
}

function todayIsoDate() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function currentMonthIso() {
  return todayIsoDate().slice(0, 7);
}

function isFutureIsoDate(isoDate) {
  return isoDate > todayIsoDate();
}

function isUnauthorizedError(error) {
  return error instanceof ApiError && error.status === 401;
}

function getStoredTheme() {
  try {
    return localStorage.getItem(THEME_STORAGE_KEY);
  } catch {
    return null;
  }
}

function setStoredTheme(theme) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    /* no-op */
  }
}

function applyTheme(theme) {
  const effectiveTheme = theme === DARK_THEME ? DARK_THEME : LIGHT_THEME;
  document.documentElement.setAttribute("data-theme", effectiveTheme);

  if (elements.themeToggleButton) {
    elements.themeToggleButton.textContent =
      effectiveTheme === DARK_THEME ? "Theme clair" : "Theme noir";
    elements.themeToggleButton.setAttribute("aria-pressed", String(effectiveTheme === DARK_THEME));
  }

  if (elements.themeColorMeta) {
    elements.themeColorMeta.setAttribute(
      "content",
      effectiveTheme === DARK_THEME ? "#0b0b0b" : "#2d6a4f"
    );
  }

  setStoredTheme(effectiveTheme);
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute("data-theme");
  applyTheme(currentTheme === DARK_THEME ? LIGHT_THEME : DARK_THEME);
}

async function apiRequest(path, options = {}) {
  const requestOptions = {
    method: options.method || "GET",
    credentials: "include",
    headers: {
      ...(options.headers || {}),
    },
  };

  if (options.body !== undefined) {
    requestOptions.body = JSON.stringify(options.body);
    requestOptions.headers["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, requestOptions);
  } catch {
    throw new ApiError("Serveur inaccessible", 0);
  }

  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new ApiError(data.error || "Erreur serveur", response.status);
  }

  return data;
}

function entryDateLabel(isoDate) {
  const parsed = new Date(`${isoDate}T00:00:00`);
  return new Intl.DateTimeFormat("fr-FR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(parsed);
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function rememberEntry(entry) {
  state.entriesByDate[entry.date] = {
    items: entry.items,
    updatedAt: entry.updatedAt,
  };
}

function resetHistoryState() {
  state.historyEntries = [];
  state.historyOffset = 0;
  state.hasMoreHistory = true;
}

function setAuthMode(mode) {
  const loginMode = mode === "login";
  elements.loginForm.hidden = !loginMode;
  elements.registerForm.hidden = loginMode;
  elements.showLoginButton.classList.toggle("is-active", loginMode);
  elements.showRegisterButton.classList.toggle("is-active", !loginMode);
  elements.showLoginButton.setAttribute("aria-pressed", String(loginMode));
  elements.showRegisterButton.setAttribute("aria-pressed", String(!loginMode));
  setStatus(elements.authStatus, "", false);
}

function setActiveView(viewName) {
  state.activeView = viewName;
  const visiblePanels = {
    entry: elements.entryPanel,
    history: elements.historyPanel,
    calendar: elements.calendarPanel,
    reminder: elements.reminderPanel,
  };

  Object.entries(visiblePanels).forEach(([name, panel]) => {
    panel.hidden = name !== viewName;
  });

  elements.navLinks.forEach((button) => {
    const isActive = button.dataset.view === viewName;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
}

function setAuthenticatedUI(isAuthenticated) {
  elements.authPanel.hidden = isAuthenticated;
  elements.appNav.hidden = !isAuthenticated;
  elements.logoutButton.hidden = !isAuthenticated;
  elements.userChip.hidden = !isAuthenticated;

  if (isAuthenticated) {
    setActiveView(state.activeView);
  } else {
    elements.entryPanel.hidden = true;
    elements.historyPanel.hidden = true;
    elements.calendarPanel.hidden = true;
    elements.reminderPanel.hidden = true;
  }

  if (isAuthenticated && state.user) {
    elements.userChip.textContent = `Connecte en tant que ${state.user.email}`;
  } else {
    elements.userChip.textContent = "";
  }
}

function resetPrivateState() {
  state.entriesByDate = {};
  state.activeView = "entry";
  resetHistoryState();
  elements.historyList.innerHTML = "";
  elements.calendarGrid.innerHTML = "";
  setStatus(elements.status, "", false);
  setStatus(elements.historyStatus, "", false);
  setStatus(elements.calendarStatus, "", false);
  setStatus(elements.reminderStatus, "", false);

  elements.textareas.forEach((textarea) => {
    textarea.value = "";
  });

  stopReminderLoop();
}

function handleUnauthorized() {
  state.user = null;
  resetPrivateState();
  setAuthenticatedUI(false);
  setStatus(elements.authStatus, "Session expiree. Merci de te reconnecter.", true);
}

function renderHistoryControls() {
  elements.loadMoreButton.hidden = !state.hasMoreHistory;
  elements.loadMoreButton.disabled = state.isLoadingHistory;
  elements.loadMoreButton.textContent = state.isLoadingHistory ? "Chargement..." : "Charger plus";

  if (state.isLoadingHistory) {
    setStatus(elements.historyStatus, "Chargement de l'historique...");
    return;
  }

  if (state.historyEntries.length === 0) {
    setStatus(elements.historyStatus, "");
    return;
  }

  if (state.hasMoreHistory) {
    setStatus(elements.historyStatus, `${state.historyEntries.length} élément(s) affichés.`);
    return;
  }

  setStatus(
    elements.historyStatus,
    `Tous les éléments sont affichés (${state.historyEntries.length}).`
  );
}

function renderHistory() {
  if (state.historyEntries.length === 0) {
    elements.historyList.innerHTML = '<p class="empty">Aucune note pour le moment.</p>';
    renderHistoryControls();
    return;
  }

  elements.historyList.innerHTML = state.historyEntries
    .map((entry) => {
      const items = entry.items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      return `
        <article class="history-card">
          <div class="history-header">
            <h3 class="history-date">${entryDateLabel(entry.date)}</h3>
            <button class="history-edit button-secondary" data-date="${entry.date}" type="button">
              Ouvrir
            </button>
          </div>
          <ul>${items}</ul>
        </article>
      `;
    })
    .join("");

  renderHistoryControls();
}

async function loadHistoryPage({ reset = false } = {}) {
  if (state.isLoadingHistory) {
    return;
  }

  if (reset) {
    resetHistoryState();
  }

  if (!state.hasMoreHistory) {
    renderHistoryControls();
    return;
  }

  state.isLoadingHistory = true;
  renderHistoryControls();

  try {
    const query = elements.searchInput.value.trim();
    const params = new URLSearchParams();
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(state.historyOffset));
    if (query) {
      params.set("q", query);
    }

    const data = await apiRequest(`/api/entries?${params.toString()}`);
    const incomingEntries = Array.isArray(data.entries) ? data.entries : [];

    if (reset) {
      state.historyEntries = [];
    }

    const indexByDate = new Map(state.historyEntries.map((entry, index) => [entry.date, index]));

    incomingEntries.forEach((entry) => {
      rememberEntry(entry);
      const existingIndex = indexByDate.get(entry.date);
      if (existingIndex === undefined) {
        state.historyEntries.push(entry);
      } else {
        state.historyEntries[existingIndex] = entry;
      }
    });

    state.hasMoreHistory = Boolean(data.hasMore);
    if (typeof data.nextOffset === "number") {
      state.historyOffset = data.nextOffset;
    } else {
      state.historyOffset += incomingEntries.length;
    }

    renderHistory();
  } finally {
    state.isLoadingHistory = false;
    renderHistoryControls();
  }
}

async function loadFormForDate(isoDate) {
  let entry = state.entriesByDate[isoDate];

  if (!entry) {
    try {
      const data = await apiRequest(`/api/entries/${isoDate}`);
      rememberEntry(data.entry);
      entry = state.entriesByDate[isoDate];
    } catch (error) {
      if (error instanceof ApiError && error.message === "entry not found") {
        entry = undefined;
      } else {
        throw error;
      }
    }
  }

  elements.textareas.forEach((textarea, index) => {
    textarea.value = entry?.items?.[index] || "";
  });

  setStatus(elements.status, entry ? "Jour chargé. Tu peux modifier puis sauvegarder." : "");
}

async function refreshHistoryAndForm() {
  await loadHistoryPage({ reset: true });
  await loadFormForDate(elements.dateInput.value);
}

function getReminderStorageKey() {
  return state.user ? `three-positives-reminder-last-${state.user.id}` : "three-positives-reminder-last";
}

function getLastReminderDate() {
  try {
    return localStorage.getItem(getReminderStorageKey());
  } catch {
    return null;
  }
}

function setLastReminderDate(isoDate) {
  try {
    localStorage.setItem(getReminderStorageKey(), isoDate);
  } catch {
    /* no-op */
  }
}

async function requestNotificationPermissionIfNeeded() {
  if (!state.reminder.enabled || typeof Notification === "undefined") {
    return;
  }

  if (Notification.permission === "default") {
    await Notification.requestPermission();
  }
}

function maybeTriggerReminderNotification() {
  if (!state.reminder.enabled || typeof Notification === "undefined") {
    return;
  }

  if (Notification.permission !== "granted") {
    return;
  }

  const now = new Date();
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const nowTime = `${hh}:${mm}`;
  if (nowTime !== state.reminder.time) {
    return;
  }

  const today = todayIsoDate();
  if (getLastReminderDate() === today) {
    return;
  }

  new Notification("3 choses positives", {
    body: "Pense a noter tes 3 choses positives du jour.",
  });
  setLastReminderDate(today);
}

function stopReminderLoop() {
  if (state.reminderIntervalId !== null) {
    window.clearInterval(state.reminderIntervalId);
    state.reminderIntervalId = null;
  }
}

function startReminderLoop() {
  stopReminderLoop();
  if (!state.reminder.enabled) {
    return;
  }

  maybeTriggerReminderNotification();
  state.reminderIntervalId = window.setInterval(maybeTriggerReminderNotification, 30 * 1000);
}

async function loadReminder() {
  const data = await apiRequest("/api/reminder");
  state.reminder = data.settings || { enabled: false, time: DEFAULT_REMINDER_TIME };

  elements.reminderEnabled.checked = Boolean(state.reminder.enabled);
  elements.reminderTime.value = state.reminder.time || DEFAULT_REMINDER_TIME;

  await requestNotificationPermissionIfNeeded();
  startReminderLoop();
}

async function loadCalendar() {
  const selectedMonth = elements.calendarMonth.value || currentMonthIso();
  const data = await apiRequest(`/api/calendar?month=${encodeURIComponent(selectedMonth)}`);

  renderCalendar(selectedMonth, data.completedDates || []);
  setStatus(elements.calendarStatus, `${(data.completedDates || []).length} jour(s) complété(s).`);
}

function renderCalendar(monthValue, completedDates) {
  const [yearText, monthText] = monthValue.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  if (!year || !month) {
    elements.calendarGrid.innerHTML = "";
    return;
  }

  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDay = new Date(year, month - 1, 1);
  const firstWeekday = (firstDay.getDay() + 6) % 7;
  const completedSet = new Set(completedDates.map((value) => Number(value.slice(8, 10))));

  const headers = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
  const cells = [];

  headers.forEach((header) => {
    cells.push(`<div class="calendar-head">${header}</div>`);
  });

  for (let i = 0; i < firstWeekday; i += 1) {
    cells.push('<div class="calendar-day empty"></div>');
  }

  const today = todayIsoDate();
  const todayYear = Number(today.slice(0, 4));
  const todayMonth = Number(today.slice(5, 7));
  const todayDay = Number(today.slice(8, 10));

  for (let day = 1; day <= daysInMonth; day += 1) {
    const classes = ["calendar-day"];
    if (completedSet.has(day)) {
      classes.push("completed");
    }
    if (todayYear === year && todayMonth === month && todayDay === day) {
      classes.push("today");
    }
    cells.push(`<div class="${classes.join(" ")}">${day}</div>`);
  }

  elements.calendarGrid.innerHTML = cells.join("");
}

async function handleLoginSubmit(event) {
  event.preventDefault();
  setStatus(elements.authStatus, "Connexion...");

  try {
    const data = await apiRequest("/api/auth/login", {
      method: "POST",
      body: {
        email: elements.authEmail.value,
        password: elements.authPassword.value,
      },
    });
    await onAuthenticated(data.user, "Connexion reussie.");
  } catch (error) {
    setStatus(elements.authStatus, error.message || "Echec de connexion.", true);
  }
}

async function handleRegisterSubmit(event) {
  event.preventDefault();
  setStatus(elements.authStatus, "Creation du compte...");

  try {
    const data = await apiRequest("/api/auth/register", {
      method: "POST",
      body: {
        email: elements.registerEmail.value,
        password: elements.registerPassword.value,
      },
    });
    await onAuthenticated(data.user, "Compte cree et connecte.");
  } catch (error) {
    setStatus(elements.authStatus, error.message || "Echec de creation du compte.", true);
  }
}

async function handleLogoutClick() {
  try {
    await apiRequest("/api/auth/logout", { method: "POST" });
  } catch {
    /* ignore */
  }

  state.user = null;
  resetPrivateState();
  setAuthenticatedUI(false);
  setStatus(elements.authStatus, "Deconnecte.");
}

async function onAuthenticated(user, statusMessage) {
  state.user = user;
  state.activeView = "entry";
  setAuthenticatedUI(true);
  setStatus(elements.authStatus, statusMessage);

  const today = todayIsoDate();
  elements.dateInput.max = today;
  elements.dateInput.value = today;
  elements.calendarMonth.value = currentMonthIso();

  try {
    await Promise.all([refreshHistoryAndForm(), loadCalendar(), loadReminder()]);
    setStatus(elements.status, "");
  } catch (error) {
    if (isUnauthorizedError(error)) {
      handleUnauthorized();
      return;
    }
    setStatus(elements.status, error.message || "Impossible de charger les donnees.", true);
  }
}

async function restoreSession() {
  try {
    const data = await apiRequest("/api/auth/me");
    await onAuthenticated(data.user, "Session restauree.");
  } catch (error) {
    state.user = null;
    resetPrivateState();
    setAuthenticatedUI(false);
    if (!(error instanceof ApiError) || error.status !== 401) {
      setStatus(elements.authStatus, "Impossible de verifier la session.", true);
    }
  }
}

async function saveCurrentForm(event) {
  event.preventDefault();

  const isoDate = elements.dateInput.value;
  const items = elements.textareas.map((textarea) => textarea.value.trim());

  if (!isoDate) {
    setStatus(elements.status, "Merci de choisir une date.", true);
    return;
  }

  if (isFutureIsoDate(isoDate)) {
    setStatus(elements.status, "Tu ne peux pas enregistrer une date dans le futur.", true);
    return;
  }

  if (items.some((item) => !item)) {
    setStatus(elements.status, "Il faut remplir les 3 champs positifs.", true);
    return;
  }

  try {
    const data = await apiRequest(`/api/entries/${isoDate}`, {
      method: "PUT",
      body: { items },
    });

    rememberEntry(data.entry);
    await Promise.all([loadHistoryPage({ reset: true }), loadCalendar()]);
    await loadFormForDate(isoDate);
    setStatus(elements.status, "Sauvegarde reussie");
  } catch (error) {
    if (isUnauthorizedError(error)) {
      handleUnauthorized();
      return;
    }
    setStatus(elements.status, error.message || "Echec de sauvegarde.", true);
  }
}

async function deleteCurrentDay() {
  const isoDate = elements.dateInput.value;
  if (!isoDate) {
    setStatus(elements.status, "Merci de choisir une date.", true);
    return;
  }

  try {
    await apiRequest(`/api/entries/${isoDate}`, { method: "DELETE" });
    delete state.entriesByDate[isoDate];

    elements.textareas.forEach((textarea) => {
      textarea.value = "";
    });

    await Promise.all([loadHistoryPage({ reset: true }), loadCalendar()]);
    setStatus(elements.status, "Jour supprime.");
  } catch (error) {
    if (isUnauthorizedError(error)) {
      handleUnauthorized();
      return;
    }
    setStatus(elements.status, error.message || "Echec de suppression.", true);
  }
}

function openHistoryItem(event) {
  const trigger = event.target.closest("[data-date]");
  if (!trigger) {
    return;
  }

  const targetDate = trigger.getAttribute("data-date");
  elements.dateInput.value = targetDate;
  void loadFormForDate(targetDate).catch((error) => {
    if (isUnauthorizedError(error)) {
      handleUnauthorized();
      return;
    }
    setStatus(elements.status, error.message || "Impossible de charger cette date.", true);
  });

  window.scrollTo({ top: 0, behavior: "smooth" });
}

function queueSearchRefresh() {
  window.clearTimeout(state.searchDebounceTimer);
  state.searchDebounceTimer = window.setTimeout(async () => {
    try {
      await loadHistoryPage({ reset: true });
    } catch (error) {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
        return;
      }
      setStatus(elements.historyStatus, "Recherche indisponible.", true);
    }
  }, 250);
}

async function handleCalendarMonthChange() {
  try {
    await loadCalendar();
  } catch (error) {
    if (isUnauthorizedError(error)) {
      handleUnauthorized();
      return;
    }
    setStatus(elements.calendarStatus, error.message || "Impossible de charger le calendrier.", true);
  }
}

async function saveReminderSettings() {
  setStatus(elements.reminderStatus, "Sauvegarde du rappel...");

  try {
    const data = await apiRequest("/api/reminder", {
      method: "PUT",
      body: {
        enabled: elements.reminderEnabled.checked,
        time: elements.reminderTime.value || DEFAULT_REMINDER_TIME,
      },
    });

    state.reminder = data.settings;
    elements.reminderEnabled.checked = state.reminder.enabled;
    elements.reminderTime.value = state.reminder.time;

    await requestNotificationPermissionIfNeeded();
    startReminderLoop();
    setStatus(elements.reminderStatus, "Rappel enregistre.");
  } catch (error) {
    if (isUnauthorizedError(error)) {
      handleUnauthorized();
      return;
    }
    setStatus(elements.reminderStatus, error.message || "Impossible d'enregistrer le rappel.", true);
  }
}

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => {
      /* no-op */
    });
  }
}

function bindEvents() {
  elements.themeToggleButton.addEventListener("click", toggleTheme);
  elements.showLoginButton.addEventListener("click", () => {
    setAuthMode("login");
  });
  elements.showRegisterButton.addEventListener("click", () => {
    setAuthMode("register");
  });
  elements.loginForm.addEventListener("submit", handleLoginSubmit);
  elements.registerForm.addEventListener("submit", handleRegisterSubmit);
  elements.logoutButton.addEventListener("click", handleLogoutClick);
  elements.appNav.addEventListener("click", (event) => {
    const target = event.target.closest("[data-view]");
    if (!target) {
      return;
    }
    setActiveView(target.dataset.view);
  });

  elements.form.addEventListener("submit", saveCurrentForm);
  elements.dateInput.addEventListener("change", () => {
    void loadFormForDate(elements.dateInput.value).catch((error) => {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
        return;
      }
      setStatus(elements.status, error.message || "Impossible de charger cette date.", true);
    });
  });

  elements.searchInput.addEventListener("input", queueSearchRefresh);
  elements.historyList.addEventListener("click", openHistoryItem);
  elements.loadMoreButton.addEventListener("click", async () => {
    try {
      await loadHistoryPage();
    } catch (error) {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
        return;
      }
      setStatus(elements.historyStatus, "Impossible de charger plus d'elements.", true);
    }
  });

  elements.deleteDayButton.addEventListener("click", deleteCurrentDay);
  elements.calendarMonth.addEventListener("change", () => {
    void handleCalendarMonthChange();
  });

  elements.saveReminderButton.addEventListener("click", saveReminderSettings);
}

async function initializeApp() {
  applyTheme(getStoredTheme());
  setAuthMode("login");
  elements.dateInput.max = todayIsoDate();
  elements.dateInput.value = todayIsoDate();
  elements.calendarMonth.value = currentMonthIso();

  bindEvents();
  await restoreSession();
  registerServiceWorker();
}

void initializeApp();
