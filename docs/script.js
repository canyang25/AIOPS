// ============================================================
// AutoSRE Website — Interactive Enhancements v2
// ============================================================

// ── Hamburger mobile menu ─────────────────────────────────
function initMobileMenu() {
  const btn = document.getElementById('hamburger');
  const menu = document.getElementById('mobile-menu');
  if (!btn || !menu) return;

  btn.addEventListener('click', () => {
    const open = btn.classList.toggle('open');
    menu.classList.toggle('open', open);
  });

  // Close on link click
  menu.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => {
      btn.classList.remove('open');
      menu.classList.remove('open');
    });
  });
}

// ── Nav scroll-spy ────────────────────────────────────────
function initScrollSpy() {
  const navLinks = document.querySelectorAll('.nav-links a[data-section]');
  const sections = Array.from(navLinks).map(a => document.getElementById(a.dataset.section)).filter(Boolean);
  const nav = document.querySelector('nav');

  const onScroll = () => {
    // Scrolled class on nav
    nav.classList.toggle('scrolled', window.scrollY > 60);

    // Active section
    let current = '';
    sections.forEach(section => {
      if (window.scrollY >= section.offsetTop - 140) {
        current = section.id;
      }
    });

    navLinks.forEach(a => a.classList.toggle('active', a.dataset.section === current));
  };

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

// ── Scroll reveal ─────────────────────────────────────────
function initScrollReveal() {
  const observer = new IntersectionObserver(
    (entries) => entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    }),
    { threshold: 0.1, rootMargin: '0px 0px -36px 0px' }
  );

  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
}

// ── Copy to clipboard ─────────────────────────────────────
function initCopyButtons() {
  document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const block = btn.closest('.code-block');
      const code = block.querySelector('code');
      navigator.clipboard.writeText(code.innerText).then(() => {
        btn.classList.add('copied');
        btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg> Copied!`;
        setTimeout(() => {
          btn.classList.remove('copied');
          btn.innerHTML = copyIcon() + ' Copy';
        }, 2000);
      });
    });
  });
}

function copyIcon() {
  return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;
}

// ── Animated terminal typewriter ──────────────────────────
const TERMINAL_SCRIPT = [
  { delay: 0,    type: 'prompt', text: 'python agent.py db' },
  { delay: 800,  type: 'info',   text: '' },
  { delay: 850,  type: 'warn',   text: '[ALERT]  order-service  latency spike detected' },
  { delay: 1100, type: 'info',   text: '         Affected service  : order-service' },
  { delay: 1200, type: 'info',   text: '         Symptom           : p99 latency 200ms -> 1.5s' },
  { delay: 1300, type: 'info',   text: '' },
  { delay: 1400, type: 'accent', text: '-- Step 1 / Gathering signals -------------------------' },
  { delay: 1700, type: 'info',   text: '  Querying Prometheus for order-service metrics...' },
  { delay: 2100, type: 'ok',     text: '  [OK]  db_connections_active  : 98 / 100' },
  { delay: 2300, type: 'ok',     text: '  [OK]  db_connections_waiting : 47' },
  { delay: 2500, type: 'ok',     text: '  [OK]  http_request_duration_p99 : 1487ms' },
  { delay: 2700, type: 'info',   text: '  Searching ELK for recent errors...' },
  { delay: 3100, type: 'ok',     text: '  [OK]  47 entries  "connection pool exhausted"' },
  { delay: 3300, type: 'info',   text: '' },
  { delay: 3400, type: 'accent', text: '-- Step 2 / Diagnosing root cause ---------------------' },
  { delay: 3800, type: 'warn',   text: '  [WARN]  Root cause: DB connection pool saturated' },
  { delay: 4000, type: 'info',   text: '           max_connections=100, all slots exhausted' },
  { delay: 4200, type: 'info',   text: '           Recommendation: restore_db_pool playbook' },
  { delay: 4300, type: 'info',   text: '' },
  { delay: 4400, type: 'accent', text: '-- Step 3 / Remediating ------------------------------' },
  { delay: 4700, type: 'info',   text: '  Executing restore_db_pool.yml via Ansible...' },
  { delay: 5200, type: 'ok',     text: '  [OK]  Pool size increased to 200' },
  { delay: 5400, type: 'ok',     text: '  [OK]  Waiting connections cleared' },
  { delay: 5500, type: 'info',   text: '' },
  { delay: 5600, type: 'accent', text: '-- Step 4 / Verifying recovery -----------------------' },
  { delay: 5900, type: 'ok',     text: '  [OK]  p99 latency: 1487ms -> 78ms' },
  { delay: 6100, type: 'ok',     text: '  [OK]  Incident report saved to reports/' },
  { delay: 6300, type: 'info',   text: '' },
  { delay: 6400, type: 'ok',     text: '[DONE]  Resolution complete in 6.4s' },
];

function initTerminal() {
  const body = document.getElementById('terminal-body');
  if (!body) return;

  function runScript() {
    body.innerHTML = '';
    const cursor = document.createElement('span');
    cursor.className = 'cursor';

    TERMINAL_SCRIPT.forEach(({ delay, type, text }) => {
      setTimeout(() => {
        const line = document.createElement('span');
        line.className = `t-line t-${type}`;

        if (type === 'prompt') {
          line.innerHTML = `<span class="t-prompt">$ </span><span class="t-cmd">${text}</span>`;
        } else {
          line.textContent = text;
        }

        body.appendChild(line);

        // Move cursor to end
        if (body.contains(cursor)) body.removeChild(cursor);
        body.appendChild(cursor);
        body.scrollTop = body.scrollHeight;
      }, delay);
    });

    // Restart loop
    const total = TERMINAL_SCRIPT[TERMINAL_SCRIPT.length - 1].delay;
    setTimeout(runScript, total + 3500);
  }

  runScript();
}

// ── Animated stat counters ────────────────────────────────
function initCounters() {
  const counters = document.querySelectorAll('[data-count]');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      const target = parseInt(el.dataset.count);
      const suffix = el.dataset.suffix || '';
      const duration = 1400;
      const start = performance.now();

      function tick(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(eased * target) + suffix;
        if (progress < 1) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
      observer.unobserve(el);
    });
  }, { threshold: 0.5 });

  counters.forEach(c => observer.observe(c));
}

// ── highlight.js ──────────────────────────────────────────
function initHighlightJS() {
  if (window.hljs) {
    hljs.configure({ ignoreUnescapedHTML: true });
    hljs.highlightAll();
  }
}

// ── Boot ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initMobileMenu();
  initScrollSpy();
  initScrollReveal();
  initHighlightJS();
  initCounters();
  initTerminal();
  setTimeout(initCopyButtons, 150);
});
