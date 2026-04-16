/**
 * App initialization, navigation, scroll triggers, and section reveals.
 */

document.addEventListener('DOMContentLoaded', () => {
  // ── Smooth scroll nav ──
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      const target = document.querySelector(link.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // ── Nav background on scroll ──
  const nav = document.querySelector('.site-nav');
  if (nav) {
    window.addEventListener('scroll', () => {
      nav.classList.toggle('scrolled', window.scrollY > 60);
    }, { passive: true });
  }

  // ── Intersection Observer for section reveals ──
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

  document.querySelectorAll('.reveal-on-scroll').forEach(el => {
    revealObserver.observe(el);
  });

  // ── Initialize Mermaid ──
  if (window.mermaid) {
    mermaid.initialize({
      startOnLoad: true,
      theme: 'dark',
      themeVariables: {
        darkMode: true,
        background: '#0d0d0d',
        primaryColor: '#1a3a2a',
        primaryTextColor: '#e0e0e0',
        primaryBorderColor: '#00ff88',
        lineColor: '#00ff88',
        secondaryColor: '#1a1a2e',
        tertiaryColor: '#0d0d0d',
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: '13px',
        nodeTextColor: '#e0e0e0'
      },
      flowchart: {
        useMaxWidth: true,
        htmlLabels: true,
        curve: 'basis'
      }
    });
  }

  // ── Game simulation — auto-play on scroll ──
  const sim = new GameSimulation();

  const simSection = document.getElementById('simulation');
  if (simSection) {
    const simObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && !sim.hasStarted) {
          simObserver.disconnect();
          setTimeout(() => sim.startIfVisible(), 600);
        }
      });
    }, { threshold: 0.25 });
    simObserver.observe(simSection);
  }

  // ── Skill category filter highlights ──
  document.querySelectorAll('.skill-row').forEach(row => {
    row.addEventListener('mouseenter', () => {
      const cat = row.dataset.category;
      document.querySelectorAll(`.skill-row[data-category="${cat}"]`).forEach(r => {
        r.classList.add('category-highlight');
      });
    });
    row.addEventListener('mouseleave', () => {
      document.querySelectorAll('.skill-row').forEach(r => {
        r.classList.remove('category-highlight');
      });
    });
  });

  // ── Populate skills tables ──
  _populateSkills('red-skills-body', RED_SKILLS, 'red');
  _populateSkills('blue-skills-body', BLUE_SKILLS, 'blue');
  _populateScoring('scoring-body');

  // ── Build kill chain UI ──
  _buildKillChain();

  // ── Staggered hero animation ──
  const heroEls = document.querySelectorAll('.hero-stagger');
  heroEls.forEach((el, i) => {
    el.style.animationDelay = `${i * 0.15 + 0.3}s`;
  });
});

function _populateSkills(tbodyId, skills, team) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;

  skills.forEach(s => {
    const tr = document.createElement('tr');
    tr.className = `skill-row ${team}`;
    tr.dataset.category = s.category;
    tr.innerHTML = `
      <td><code>${s.skill}</code></td>
      <td><span class="cat-badge cat-${s.category.toLowerCase()}">${s.category}</span></td>
      <td>${s.description}</td>
    `;
    tbody.appendChild(tr);
  });
}

function _populateScoring(tbodyId) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;

  SCORING_TABLE.forEach(s => {
    const tr = document.createElement('tr');
    const teamClass = s.team.toLowerCase();
    tr.innerHTML = `
      <td><code>${s.event}</code></td>
      <td class="score-val ${teamClass}">${s.points}</td>
      <td><span class="team-label ${teamClass}">${s.team}</span></td>
      <td>${s.description}</td>
    `;
    tbody.appendChild(tr);
  });
}

function _buildKillChain() {
  const container = document.getElementById('kill-chain');
  if (!container) return;

  KILL_CHAIN_STAGES.forEach((stage, i) => {
    const node = document.createElement('div');
    node.className = 'kc-node';
    node.id = `kc-${stage.id}`;
    node.innerHTML = `
      <div class="kc-icon">${stage.icon}</div>
      <div class="kc-label">${stage.label}</div>
      <div class="kc-check">&#10003;</div>
    `;
    container.appendChild(node);

    if (i < KILL_CHAIN_STAGES.length - 1) {
      const arrow = document.createElement('div');
      arrow.className = 'kc-arrow';
      arrow.textContent = '\u25B6';
      container.appendChild(arrow);
    }
  });
}
