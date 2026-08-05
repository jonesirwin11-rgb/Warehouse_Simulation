/* ═══════════════════════════════════════════════════════════════════════
   Warehouse Vision AI — Dashboard JS
   ═══════════════════════════════════════════════════════════════════════ */
(() => {
  "use strict";

  // ── DOM Refs ──────────────────────────────────────────────────────
  const $ = (s) => document.querySelector(s);

  const uploadZone     = $("#uploadZone");
  const videoInput     = $("#videoInput");
  const uploadProgress = $("#uploadProgress");
  const uploadFileName = $("#uploadFileName");
  const uploadBar      = $("#uploadBar");
  const uploadLabel    = $("#uploadLabel");

  const step1Section = $("#step1Section");
  const step2Section = $("#step2Section");
  const step3Section = $("#step3Section");

  const canvas        = $("#frameCanvas");
  const ctx           = canvas.getContext("2d");
  const canvasOverlay = $("#canvasOverlay");
  const coordAVal     = $("#coordAVal");
  const coordBVal     = $("#coordBVal");
  const coordA        = $("#coordA");
  const coordB        = $("#coordB");
  const resetLineBtn  = $("#resetLineBtn");
  const processBtn    = $("#processBtn");

  const processingView = $("#processingView");
  const resultsView    = $("#resultsView");
  const processingMsg  = $("#processingMsg");
  const processBar     = $("#processBar");
  const processPercent = $("#processPercent");

  const statLoaded         = $("#statLoaded");
  const statUnloaded       = $("#statUnloaded");
  const statLoadSessions   = $("#statLoadSessions");
  const statUnloadSessions = $("#statUnloadSessions");
  const resultVideo        = $("#resultVideo");
  const downloadVideoBtn   = $("#downloadVideoBtn");
  const downloadReportBtn  = $("#downloadReportBtn");
  const newSessionBtn      = $("#newSessionBtn");

  const globalStatus = $("#globalStatus");

  // ── State ─────────────────────────────────────────────────────────
  let jobId          = null;
  let videoFilename  = null;
  let videoWidth     = 0;
  let videoHeight    = 0;
  let frameImg       = null;
  let points         = []; // [{x,y}, {x,y}]  — in VIDEO coords
  let pollTimer      = null;

  // ── Helpers ───────────────────────────────────────────────────────
  function toast(msg, type = "info") {
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = msg;
    $("#toastContainer").appendChild(el);
    setTimeout(() => el.remove(), 4500);
  }

  function setGlobalStatus(text, cls = "") {
    $(".status-text").textContent = text;
    globalStatus.className = "status-chip " + cls;
  }

  function enableStep(section) {
    section.classList.remove("disabled");
  }
  function disableStep(section) {
    section.classList.add("disabled");
  }

  // ── Upload ────────────────────────────────────────────────────────
  // Click
  uploadZone.addEventListener("click", () => videoInput.click());

  // Drag & drop
  uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.classList.add("dragover");
  });
  uploadZone.addEventListener("dragleave", () => {
    uploadZone.classList.remove("dragover");
  });
  uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
  });

  videoInput.addEventListener("change", () => {
    if (videoInput.files.length) handleFile(videoInput.files[0]);
  });

  function handleFile(file) {
    if (!file.type.startsWith("video/")) {
      toast("Please select a valid video file.", "error");
      return;
    }

    uploadFileName.textContent = file.name;
    uploadZone.style.display = "none";
    uploadProgress.style.display = "flex";
    uploadBar.style.width = "0%";
    uploadLabel.textContent = "Uploading…";
    setGlobalStatus("Uploading…", "running");

    const fd = new FormData();
    fd.append("video", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/upload");

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        uploadBar.style.width = pct + "%";
        uploadLabel.textContent = `Uploading… ${pct}%`;
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status === 200) {
        const data = JSON.parse(xhr.responseText);
        jobId         = data.job_id;
        videoFilename = data.video_filename;
        videoWidth    = data.video_width;
        videoHeight   = data.video_height;

        uploadBar.style.width = "100%";
        uploadLabel.textContent = "Upload complete ✓";
        setGlobalStatus("Ready", "");
        toast("Video uploaded — select your tripwire line", "success");

        loadFrame(data.frame_url);
        enableStep(step2Section);
      } else {
        const err = JSON.parse(xhr.responseText);
        toast(err.error || "Upload failed", "error");
        resetUploadUI();
        setGlobalStatus("Error", "error");
      }
    });

    xhr.addEventListener("error", () => {
      toast("Network error during upload", "error");
      resetUploadUI();
      setGlobalStatus("Error", "error");
    });

    xhr.send(fd);
  }

  function resetUploadUI() {
    uploadZone.style.display = "";
    uploadProgress.style.display = "none";
  }

  // ── Frame & Canvas ────────────────────────────────────────────────
  function loadFrame(url) {
    frameImg = new Image();
    frameImg.onload = () => {
      canvas.width  = frameImg.naturalWidth;
      canvas.height = frameImg.naturalHeight;
      canvasOverlay.style.display = "none";
      drawScene();
    };
    frameImg.src = url;
  }

  function drawScene() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(frameImg, 0, 0);

    // Draw existing points & line
    points.forEach((p, i) => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, 7, 0, Math.PI * 2);
      ctx.fillStyle = i === 0 ? "#00cec9" : "#ff6b6b";
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#fff";
      ctx.stroke();

      // Label
      ctx.font = "bold 13px Inter, sans-serif";
      ctx.fillStyle = "#fff";
      ctx.fillText(i === 0 ? "START" : "END", p.x + 12, p.y + 5);
    });

    if (points.length === 2) {
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      ctx.lineTo(points[1].x, points[1].y);
      ctx.strokeStyle = "rgba(0,206,201,.85)";
      ctx.lineWidth = 3;
      ctx.setLineDash([8, 6]);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  // Canvas clicks → video coordinates
  canvas.addEventListener("click", (e) => {
    if (points.length >= 2) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const vx = Math.round((e.clientX - rect.left) * scaleX);
    const vy = Math.round((e.clientY - rect.top) * scaleY);

    points.push({ x: vx, y: vy });
    drawScene();

    if (points.length === 1) {
      coordAVal.textContent = `(${vx}, ${vy})`;
      coordA.classList.add("set");
      resetLineBtn.disabled = false;
      toast("Start point set — click the second point", "info");
    }
    if (points.length === 2) {
      coordBVal.textContent = `(${vx}, ${vy})`;
      coordB.classList.add("set");
      processBtn.disabled = false;
      toast("Line defined! Hit Process Video when ready.", "success");
    }
  });

  // Canvas hover cursor feedback
  canvas.addEventListener("mousemove", (e) => {
    if (points.length >= 2) {
      canvas.style.cursor = "default";
    } else {
      canvas.style.cursor = "crosshair";
    }
  });

  // Reset
  resetLineBtn.addEventListener("click", () => {
    points = [];
    coordAVal.textContent = "—";
    coordBVal.textContent = "—";
    coordA.classList.remove("set");
    coordB.classList.remove("set");
    processBtn.disabled = true;
    drawScene();
    toast("Line reset — click two new points", "info");
  });

  // ── Process ───────────────────────────────────────────────────────
  processBtn.addEventListener("click", () => {
    if (points.length < 2) return;

    // Disable step 2, enable step 3
    disableStep(step2Section);
    enableStep(step3Section);
    processingView.style.display = "";
    resultsView.style.display = "none";
    processBar.style.width = "0%";
    processPercent.textContent = "0 %";
    processingMsg.textContent = "Sending to server…";
    setGlobalStatus("Processing…", "running");

    fetch("/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: jobId,
        video_filename: videoFilename,
        line_start: points[0],
        line_end: points[1],
      }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.error) {
          toast(data.error, "error");
          setGlobalStatus("Error", "error");
          return;
        }
        // Start polling
        pollTimer = setInterval(pollStatus, 1500);
      })
      .catch(() => {
        toast("Failed to start processing", "error");
        setGlobalStatus("Error", "error");
      });
  });

  function pollStatus() {
    fetch(`/status/${jobId}`)
      .then((r) => r.json())
      .then((job) => {
        processingMsg.textContent = job.message;
        processBar.style.width = job.progress + "%";
        processPercent.textContent = job.progress + " %";

        if (job.status === "done") {
          clearInterval(pollTimer);
          showResults(job);
        } else if (job.status === "error") {
          clearInterval(pollTimer);
          toast("Processing error: " + job.message, "error");
          setGlobalStatus("Error", "error");
        }
      })
      .catch(() => {}); // swallow transient network hiccups
  }

  // ── Results ───────────────────────────────────────────────────────
  function showResults(job) {
    processingView.style.display = "none";
    resultsView.style.display = "";
    setGlobalStatus("Complete", "");

    const s = job.summary || {};
    animateNumber(statLoaded, s.total_loaded || 0);
    animateNumber(statUnloaded, s.total_unloaded || 0);
    animateNumber(statLoadSessions, s.load_sessions || 0);
    animateNumber(statUnloadSessions, s.unload_sessions || 0);

    resultVideo.src = job.output_video;
    downloadVideoBtn.href = job.output_video;

    if (job.report_csv) {
      downloadReportBtn.href = job.report_csv;
      downloadReportBtn.style.display = "";
    } else {
      downloadReportBtn.style.display = "none";
    }

    toast("Processing complete — review your results!", "success");

    // Smooth scroll
    step3Section.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function animateNumber(el, target) {
    let current = 0;
    const step = Math.max(1, Math.ceil(target / 30));
    const interval = setInterval(() => {
      current += step;
      if (current >= target) {
        current = target;
        clearInterval(interval);
      }
      el.textContent = current;
    }, 30);
  }

  // ── New Session ─────────────────────────────────────────────────
  newSessionBtn.addEventListener("click", () => {
    // Reset everything
    jobId = null;
    videoFilename = null;
    points = [];
    clearInterval(pollTimer);

    resetUploadUI();
    videoInput.value = "";

    coordAVal.textContent = "—";
    coordBVal.textContent = "—";
    coordA.classList.remove("set");
    coordB.classList.remove("set");
    processBtn.disabled = true;
    resetLineBtn.disabled = true;

    canvasOverlay.style.display = "";
    processingView.style.display = "";
    resultsView.style.display = "none";

    disableStep(step2Section);
    disableStep(step3Section);
    setGlobalStatus("Ready", "");

    step1Section.scrollIntoView({ behavior: "smooth", block: "start" });
    toast("Session reset — upload a new video to begin", "info");
  });
})();
