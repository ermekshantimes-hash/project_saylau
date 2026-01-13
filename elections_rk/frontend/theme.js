// Universal theme management for RK Elections

function toggleTheme() {
  const html = document.documentElement;
  const currentTheme = html.getAttribute('data-theme');
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  
  html.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
  
  // Update button icon
  const btn = document.querySelector('.theme-toggle');
  if (btn) {
    btn.textContent = newTheme === 'dark' ? '🌙' : '☀️';
  }
  
  return newTheme;
}

function loadTheme() {
  const savedTheme = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', savedTheme);
  
  const btn = document.querySelector('.theme-toggle');
  if (btn) {
    btn.textContent = savedTheme === 'dark' ? '🌙' : '☀️';
  }
  
  return savedTheme;
}

// Auto-load theme on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadTheme);
} else {
  loadTheme();
}
