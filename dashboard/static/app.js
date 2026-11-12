(() => {
  "use strict";

  const SLOTS = ["t1_cam1", "t1_cam2", "t2_cam1", "t2_cam2"];
  const globalStatus = document.getElementById("globalStatus");

  async function checkHealth() {
    try {
      const res = await fetch("/api/inventory");
      if (res.ok && globalStatus) {
        globalStatus.className = "status-chip running";
        globalStatus.querySelector(".status-text").textContent = "Connected";
      }
    } catch (_) {
      if (globalStatus) {
        globalStatus.className = "status-chip error";
        globalStatus.querySelector(".status-text").textContent = "Disconnected";
      }
    }
  }

  function findLatestForSlot(runs, slot) {
    const direct = runs.find((r) => r.startsWith(`${slot}_`));
    if (direct) return direct;
    // Backward compatibility with legacy cam1_ / cam2_ outputs for Trolley 1
    if (slot === "t1_cam1") return runs.find((r) => r.startsWith("cam1_"));
    if (slot === "t1_cam2") return runs.find((r) => r.startsWith("cam2_"));
    return null;
  }

  async function loadLatestRuns() {
    try {
      const res = await fetch("/api/runs");
      const runs = await res.json();
      SLOTS.forEach((slot) => {
        const match = findLatestForSlot(runs, slot);
        const player = document.getElementById(`player_${slot}`);
        if (match && player) {
          const src = `/videos/${encodeURIComponent(match)}`;
          if (!player.src.endsWith(src)) {
            player.src = src;
          }
        }
      });
    } catch (e) {
      console.error("Failed loading runs", e);
    }
  }

  function setupUploadForm(slot) {
    const form = document.getElementById(`uploadForm_${slot}`);
    const status = document.getElementById(`status_${slot}`);
    const btn = document.getElementById(`btn_${slot}`);
    const player = document.getElementById(`player_${slot}`);
    const stream = document.getElementById(`stream_${slot}`);
    const calibContainer = document.getElementById(`calibrationContainer_${slot}`);

    if (!form) return;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const formData = new FormData(form);

      btn.disabled = true;
      btn.textContent = "Uploading...";
      status.style.display = "block";
      status.style.color = "var(--text-dim)";
      status.textContent = "Uploading file to server...";

      try {
        const res = await fetch("/api/upload", { method: "POST", body: formData });
        const data = await res.json();

        if (!res.ok) {
          status.style.color = "var(--red)";
          status.textContent = data.error || "Upload failed.";
          btn.disabled = false;
          btn.textContent = "Process";
          return;
        }

        status.style.color = "#059669";
        status.textContent = "Analyzing frames natively (Live View Attached)...";
        form.reset();

        if (calibContainer) calibContainer.style.display = "none";
        player.style.display = "none";
        stream.style.display = "block";
        player.pause();

        const streamInterval = setInterval(async () => {
          try {
            const statusRes = await fetch(`/api/status/${slot}`);
            const statusData = await statusRes.json();

            if (statusData.processing === false) {
              clearInterval(streamInterval);
              status.textContent = "Analysis Complete! Loading finalized video...";
              stream.style.display = "none";
              player.style.display = "block";
              await loadLatestRuns();
              btn.disabled = false;
              btn.textContent = "Process";
            } else {
              const imgBuffer = new Image();
              imgBuffer.onload = () => {
                stream.src = imgBuffer.src;
              };
              imgBuffer.src = `/api/stream/${slot}?t=${Date.now()}`;
            }
          } catch (err) {
            console.warn("Stream ping dropped", err);
          }
        }, 250);
      } catch (err) {
        console.error(err);
        status.style.color = "var(--red)";
        status.textContent = "Network error during upload.";
        btn.disabled = false;
        btn.textContent = "Process";
      }
    });
  }

  function setupCalibration(slot) {
    const fileInput = document.getElementById(`videoInput_${slot}`);
    const container = document.getElementById(`calibrationContainer_${slot}`);
    const canvas = document.getElementById(`calibrationCanvas_${slot}`);
    const hint = document.getElementById(`calibrationHint_${slot}`);
    const btnReset = document.getElementById(`btnReset_${slot}`);
    const entryInput = document.getElementById(`entryLine_${slot}`);
    const exitInput = document.getElementById(`exitLine_${slot}`);
    const btnProcess = document.getElementById(`btn_${slot}`);

    if (!canvas || !fileInput) return;
    const ctx = canvas.getContext("2d");

    let clicks = [];
    let videoWidth = 1920;
    let videoHeight = 1080;
    let previewImage = null;

    function redraw() {
      if (previewImage) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(previewImage, 0, 0, canvas.width, canvas.height);
      }

      ctx.fillStyle = "red";
      ctx.strokeStyle = "#00ff00";
      ctx.lineWidth = 2;

      clicks.forEach((pt, i) => {
        ctx.beginPath();
        ctx.arc(pt.cx, pt.cy, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "white";
        ctx.fillText(i + 1, pt.cx + 8, pt.cy - 8);
        ctx.fillStyle = "red";
      });

      if (clicks.length >= 2) {
        ctx.beginPath();
        ctx.moveTo(clicks[0].cx, clicks[0].cy);
        ctx.lineTo(clicks[1].cx, clicks[1].cy);
        ctx.stroke();
      }
      if (clicks.length === 4) {
        ctx.beginPath();
        ctx.moveTo(clicks[2].cx, clicks[2].cy);
        ctx.lineTo(clicks[3].cx, clicks[3].cy);
        ctx.stroke();
      }
    }

    function clearCalibration() {
      clicks = [];
      entryInput.value = "";
      exitInput.value = "";
      btnProcess.disabled = false;
      hint.textContent = "Set 4 points (1&2=Entry, 3&4=Exit). Click to draw. (Optional)";
      hint.style.color = "#b45309";
      redraw();
    }

    if (btnReset) btnReset.addEventListener("click", clearCalibration);

    canvas.addEventListener("click", (e) => {
      if (clicks.length >= 4) return;
      const rect = canvas.getBoundingClientRect();
      const cx = (e.clientX - rect.left) * (canvas.width / rect.width);
      const cy = (e.clientY - rect.top) * (canvas.height / rect.height);
      const nx = Math.round(cx * (videoWidth / canvas.width));
      const ny = Math.round(cy * (videoHeight / canvas.height));

      clicks.push({ cx, cy, nx, ny });
      redraw();

      if (clicks.length > 0 && clicks.length < 4) {
        btnProcess.disabled = true;
        hint.textContent = `Needs ${4 - clicks.length} more point(s) to form geometries.`;
      } else if (clicks.length === 4) {
        btnProcess.disabled = false;
        hint.textContent = "Geometries captured.";
        hint.style.color = "#059669";
        entryInput.value = `${clicks[0].nx},${clicks[0].ny},${clicks[1].nx},${clicks[1].ny}`;
        exitInput.value = `${clicks[2].nx},${clicks[2].ny},${clicks[3].nx},${clicks[3].ny}`;
      }
    });

    fileInput.addEventListener("change", (e) => {
      if (!e.target.files || !e.target.files[0]) return;
      clearCalibration();
      container.style.display = "block";

      const player = document.getElementById(`player_${slot}`);
      const stream = document.getElementById(`stream_${slot}`);
      if (player) player.style.display = "none";
      if (stream) stream.style.display = "none";

      const fileURL = URL.createObjectURL(e.target.files[0]);
      const tempVid = document.createElement("video");
      tempVid.src = fileURL;
      tempVid.muted = true;
      tempVid.playsInline = true;

      tempVid.onloadedmetadata = () => {
        videoWidth = tempVid.videoWidth || 1920;
        videoHeight = tempVid.videoHeight || 1080;
        canvas.width = 640;
        canvas.height = Math.round(640 * (videoHeight / videoWidth));
        tempVid.currentTime = Math.min(1.0, (tempVid.duration || 1.0) / 2);
      };

      tempVid.onseeked = () => {
        const tempCanvas = document.createElement("canvas");
        tempCanvas.width = canvas.width;
        tempCanvas.height = canvas.height;
        tempCanvas.getContext("2d").drawImage(tempVid, 0, 0, canvas.width, canvas.height);

        previewImage = new Image();
        previewImage.onload = () => redraw();
        previewImage.src = tempCanvas.toDataURL();
        URL.revokeObjectURL(fileURL);
      };
    });
  }

  SLOTS.forEach((slot) => {
    setupUploadForm(slot);
    setupCalibration(slot);
  });

  const btnResetData = document.getElementById("btnResetData");
  if (btnResetData) {
    btnResetData.addEventListener("click", async () => {
      if (confirm("Are you sure you want to permanently clear all event logs, counts, and processed video records?")) {
        btnResetData.textContent = "Clearing...";
        document.querySelectorAll("video").forEach((v) => {
          v.removeAttribute("src");
          v.load();
        });
        await fetch("/api/reset", { method: "POST" });
        window.location.reload();
      }
    });
  }

  checkHealth();
  setInterval(checkHealth, 2000);
  loadLatestRuns();
  setInterval(loadLatestRuns, 10000);
})();
