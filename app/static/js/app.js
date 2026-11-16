document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form:not([data-async]):not([method="get"])').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (event.defaultPrevented || !form.checkValidity()) return;
      const button = event.submitter || form.querySelector('button[type=submit],button:not([type])');
      // Named submit controls carry form data and must stay enabled until the browser serializes it.
      if (button && !button.name) {
        button.disabled = true;
        button.textContent = 'Please wait…';
      }
    });
  });
});
