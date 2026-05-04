document.addEventListener("DOMContentLoaded", () => {
  const operationCard = document.querySelector(".operation-card");

  if (!operationCard) {
    return;
  }

  const statusUrl = operationCard.dataset.statusUrl;
  const stepsContainer = document.getElementById("operation-steps");
  const statusBadge = document.getElementById("operation-status");

  if (!statusUrl || !stepsContainer || !statusBadge) {
    return;
  }

  function getBadgeData(status) {
    if (status === "success") {
      return {
        className: "badge badge-green",
        label: "OK",
      };
    }

    if (status === "error") {
      return {
        className: "badge badge-red",
        label: "Erreur",
      };
    }

    return {
      className: "badge badge-orange",
      label: '<span class="loading-dot"></span> En cours',
    };
  }

  function getItemClass(status) {
    if (status === "success") {
      return "diagnostic-item diagnostic-success";
    }

    if (status === "error") {
      return "diagnostic-item diagnostic-error";
    }

    return "diagnostic-item diagnostic-warning";
  }

  function renderStep(step) {
    const item = document.createElement("article");
    item.className = getItemClass(step.status);

    const badge = getBadgeData(step.status);

    const content = document.createElement("div");

    const title = document.createElement("strong");
    title.textContent = step.name;

    const message = document.createElement("p");
    message.textContent = step.message || "";

    content.appendChild(title);
    content.appendChild(message);

    const status = document.createElement("span");
    status.className = badge.className;
    status.innerHTML = badge.label;

    item.appendChild(content);
    item.appendChild(status);

    return item;
  }

  function updateGlobalStatus(operationStatus) {
    if (operationStatus === "success") {
      statusBadge.className = "badge badge-green";
      statusBadge.textContent = "Terminé";
      return;
    }

    if (operationStatus === "error") {
      statusBadge.className = "badge badge-red";
      statusBadge.textContent = "Erreur";
      return;
    }

    statusBadge.className = "badge badge-orange";
    statusBadge.innerHTML = '<span class="loading-dot"></span> En cours';
  }

  async function refreshOperation() {
    try {
      const response = await fetch(statusUrl, {
        headers: {
          "Accept": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();

      stepsContainer.innerHTML = "";

      data.steps.forEach((step) => {
        stepsContainer.appendChild(renderStep(step));
      });

      updateGlobalStatus(data.status);

      if (data.status === "success" || data.status === "error") {
        clearInterval(timer);
      }
    } catch (error) {
      statusBadge.className = "badge badge-red";
      statusBadge.textContent = "Erreur de suivi";

      const item = document.createElement("article");
      item.className = "diagnostic-item diagnostic-error";

      const content = document.createElement("div");

      const title = document.createElement("strong");
      title.textContent = "Erreur de récupération";

      const message = document.createElement("p");
      message.textContent = error.message;

      content.appendChild(title);
      content.appendChild(message);

      const badge = document.createElement("span");
      badge.className = "badge badge-red";
      badge.textContent = "Erreur";

      item.appendChild(content);
      item.appendChild(badge);

      stepsContainer.appendChild(item);
      clearInterval(timer);
    }
  }

  refreshOperation();

  const timer = setInterval(refreshOperation, 1000);
});