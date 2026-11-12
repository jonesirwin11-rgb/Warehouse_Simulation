(() => {
  "use strict";

  const barLabelsPlugin = {
    id: "barLabelsPlugin",
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      const dataset = chart.data.datasets[0];
      const meta = chart.getDatasetMeta(0);
      const boxCounts = dataset.boxCounts || [0, 0, 0];

      ctx.save();
      ctx.font = "700 15px Inter, system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      meta.data.forEach((bar, i) => {
        const boxes = boxCounts[i] ?? 0;
        const timeSec = Number(dataset.data[i] || 0).toFixed(1);
        const barHeight = Math.abs(bar.base - bar.y);
        const barWidth = bar.width || 80;
        const line1 = `Boxes: ${boxes}`;
        const line2 = `Time: ${timeSec}s`;

        const fontSize = Math.max(11, Math.min(15, Math.floor((barWidth - 16) / 6.8)));
        ctx.font = `700 ${fontSize}px Inter, system-ui, sans-serif`;

        if (barHeight >= 46 && barWidth >= 78) {
          const midY = bar.y + barHeight / 2;
          const lineOffset = Math.max(8, Math.round(fontSize * 0.72));
          ctx.fillStyle = "#ffffff";
          ctx.fillText(line1, bar.x, midY - lineOffset);
          ctx.fillText(line2, bar.x, midY + lineOffset);
        } else {
          ctx.fillStyle = "#12141c";
          ctx.fillText(line1, bar.x, bar.y - 24);
          ctx.fillText(line2, bar.x, bar.y - 8);
        }
      });

      ctx.restore();
    },
  };

  let trendChart = null;

  function initChart() {
    const ctx = document.getElementById("trendChart").getContext("2d");
    trendChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: ["Trolley 1", "Trolley 2", "Total Truck Time"],
        datasets: [
          {
            label: "Seconds",
            data: [0, 0, 0],
            boxCounts: [0, 0, 0],
            backgroundColor: ["#2563eb", "#0284c7", "#059669"],
            borderRadius: { topLeft: 8, topRight: 8 },
            barPercentage: 0.52,
            categoryPercentage: 0.72,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 28 } },
        scales: {
          x: {
            ticks: { color: "#475569", font: { size: 13, weight: "600" } },
            grid: { display: false },
          },
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: "Turnaround Time (Seconds)",
              color: "#334155",
              font: { size: 12, weight: "600" },
            },
            ticks: {
              color: "#64748b",
              stepSize: 2,
            },
            grid: { color: "rgba(15, 23, 42, 0.06)" },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label(context) {
                const boxes = context.dataset.boxCounts?.[context.dataIndex] ?? 0;
                const sec = Number(context.parsed.y || 0).toFixed(1);
                return `Boxes: ${boxes} | Time: ${sec}s`;
              },
            },
          },
        },
      },
      plugins: [barLabelsPlugin],
    });
  }

  async function refreshAnalysis() {
    try {
      const res = await fetch("/api/analysis");
      const data = await res.json();

      const t1 = data.trolley_1 || { boxes: 0, time_sec: 0 };
      const t2 = data.trolley_2 || { boxes: 0, time_sec: 0 };
      const total = data.total || { boxes: 0, time_sec: 0, tat_formatted: "0m 0s" };

      const maxTime = Math.max(t1.time_sec, t2.time_sec, total.time_sec, 10);
      trendChart.options.scales.y.ticks.stepSize = maxTime > 60 ? Math.ceil(maxTime / 12) : 2;

      trendChart.data.datasets[0].data = [t1.time_sec, t2.time_sec, total.time_sec];
      trendChart.data.datasets[0].boxCounts = [t1.boxes, t2.boxes, total.boxes];
      trendChart.update();

      document.getElementById("tatSummary").textContent = total.tat_formatted || "0m 0s";
      document.getElementById("tatSecondsMeta").textContent =
        `Total elapsed: ${Number(total.time_sec || 0).toFixed(1)}s`;
      document.getElementById("trolley1Summary").textContent = `${t1.boxes ?? 0} Boxes`;
      document.getElementById("trolley1TimeMeta").textContent =
        `Time taken: ${Number(t1.time_sec || 0).toFixed(1)}s`;
      document.getElementById("trolley2Summary").textContent = `${t2.boxes ?? 0} Boxes`;
      document.getElementById("trolley2TimeMeta").textContent =
        `Time taken: ${Number(t2.time_sec || 0).toFixed(1)}s`;
      document.getElementById("truckSummary").textContent = `${total.boxes ?? 0} Boxes`;
    } catch (e) {
      console.error("Failed to fetch analysis data", e);
    }
  }

  initChart();
  refreshAnalysis();
  setInterval(refreshAnalysis, 2000);
})();
