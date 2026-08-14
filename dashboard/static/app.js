(() => {
    "use strict";
  
    const $ = (s) => document.querySelector(s);
  
    const globalStatus = $("#globalStatus");
    const liveInventoryCount = $("#liveInventoryCount");
    const truckExitEvents = $("#truckExitEvents");
    const stagingArrivalEvents = $("#stagingArrivalEvents");
    const btnAudit = $("#btnAudit");
    
    const auditResult = $("#auditResult");
    const auditStatusTitle = $("#auditStatusTitle");
    const auditDesc = $("#auditDesc");
    const auditLiveCount = $("#auditLiveCount");
    const auditEstimateCount = $("#auditEstimateCount");
    const auditDifference = $("#auditDifference");
  
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
            liveInventoryCount.textContent = data.staged_boxes || 0;
            truckExitEvents.textContent = data.truck_exit_events || 0;
            stagingArrivalEvents.textContent = data.staging_arrival_events || 0;
        })
        .catch(e => {
            // silent fail for polling to not spam terminal if disconnected
        });
    }
  
    // Poll every 0.5 seconds for near real-time updates
    setInterval(pollInventory, 500);
    pollInventory(); // initial poll
  
    btnAudit.addEventListener("click", () => {
        btnAudit.disabled = true;
        btnAudit.innerHTML = "Auditing...";
        
        fetch("/api/audit", {
            method: "POST"
        })
        .then(r => r.json())
        .then(data => {
            btnAudit.disabled = false;
            btnAudit.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Initiate Static Stack Audit`;
            
            if (data.error) {
                toast(data.error, "error");
                return;
            }
            
            auditResult.style.display = "block";
            
            auditLiveCount.textContent = data.live_count;
            auditEstimateCount.textContent = data.audit_count;
            auditDifference.textContent = data.difference;
            
            if (data.status === "PASS") {
                auditResult.className = "audit-result-card pass";
                auditStatusTitle.className = "status-large pass-text";
                auditStatusTitle.textContent = "✓ PASS";
                auditDesc.textContent = "Inventory appears consistent.";
                toast("Audit passed!", "success");
            } else {
                auditResult.className = "audit-result-card warning";
                auditStatusTitle.className = "status-large warning-text";
                auditStatusTitle.textContent = "⚠ WARNING";
                auditDesc.textContent = "Inventory discrepancy detected. Investigation required.";
                toast("Audit raised a warning!", "error");
            }
        })
        .catch(e => {
            btnAudit.disabled = false;
            btnAudit.innerHTML = "Initiate Static Stack Audit";
            toast("Failed to reach audit API", "error");
        });
    });
  
  })();
