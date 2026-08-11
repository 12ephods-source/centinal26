(() => {
  const data = window.AUTOMATION_OS_DATA;
  const $ = (selector) => document.querySelector(selector);

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function renderInvariant() {
    $("#invariant-flow").innerHTML = data.invariant
      .map((item, index) => `
        <div class="invariant-node">
          <span class="node-index">${String(index + 1).padStart(2, "0")}</span>
          <strong>${escapeHtml(item)}</strong>
        </div>${index < data.invariant.length - 1 ? '<span class="flow-arrow" aria-hidden="true">→</span>' : ""}`)
      .join("");
  }

  function renderStatuses() {
    $("#status-grid").innerHTML = data.statuses
      .map((item) => `
        <article class="status-card ${item.state.toLowerCase()}">
          <div class="status-card-head">
            <span class="status-dot"></span>
            <span class="status-label">${escapeHtml(item.state)}</span>
          </div>
          <h3>${escapeHtml(item.label)}</h3>
          <p>${escapeHtml(item.detail)}</p>
        </article>`)
      .join("");
  }

  function renderArchitecture() {
    $("#architecture-grid").innerHTML = data.architecture
      .map((item) => `
        <article class="architecture-card">
          <span class="architecture-code">${escapeHtml(item.code)}</span>
          <h3>${escapeHtml(item.name)}</h3>
          <p>${escapeHtml(item.text)}</p>
        </article>`)
      .join("");
  }

  function renderTools() {
    $("#rc4-tools").innerHTML = data.tools
      .map((item, index) => `
        <article class="tool-card">
          <span class="tool-index">RC4.${index + 1}</span>
          <h3>${escapeHtml(item.name)}</h3>
          <p>${escapeHtml(item.text)}</p>
        </article>`)
      .join("");
  }

  function renderPipeline() {
    $("#release-pipeline").innerHTML = data.pipeline
      .map((item, index) => `
        <div class="pipeline-step ${escapeHtml(item.state)}">
          <span class="pipeline-index">${index + 1}</span>
          <div><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.state.toUpperCase())}</small></div>
        </div>`)
      .join("");
  }

  function renderProvenance() {
    $("#provenance-grid").innerHTML = data.provenance
      .map((item) => `
        <article class="provenance-card">
          <h3>${escapeHtml(item.name)}</h3>
          <p>${escapeHtml(item.text)}</p>
        </article>`)
      .join("");
  }

  function renderSafety() {
    $("#safety-grid").innerHTML = data.safety
      .map((item) => `
        <article class="safety-card">
          <span aria-hidden="true">◇</span>
          <div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.text)}</p></div>
        </article>`)
      .join("");
  }

  function renderTimeline() {
    $("#timeline-list").innerHTML = data.timeline
      .map((item) => `
        <article class="timeline-item">
          <time>${escapeHtml(item.date)}</time>
          <div class="timeline-marker" aria-hidden="true"></div>
          <div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.text)}</p></div>
        </article>`)
      .join("");
  }

  function initNavigation() {
    const button = $(".nav-toggle");
    const nav = $("#site-nav");
    button.addEventListener("click", () => {
      const open = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!open));
      nav.classList.toggle("open", !open);
    });
    nav.addEventListener("click", (event) => {
      if (event.target instanceof HTMLAnchorElement) {
        nav.classList.remove("open");
        button.setAttribute("aria-expanded", "false");
      }
    });
  }

  function initActiveSection() {
    const links = [...document.querySelectorAll('.site-nav a[href^="#"]')];
    const sections = links
      .map((link) => document.querySelector(link.getAttribute("href")))
      .filter(Boolean);
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      links.forEach((link) => link.classList.toggle("active", link.getAttribute("href") === `#${visible.target.id}`));
    }, { rootMargin: "-25% 0px -65% 0px", threshold: [0, 0.1, 0.5] });
    sections.forEach((section) => observer.observe(section));
  }

  renderInvariant();
  renderStatuses();
  renderArchitecture();
  renderTools();
  renderPipeline();
  renderProvenance();
  renderSafety();
  renderTimeline();
  initNavigation();
  initActiveSection();
})();
