/**
 * Content-to-Ebook Agent — Frontend JavaScript
 *
 * Handles project creation, content upload, and ebook generation
 * by communicating with the backend API.
 */

const API_BASE = "/api/v1";
let currentProjectId = null;
let currentUserId = null;

// ─── Project Creation ───────────────────────────

const projectForm = document.getElementById("project-form");
if (projectForm) {
  projectForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(projectForm);
    const data = {
      title: formData.get("title"),
      description: formData.get("description"),
      language: formData.get("language"),
      template: formData.get("template"),
    };

    // Ensure we have a user (simplified — in production use auth)
    if (!currentUserId) {
      currentUserId = await ensureUser();
    }

    const res = await fetch(
      `${API_BASE}/projects?user_id=${currentUserId}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }
    );

    if (res.ok) {
      const project = await res.json();
      currentProjectId = project.id;
      showSection("content-upload");
      showSection("generate-section");
    } else {
      alert("Error creating project. Please try again.");
    }
  });
}

// ─── Text Upload ────────────────────────────────

const textForm = document.getElementById("text-form");
if (textForm) {
  textForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentProjectId) return;

    const formData = new FormData(textForm);

    const res = await fetch(
      `${API_BASE}/projects/${currentProjectId}/content/text`,
      {
        method: "POST",
        body: formData,
      }
    );

    if (res.ok) {
      const item = await res.json();
      addContentItem(item);
      textForm.reset();
    } else {
      alert("Error uploading text.");
    }
  });
}

// ─── Media Upload ───────────────────────────────

const mediaForm = document.getElementById("media-form");
if (mediaForm) {
  mediaForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentProjectId) return;

    const formData = new FormData(mediaForm);

    const res = await fetch(
      `${API_BASE}/projects/${currentProjectId}/content/media`,
      {
        method: "POST",
        body: formData,
      }
    );

    if (res.ok) {
      const item = await res.json();
      addContentItem(item);
      mediaForm.reset();
    } else {
      const error = await res.json();
      alert(error.detail || "Error uploading media.");
    }
  });
}

// ─── Drag & Drop ────────────────────────────────

const dropZone = document.getElementById("drop-zone");
if (dropZone) {
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    const fileInput = document.getElementById("media-file");
    fileInput.files = e.dataTransfer.files;
  });
}

// ─── Generate Ebook ─────────────────────────────

const generateBtn = document.getElementById("generate-btn");
if (generateBtn) {
  generateBtn.addEventListener("click", async () => {
    if (!currentProjectId) return;

    const formats = [];
    document
      .querySelectorAll('.generate-options input[type="checkbox"]:checked')
      .forEach((cb) => formats.push(cb.name));

    if (formats.length === 0) {
      alert("Select at least one format.");
      return;
    }

    const statusEl = document.getElementById("generation-status");
    statusEl.className = "status-message processing";
    statusEl.textContent = "Generating your ebook... This may take a moment.";
    statusEl.classList.remove("hidden");

    generateBtn.disabled = true;

    const res = await fetch(
      `${API_BASE}/projects/${currentProjectId}/generate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ formats }),
      }
    );

    generateBtn.disabled = false;

    if (res.ok) {
      const files = await res.json();
      statusEl.className = "status-message success";
      statusEl.innerHTML =
        "Ebook generated successfully! " +
        files
          .map(
            (f) =>
              `<a href="${API_BASE}/projects/${currentProjectId}/download/${f.id}">${f.format.toUpperCase()}</a>`
          )
          .join(" | ");
    } else {
      statusEl.className = "status-message error";
      statusEl.textContent = "Error generating ebook. Please try again.";
    }
  });
}

// ─── Helpers ────────────────────────────────────

function showSection(id) {
  document.getElementById(id)?.classList.remove("hidden");
}

function addContentItem(item) {
  const container = document.getElementById("content-items");
  if (!container) return;

  const div = document.createElement("div");
  div.className = "content-item";
  div.innerHTML = `
    <span>${item.title || "Untitled"}</span>
    <span class="type-badge">${item.content_type}</span>
  `;
  container.appendChild(div);
}

async function ensureUser() {
  // Simplified user creation — in production, use proper auth (Firebase, etc.)
  const res = await fetch(`${API_BASE}/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: "user@example.com",
      name: "Demo User",
    }),
  });

  if (res.ok) {
    const user = await res.json();
    return user.id;
  }
  return null;
}
