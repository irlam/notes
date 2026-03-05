/* ===== Settings page — Dark mode preference (localStorage) ===== */
const darkKey = 'notes_dark_mode';
const darkToggle = document.getElementById('pref-dark-mode');
if (localStorage.getItem(darkKey) === '1') {
  document.documentElement.setAttribute('data-theme', 'dark');
  darkToggle.checked = true;
}
darkToggle.addEventListener('change', () => {
  if (darkToggle.checked) {
    document.documentElement.setAttribute('data-theme', 'dark');
    localStorage.setItem(darkKey, '1');
  } else {
    document.documentElement.removeAttribute('data-theme');
    localStorage.setItem(darkKey, '0');
  }
});

/* ===== Save email address ===== */
const emailForm = document.getElementById('email-form');
const emailMsg  = document.getElementById('email-msg');
const emailBtn  = document.getElementById('email-btn');

emailForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  emailMsg.textContent = '';
  emailMsg.className = 'form-msg';
  emailBtn.disabled = true;

  const email = document.getElementById('user-email').value.trim();
  try {
    const r = await fetch('/api/settings/email', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email}),
    });
    const data = await r.json();
    if (r.ok) {
      emailMsg.textContent = 'Email address saved.';
      emailMsg.className = 'form-msg ok';
    } else {
      emailMsg.textContent = data.error || 'Failed to save email.';
      emailMsg.className = 'form-msg err';
    }
  } catch {
    emailMsg.textContent = 'Network error. Please try again.';
    emailMsg.className = 'form-msg err';
  } finally {
    emailBtn.disabled = false;
  }
});

/* ===== Change password ===== */
const pwForm = document.getElementById('pw-form');
const pwMsg  = document.getElementById('pw-msg');
const pwBtn  = document.getElementById('pw-btn');

pwForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  pwMsg.textContent = '';
  pwMsg.className = 'form-msg';
  pwBtn.disabled = true;

  const body = {
    current_password: document.getElementById('current-pw').value,
    new_password:     document.getElementById('new-pw').value,
    confirm_password: document.getElementById('confirm-pw').value,
  };

  try {
    const r = await fetch('/api/settings/password', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (r.ok) {
      pwMsg.textContent = 'Password updated successfully.';
      pwMsg.className = 'form-msg ok';
      pwForm.reset();
    } else {
      pwMsg.textContent = data.error || 'Failed to update password.';
      pwMsg.className = 'form-msg err';
    }
  } catch {
    pwMsg.textContent = 'Network error. Please try again.';
    pwMsg.className = 'form-msg err';
  } finally {
    pwBtn.disabled = false;
  }
});
