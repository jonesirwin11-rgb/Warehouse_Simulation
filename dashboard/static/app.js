(() => {
    "use strict";
  
    const $ = (s) => document.querySelector(s);
  
    const globalStatus = $("#globalStatus");
    // UI variables removed
  
    function toast(msg, type = "info") {
      const el = document.createElement("div");
      el.className = `toast ${type}`;
      el.textContent = msg;
      $("#toastContainer").appendChild(el);
      setTimeout(() => el.remove(), 4500);
    }
  
    function pollInventory() {
        fetch("/api/inventory")
        .then(r => r.json())
        .then(data => {
            // Removed textContent updates for live inventory
            
            const bc1 = document.getElementById('boxCountCam1');
            if(bc1) bc1.textContent = data.truck_exit_events || 0;
            
            const bc2 = document.getElementById('boxCountCam2');
            if(bc2) bc2.textContent = data.staging_arrival_events || 0;
        })
        .catch(e => {
            // silent fail for polling to not spam terminal if disconnected
        });
    }
  
    // Poll every 0.5 seconds for near real-time updates
    setInterval(pollInventory, 500);
    pollInventory(); // initial poll
  
    // Audit button logic removed
  
    // ==========================================
    // Parallel Cameras: Video Review 
    // ==========================================
    async function loadLatestRuns() {
        try {
            const res = await fetch('/api/runs');
            const runs = await res.json();
            
            const cam1Runs = runs.filter(r => r.includes('cam1_')).sort((a,b) => b.localeCompare(a));
            const cam2Runs = runs.filter(r => r.includes('cam2_')).sort((a,b) => b.localeCompare(a));
            
            if (cam1Runs.length > 0) {
               const p1 = document.getElementById('playerCam1');
               const src = `/videos/${cam1Runs[0]}`;
               if (!p1.src.includes(src)) p1.src = src;
            }
            if (cam2Runs.length > 0) {
               const p2 = document.getElementById('playerCam2');
               const src = `/videos/${cam2Runs[0]}`;
               if (!p2.src.includes(src)) p2.src = src;
            }
        } catch(e) {
            console.error("Failed loading runs", e);
        }
    }
    
    function setupUploadForm(cameraId) {
        const form = document.getElementById(`uploadFormCam${cameraId}`);
        const status = document.getElementById(`statusCam${cameraId}`);
        const btn = document.getElementById(`btnCam${cameraId}`);
        const player = document.getElementById(`playerCam${cameraId}`);
        const stream = document.getElementById(`streamCam${cameraId}`);
        
        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(form);
                
                btn.disabled = true;
                btn.textContent = 'Uploading...';
                status.style.display = 'block';
                status.style.color = '#fff';
                status.textContent = 'Uploading file to server...';

                try {
                    const res = await fetch('/api/upload', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await res.json();
                    
                    if (res.ok) {
                        status.style.color = 'var(--success)';
                        status.textContent = 'Analyzing frames natively (Live View Attached)...';
                        form.reset();
                        
                        const calibContainer = document.getElementById(`calibrationContainerCam${cameraId}`);
                        if (calibContainer) calibContainer.style.display = 'none';
                        player.style.display = 'none';
                        stream.style.display = 'block';
                        player.pause();
                        
                        const streamInterval = setInterval(async () => {
                            try {
                                const statusRes = await fetch(`/api/status/${cameraId}`);
                                const statusData = await statusRes.json();
                                
                                if (statusData.processing === false) {
                                    clearInterval(streamInterval);
                                    status.textContent = "Analysis Complete! Loading finalized video...";
                                    stream.style.display = 'none';
                                    player.style.display = 'block';
                                    loadLatestRuns();
                                    
                                    // Unlock button
                                    btn.disabled = false;
                                    btn.textContent = 'Process';
                                } else {
                                    // Buffer Image to prevent flicker glitches
                                    const imgBuffer = new Image();
                                    imgBuffer.onload = () => { stream.src = imgBuffer.src; };
                                    imgBuffer.src = `/api/stream/${cameraId}?t=` + Date.now();
                                }
                            } catch(e) {
                                console.warn("Stream ping dropped", e);
                            }
                        }, 250);
                    } else {
                        status.style.color = '#ff6b6b';
                        status.textContent = data.error || 'Upload failed.';
                        btn.disabled = false;
                        btn.textContent = 'Process';
                    }
                } catch (err) {
                    console.error(err);
                    status.style.color = '#ff6b6b';
                    status.textContent = 'Network error during upload.';
                    btn.disabled = false;
                    btn.textContent = 'Process';
                }
            });
        }
    }

    function setupCalibration(cameraId) {
        const fileInput = document.getElementById(`videoInputCam${cameraId}`);
        const container = document.getElementById(`calibrationContainerCam${cameraId}`);
        const canvas = document.getElementById(`calibrationCanvasCam${cameraId}`);
        const ctx = canvas.getContext('2d');
        const hint = document.getElementById(`calibrationHintCam${cameraId}`);
        const btnReset = document.getElementById(`btnResetCam${cameraId}`);
        const entryInput = document.getElementById(`entryLineCam${cameraId}`);
        const exitInput = document.getElementById(`exitLineCam${cameraId}`);
        const btnProcess = document.getElementById(`btnCam${cameraId}`);
        
        let clicks = [];
        let videoWidth = 1920; 
        let videoHeight = 1080;
        let previewImage = null;
        
        function redraw() {
            if (previewImage) {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(previewImage, 0, 0, canvas.width, canvas.height);
            }
            
            ctx.fillStyle = 'red';
            ctx.strokeStyle = '#00ff00';
            ctx.lineWidth = 2;
            
            clicks.forEach((pt, i) => {
                ctx.beginPath();
                ctx.arc(pt.cx, pt.cy, 5, 0, Math.PI*2);
                ctx.fill();
                
                ctx.fillStyle = 'white';
                ctx.fillText(i+1, pt.cx+8, pt.cy-8);
                ctx.fillStyle = 'red';
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
            hint.style.color = "var(--warning)";
            redraw();
        }
        
        if (btnReset) {
            btnReset.addEventListener('click', clearCalibration);
        }
        
        if (canvas) {
            canvas.addEventListener('click', (e) => {
                if (clicks.length >= 4) return;
                
                const rect = canvas.getBoundingClientRect();
                // Scale the physical click (rect) up to the internal canvas dimensions (800x640 etc)
                const cx = (e.clientX - rect.left) * (canvas.width / rect.width);
                const cy = (e.clientY - rect.top) * (canvas.height / rect.height);
                
                const scaleX = videoWidth / canvas.width;
                const scaleY = videoHeight / canvas.height;
                const nx = Math.round(cx * scaleX);
                const ny = Math.round(cy * scaleY);
                
                clicks.push({cx, cy, nx, ny});
                redraw();
                
                if (clicks.length > 0 && clicks.length < 4) {
                    btnProcess.disabled = true;
                    hint.textContent = `Needs ${4 - clicks.length} more point(s) to form geometries.`;
                }
                
                if (clicks.length === 4) {
                    btnProcess.disabled = false;
                    hint.textContent = "Geometries captured.";
                    hint.style.color = "var(--success)";
                    
                    entryInput.value = `${clicks[0].nx},${clicks[0].ny},${clicks[1].nx},${clicks[1].ny}`;
                    exitInput.value = `${clicks[2].nx},${clicks[2].ny},${clicks[3].nx},${clicks[3].ny}`;
                }
            });
        }

        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                if (!e.target.files || !e.target.files[0]) return;
                
                clearCalibration();
                container.style.display = 'block';
                
                // Keep UI clean, hide other media streams while annotating initially
                const player = document.getElementById(`playerCam${cameraId}`);
                const stream = document.getElementById(`streamCam${cameraId}`);
                if (player) player.style.display = 'none';
                if (stream) stream.style.display = 'none';
                
                const file = e.target.files[0];
                const fileURL = URL.createObjectURL(file);
                
                const tempVid = document.createElement('video');
                tempVid.src = fileURL;
                tempVid.muted = true;
                tempVid.playsInline = true;
                
                tempVid.onloadedmetadata = () => {
                    videoWidth = tempVid.videoWidth || 1920;
                    videoHeight = tempVid.videoHeight || 1080;
                    canvas.width = 640;
                    canvas.height = Math.round(640 * (videoHeight / videoWidth));
                    tempVid.currentTime = 1.0; 
                };
                
                tempVid.onseeked = () => {
                    const tempCanvas = document.createElement('canvas');
                    tempCanvas.width = canvas.width;
                    tempCanvas.height = canvas.height;
                    const tCtx = tempCanvas.getContext('2d');
                    tCtx.drawImage(tempVid, 0, 0, canvas.width, canvas.height);
                    
                    previewImage = new Image();
                    previewImage.onload = () => { redraw(); };
                    previewImage.src = tempCanvas.toDataURL();
                };
            });
        }
    }

    setupUploadForm(1);
    setupUploadForm(2);
    
    setupCalibration(1);
    setupCalibration(2);
    
    const btnResetData = document.getElementById('btnResetData');
    if (btnResetData) {
        btnResetData.addEventListener('click', async () => {
            if (confirm("Are you sure you want to permanently clear all event logs, counts, and processed video records?")) {
                btnResetData.textContent = "Clearing...";
                
                // Break Windows file-locks before asking backend to delete
                document.querySelectorAll('video').forEach(v => {
                    v.removeAttribute('src');
                    v.load();
                });
                
                await fetch('/api/reset', { method: 'POST' });
                window.location.reload();
            }
        });
    }
    
    // Fetch once
    loadLatestRuns();
    // Refresh periodically
    setInterval(loadLatestRuns, 10000);

    // ==========================================
    // Trend Analysis Chart
    // ==========================================
    let trendChart = null;

    function initTrendChart() {
        const ctx = document.getElementById('trendChart').getContext('2d');
        trendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Dock View (Truck Exit)',
                        data: [],
                        borderColor: '#a855f7',
                        backgroundColor: 'rgba(168, 85, 247, 0.2)',
                        fill: true,
                        tension: 0.3
                    },
                    {
                        label: 'Side View (Staging)',
                        data: [],
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.2)',
                        fill: true,
                        tension: 0.3
                    },
                    {
                        label: 'Total Count',
                        data: [],
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.2)',
                        fill: false,
                        borderDash: [5, 5],
                        borderWidth: 3,
                        tension: 0.3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        ticks: { color: 'rgba(0, 0, 0, 0.7)' },
                        grid: { color: 'rgba(0, 0, 0, 0.1)' }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: 'rgba(0, 0, 0, 0.7)', stepSize: 2 },
                        grid: { color: 'rgba(0, 0, 0, 0.1)' }
                    }
                },
                plugins: {
                    legend: { labels: { color: 'rgba(0, 0, 0, 0.9)' } }
                }
            }
        });
    }

    async function updateTrendChartData() {
        try {
            const res = await fetch('/api/events/log');
            let events = await res.json();
            
            // Events are returned DESC (newest first). Let's sort ASC (oldest first).
            events.reverse();

            const labels = [];
            const dataCam1 = [];
            const dataCam2 = [];
            const dataTotal = [];

            let cumCam1 = 0;
            let cumCam2 = 0;
            let cumTotal = 0;

            if(events.length === 0) {
                if (trendChart) {
                    trendChart.data.labels = [];
                    trendChart.data.datasets[0].data = [];
                    trendChart.data.datasets[1].data = [];
                    trendChart.data.datasets[2].data = [];
                    trendChart.update();
                }
                return;
            }

            events.forEach(ev => {
                const date = new Date(ev.received_at + " UTC");
                labels.push(date.toLocaleTimeString());

                if (ev.event_type === "TRUCK_EXIT_EVENT") {
                    cumCam1 += ev.quantity;
                } else if (ev.event_type === "STAGING_ARRIVAL_EVENT") {
                    cumCam2 += ev.quantity;
                }
                cumTotal = cumCam1 + cumCam2;

                dataCam1.push(cumCam1);
                dataCam2.push(cumCam2);
                dataTotal.push(cumTotal);
            });

            if (trendChart) {
                trendChart.data.labels = labels;
                trendChart.data.datasets[0].data = dataCam1;
                trendChart.data.datasets[1].data = dataCam2;
                trendChart.data.datasets[2].data = dataTotal;
                trendChart.update();
            }
        } catch (e) {
            console.error("Failed to load trend data", e);
        }
    }

    // Initialize and periodically poll trend metrics mapping directly to canvas
    initTrendChart();
    setInterval(updateTrendChartData, 2000);
    updateTrendChartData();

  })();
