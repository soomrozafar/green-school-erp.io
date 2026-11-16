const sidebarToggle = document.querySelector('#sidebarToggle');
const sidebar = document.querySelector('#workspaceNav');
if (sidebarToggle && sidebar) {
  const closeSidebar = () => {
    sidebar.classList.remove('show-mobile');
    sidebarToggle.setAttribute('aria-expanded', 'false');
  };
  sidebarToggle.addEventListener('click', () => {
    sidebarToggle.setAttribute('aria-expanded', String(sidebar.classList.toggle('show-mobile')));
  });
  document.addEventListener('click', (event) => {
    if (!sidebar.contains(event.target) && !sidebarToggle.contains(event.target)) closeSidebar();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebar.classList.contains('show-mobile')) {
      closeSidebar();
      sidebarToggle.focus();
    }
  });
}

const compactToggle = document.querySelector('#sidebarCompactToggle');
if (sidebar && compactToggle) {
  const desktop = window.matchMedia('(min-width: 768px)');
  const key = 'erp-sidebar:' + sidebar.dataset.scrollKey;
  const read = (name) => {
    try { return sessionStorage.getItem(key + ':' + name); } catch { return null; }
  };
  const save = (name, value) => {
    try { sessionStorage.setItem(key + ':' + name, value); } catch { /* storage unavailable */ }
  };
  const scrollKey = () => !desktop.matches ? 'mobile' :
    sidebar.classList.contains('is-compact') ? 'compact' : 'expanded';
  const findActive = () => sidebar.querySelector('[aria-current="page"]') ||
    [...sidebar.querySelectorAll('a[href]')].find(link => link.pathname === window.location.pathname);
  const revealActive = () => {
    if (!sidebar.clientHeight) return;
    const active = findActive();
    if (!active) return;
    const viewport = sidebar.getBoundingClientRect();
    const item = active.getBoundingClientRect();
    if (item.top < viewport.top) sidebar.scrollTop += item.top - viewport.top - 8;
    else if (item.bottom > viewport.bottom) sidebar.scrollTop += item.bottom - viewport.bottom + 8;
  };
  const restore = () => {
    sidebar.scrollTop = Number(read(scrollKey())) || 0;
    revealActive();
  };
  const setCompact = (compact) => {
    sidebar.classList.toggle('is-compact', compact);
    const label = compact ? 'Expand navigation' : 'Collapse navigation';
    compactToggle.setAttribute('aria-label', label);
    compactToggle.title = label;
    compactToggle.setAttribute('aria-expanded', String(!compact));
  };
  setCompact(read('preference') === 'compact');
  restore();
  window.addEventListener('pageshow', restore);
  desktop.addEventListener('change', restore);
  sidebarToggle?.addEventListener('click', () => {
    if (sidebar.classList.contains('show-mobile')) restore();
  });
  sidebar.addEventListener('scroll', () => {
    if (desktop.matches || sidebar.classList.contains('show-mobile')) save(scrollKey(), sidebar.scrollTop);
  }, {passive: true});
  sidebar.addEventListener('click', (event) => {
    if (event.target.closest('a')) save(scrollKey(), sidebar.scrollTop);
  });
  compactToggle.addEventListener('click', () => {
    save(scrollKey(), sidebar.scrollTop);
    setCompact(!sidebar.classList.contains('is-compact'));
    save('preference', scrollKey());
    restore();
  });
}

document.querySelectorAll('form[data-live-search]').forEach((form) => {
  const searchInput = form.elements.q;
  const searchResults = document.getElementById(searchInput.getAttribute('aria-controls'));
  if (!searchResults) return;
  const directory = form.dataset.liveSearch === 'directory';
  let timer;
  let revision = 0;
  let pending;
  function closeSearch() {
    ++revision;
    pending?.abort();
    clearTimeout(timer);
    searchResults.classList.remove('show');
  }
  function showResults(data, message) {
    const links = [
      ...data.students.map((row) => [form.dataset.students, row.name, row.admission_no, row.admission_no]),
      ...data.employees.map((row) => [form.dataset.employees, row.name, row.employee_no, row.employee_no]),
      ...data.invoices.map((row) => [form.dataset.invoices, row.invoice_no, row.status, row.invoice_no]),
      ...(data.records || []).map((row) => [row.url, row.name, row.detail]),
    ];
    searchResults.replaceChildren();
    for (const [path, label, detail, query] of links) {
      const destination = new URL(path, location.origin);
      if (query) destination.searchParams.set('q', query);
      if (directory) {
        for (const key of ['status', 'incomplete']) {
          const value = form.elements[key]?.value;
          if (value) destination.searchParams.set(key, value);
        }
      }
      const link = document.createElement('a');
      const extra = document.createElement('small');
      link.href = destination;
      link.textContent = label;
      extra.textContent = detail;
      link.append(extra);
      searchResults.append(link);
    }
    if (!links.length) {
      const status = document.createElement('p');
      status.className = 'empty mb-0';
      status.textContent = message;
      searchResults.append(status);
    }
    searchResults.classList.add('show');
  }
  async function search() {
    const query = searchInput.value.trim();
    const current = ++revision;
    if (!query) {
      closeSearch();
      return;
    }
    try {
      const url = new URL(form.action);
      url.searchParams.set('q', query);
      if (directory) {
        url.searchParams.set('suggest', '1');
        for (const key of ['status', 'incomplete']) {
          const value = form.elements[key]?.value;
          if (value) url.searchParams.set(key, value);
        }
      } else {
        url.searchParams.set('scope', 'workspace');
      }
      pending?.abort();
      pending = new AbortController();
      const response = await fetch(url, {signal: pending.signal});
      if (!response.ok) throw new Error('Search failed');
      const data = await response.json();
      if (current === revision) showResults(data, 'No matching records.');
    } catch {
      if (current === revision) showResults({students: [], employees: [], invoices: []}, 'Search is unavailable. Please try again.');
    }
  }
  searchInput.addEventListener('input', () => {
    closeSearch();
    timer = setTimeout(search, 160);
  });
  form.elements.status?.addEventListener('change', closeSearch);
  form.addEventListener('submit', (event) => {
    if (directory) return;
    event.preventDefault();
    clearTimeout(timer);
    search();
  });
  form.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeSearch();
      searchInput.focus();
    }
  });
  document.addEventListener('click', (event) => {
    if (!form.contains(event.target)) closeSearch();
  });
});

const assistant = document.querySelector('#erpAssistant');
if (assistant) {
  const form = assistant.querySelector('form');
  const question = form.elements.question;
  const exchange = assistant.querySelector('#assistantExchange');
  const asked = assistant.querySelector('#assistantAsked');
  const answer = assistant.querySelector('#assistantAnswer');
  const body = assistant.querySelector('.assistant-body');
  const submit = form.querySelector('[type="submit"]');
  const prompts = [...assistant.querySelectorAll('[data-assistant-prompt]')];

  function showAnswer(message, actions = [], source) {
    const paragraph = document.createElement('p');
    paragraph.textContent = message;
    answer.replaceChildren();
    if (source === 'ollama' || source === 'builtin') {
      const label = document.createElement('small');
      label.textContent = source === 'ollama' ? 'Matched by Ollama' : 'Built-in command';
      answer.append(label);
    }
    answer.append(paragraph);
    if (actions.length) {
      const links = document.createElement('div');
      links.className = 'assistant-links';
      for (const action of actions) {
        const link = document.createElement('a');
        link.href = action.url;
        link.textContent = action.label;
        links.append(link);
      }
      answer.append(links);
    }
    exchange.hidden = false;
    if (assistant.open) exchange.scrollIntoView({block: 'nearest'});
  }

  const history = assistant.querySelector('.assistant-history');
  const overview = assistant.querySelector('.assistant-overview');
  let overviewRequest = false;

  function overviewItem(title, message, suggestion, action) {
    const card = document.createElement('article');
    const heading = document.createElement('h4');
    heading.textContent = title;
    const text = document.createElement('p');
    text.textContent = message;
    card.append(heading, text);
    if (suggestion) {
      const hint = document.createElement('p');
      hint.className = 'assistant-hint';
      hint.textContent = suggestion;
      const link = document.createElement('a');
      link.href = action.url;
      link.textContent = action.label;
      card.append(hint, link);
    }
    return card;
  }

  async function loadOverview() {
    if (overviewRequest) return;
    overviewRequest = true;
    overview.textContent = 'Loading alerts…';
    try {
      const response = await fetch(assistant.dataset.overviewUrl);
      if (!response.ok || response.redirected) throw new Error('Overview unavailable');
      const {cards, notices} = await response.json();
      const content = document.createDocumentFragment();
      for (const [label, items] of [['Suggested next steps', cards], ['School notifications', notices]]) {
        if (!items.length && items === cards) continue;
        const heading = document.createElement('h3');
        heading.textContent = label;
        content.append(heading);
        for (const item of items) {
          content.append(overviewItem(item.title, item.summary || item.message, item.suggestion, item.action));
        }
        if (!items.length) {
          const empty = document.createElement('p');
          empty.textContent = 'No active notices for your account.';
          content.append(empty);
        }
      }
      overview.replaceChildren(content);
    } catch {
      overview.textContent = 'Alerts unavailable. Reopen the assistant to retry.';
    } finally {
      overviewRequest = false;
    }
  }

  document.querySelectorAll('[data-assistant-open]').forEach((button) => {
    button.addEventListener('click', () => {
      assistant.showModal();
      question.focus();
      loadOverview();
    });
  });
  assistant.querySelector('[data-assistant-close]').addEventListener('click', () => assistant.close());
  prompts.forEach((button) => button.addEventListener('click', () => {
    question.value = button.dataset.assistantPrompt;
    form.requestSubmit();
  }));

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    if (!question.value.trim()) {
      question.focus();
      return;
    }
    const buttons = [submit, ...prompts];
    buttons.forEach((button) => { button.disabled = true; });
    if (!exchange.hidden && history) {
      const previous = exchange.cloneNode(true);
      previous.removeAttribute('id');
      for (const node of previous.querySelectorAll('[id], [role]')) {
        node.removeAttribute('id');
        node.removeAttribute('role');
      }
      history.append(previous);
      if (history.children.length > 10) history.firstElementChild.remove();
    }
    asked.textContent = question.value.trim();
    showAnswer('Checking…');
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: {Accept: 'application/json'},
      });
      if (response.redirected) {
        showAnswer('Your session has expired. Sign in again and retry.');
        return;
      }
      const data = await response.json();
      showAnswer(data.message, data.actions, data.source);
    } catch {
      showAnswer('The assistant is unavailable. Refresh the page and try again.');
    } finally {
      buttons.forEach((button) => { button.disabled = false; });
    }
  });
}


document.querySelectorAll('[data-record-search]').forEach((input) => {
  const table = document.getElementById(input.getAttribute('aria-controls'));
  if (!table) return;
  const rows = [...table.querySelectorAll('tbody tr')].filter(row => row.querySelector('td'));
  const index = rows.map(row => [row, row.textContent.trim().toLocaleLowerCase()]);
  input.addEventListener('input', () => {
    const words = input.value.trim().toLocaleLowerCase().split(/\s+/);
    for (const [row, text] of index) row.hidden = !words.every(word => text.includes(word));
  });
});
