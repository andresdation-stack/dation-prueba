// Navbar scroll effect
const navbar = document.getElementById('navbar');
if (navbar) {
  window.addEventListener('scroll', () => {
    navbar.classList.toggle('scrolled', window.scrollY > 60);
  });
}

// Mobile nav toggle
const navToggle = document.getElementById('navToggle');
const navLinks  = document.getElementById('navLinks');

if (navToggle && navLinks) {
  navToggle.addEventListener('click', () => {
    const open = navLinks.classList.toggle('open');
    const spans = navToggle.querySelectorAll('span');
    if (open) {
      spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
      spans[1].style.opacity   = '0';
      spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
    } else {
      spans.forEach(s => { s.style.transform = ''; s.style.opacity = ''; });
    }
  });

  navLinks.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => {
      navLinks.classList.remove('open');
      navToggle.querySelectorAll('span').forEach(s => {
        s.style.transform = '';
        s.style.opacity   = '';
      });
    });
  });
}

// Typewriter
const phrases = [
  'Automatización Industrial',
  'Soluciones a Medida',
  'Ingeniería de Vanguardia',
  'Mejora de Procesos',
];
let phraseIndex = 0, charIndex = 0, deleting = false;
const typeEl = document.getElementById('typewriter');

function typewriter() {
  if (!typeEl) return;
  const current = phrases[phraseIndex];
  typeEl.textContent = deleting
    ? current.slice(0, charIndex - 1)
    : current.slice(0, charIndex + 1);

  if (!deleting) {
    charIndex++;
    if (charIndex === current.length) {
      deleting = true;
      setTimeout(typewriter, 2200);
      return;
    }
  } else {
    charIndex--;
    if (charIndex === 0) {
      deleting = false;
      phraseIndex = (phraseIndex + 1) % phrases.length;
    }
  }
  setTimeout(typewriter, deleting ? 55 : 95);
}
typewriter();

// Scroll reveal
const revealEls = document.querySelectorAll('.reveal');
if (revealEls.length) {
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        setTimeout(() => entry.target.classList.add('visible'), i * 90);
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });
  revealEls.forEach(el => revealObserver.observe(el));
}

// Counter animation
function animateCounter(el) {
  const target   = parseInt(el.getAttribute('data-target'));
  const duration = 1800;
  const step     = target / (duration / 16);
  let current    = 0;
  const timer = setInterval(() => {
    current += step;
    if (current >= target) {
      el.textContent = target;
      clearInterval(timer);
    } else {
      el.textContent = Math.floor(current);
    }
  }, 16);
}

const statsSection = document.querySelector('.stats-section');
if (statsSection) {
  const statsObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.querySelectorAll('.stat-number').forEach(animateCounter);
        statsObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.3 });
  statsObserver.observe(statsSection);
}

// Contact form feedback
const contactForm = document.getElementById('contactForm');
if (contactForm) {
  contactForm.addEventListener('submit', function (e) {
    e.preventDefault();
    const btn = this.querySelector('button[type="submit"]');
    const orig = btn.innerHTML;
    btn.textContent = '¡Enviado! Te contactamos pronto.';
    btn.style.background    = '#22c55e';
    btn.style.borderColor   = '#22c55e';
    btn.disabled = true;
    setTimeout(() => {
      btn.innerHTML           = orig;
      btn.style.background    = '';
      btn.style.borderColor   = '';
      btn.disabled = false;
      this.reset();
    }, 3500);
  });
}
