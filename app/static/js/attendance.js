document.querySelectorAll('[data-mark-unmarked]').forEach((button) => {
  button.addEventListener('click', () => {
    button.form.querySelectorAll('[data-attendance-status]').forEach((select) => {
      if (!select.value) select.value = 'Present';
    });
  });
});
