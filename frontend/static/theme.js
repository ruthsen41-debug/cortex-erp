// Cortex ERP - comportamento do tema: título da página, padrões do Chart.js e ícone do tema.
(function () {
  function applyChartDefaults() {
    if (!window.Chart) return;
    const dark = document.documentElement.classList.contains('dark');
    Chart.defaults.color = dark ? '#8d97c4' : '#6b7280';
    Chart.defaults.borderColor = dark ? 'rgba(129,140,248,.10)' : 'rgba(229,231,235,1)';
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.tooltip.backgroundColor = dark ? 'rgba(8,12,28,.94)' : '#fff';
    Chart.defaults.plugins.tooltip.borderColor = dark ? 'rgba(129,140,248,.4)' : '#e5e7eb';
    Chart.defaults.plugins.tooltip.titleColor = dark ? '#e9edff' : '#111827';
    Chart.defaults.plugins.tooltip.bodyColor = dark ? '#8d97c4' : '#6b7280';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 10;
  }

  function syncThemeIcon() {
    const dark = document.documentElement.classList.contains('dark');
    document.querySelectorAll('button[onclick="toggleDarkMode()"] [data-lucide], button[onclick="toggleDarkMode()"] svg').forEach((el) => {
      const holder = el.closest('button');
      if (!holder) return;
      holder.innerHTML = `<i data-lucide="${dark ? 'moon' : 'sun'}" class="w-4 h-4"></i>`;
    });
    if (window.lucide) lucide.createIcons();
    applyChartDefaults();
  }

  // Título e chip de área de cada módulo agora vêm do launcher.js.
  const origToggle = window.toggleDarkMode;
  if (typeof origToggle === 'function') {
    window.toggleDarkMode = function () {
      const r = origToggle.apply(this, arguments);
      syncThemeIcon();
      return r;
    };
  }

  applyChartDefaults();
  document.addEventListener('DOMContentLoaded', () => {
    syncThemeIcon();
  });
})();
