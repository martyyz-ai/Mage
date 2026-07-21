function showFeature(index, color, event) {
  var source = event && event.currentTarget;
  var container = source ? source.closest('.feature-container') : document.querySelector('.feature-container');
  if (!container) return;
  var tabs = Array.from(container.querySelectorAll('.feature-tab'));
  var panels = Array.from(container.querySelectorAll('.feature-panel'));
  tabs.forEach(function (tab) {
    tab.classList.remove('active-blue', 'active-amber', 'active-purple', 'active-teal', 'active-rose', 'active-indigo');
    tab.setAttribute('aria-selected', 'false');
  });
  panels.forEach(function (panel) { panel.classList.remove('active'); });
  if (tabs[index]) {
    tabs[index].classList.add('active-' + color);
    tabs[index].setAttribute('aria-selected', 'true');
  }
  if (panels[index]) panels[index].classList.add('active');
}
window.showFeature = showFeature;

document.addEventListener('DOMContentLoaded', function () {
  var switcher = document.querySelector('.rf-project-switcher');
  var trigger = document.querySelector('.rf-project-trigger');
  if (switcher && trigger) {
    trigger.addEventListener('click', function () {
      var open = !switcher.classList.contains('is-open');
      switcher.classList.toggle('is-open', open);
      trigger.setAttribute('aria-expanded', String(open));
    });
    document.addEventListener('click', function (event) {
      if (!switcher.contains(event.target)) closeSwitcher();
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        closeSwitcher();
        trigger.blur();
      }
    });
    function closeSwitcher() {
      switcher.classList.remove('is-open');
      trigger.setAttribute('aria-expanded', 'false');
    }
  }

  document.querySelectorAll('.feature-container').forEach(function (container) {
    var tabs = Array.from(container.querySelectorAll('.feature-tab'));
    tabs.forEach(function (tab) {
      tab.setAttribute('aria-selected', 'false');
      tab.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          tab.click();
        }
      });
    });
    if (tabs[0]) showFeature(0, tabs[0].dataset.color || 'blue', { currentTarget: tabs[0] });
  });

  if (window.GLightbox) {
    window.GLightbox({ selector: '.glightbox', touchNavigation: true, loop: true });
  }

  document.querySelectorAll('.rf-image-strip').forEach(function (strip) {
    var shell = strip.closest('.rf-image-strip-shell');
    var lazyImages = Array.from(strip.querySelectorAll('img[data-src]'));

    function loadImage(image) {
      if (!image.dataset.src) return;
      image.src = image.dataset.src;
      image.removeAttribute('data-src');
    }

    if ('IntersectionObserver' in window) {
      var imageObserver = new IntersectionObserver(function (entries, observer) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          loadImage(entry.target);
          observer.unobserve(entry.target);
        });
      }, { root: strip, rootMargin: '0px', threshold: 0 });
      lazyImages.forEach(function (image) { imageObserver.observe(image); });
    } else {
      lazyImages.forEach(loadImage);
    }

    var hintFrame = 0;
    function updateScrollHint() {
      hintFrame = 0;
      var atEnd = strip.scrollLeft + strip.clientWidth >= strip.scrollWidth - 2;
      if (shell) shell.classList.toggle('is-at-end', atEnd);
    }
    function requestHintUpdate() {
      if (!hintFrame) hintFrame = window.requestAnimationFrame(updateScrollHint);
    }
    strip.addEventListener('scroll', requestHintUpdate, { passive: true });
    window.addEventListener('resize', requestHintUpdate, { passive: true });
    if ('ResizeObserver' in window) new ResizeObserver(requestHintUpdate).observe(strip);
    requestHintUpdate();
  });

  var diversityResult = document.getElementById('rf-diversity-result');
  var diversityLabel = document.getElementById('rf-diversity-result-label');
  var diversityButtons = Array.prototype.slice.call(document.querySelectorAll('.rf-diversity-button'));
  var diversityRequest = 0;
  diversityButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      if (button.classList.contains('is-active') || !diversityResult || !diversityLabel) return;
      diversityButtons.forEach(function (item) {
        var active = item === button;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-pressed', String(active));
      });

      var label = button.dataset.label;
      var request = ++diversityRequest;
      diversityResult.classList.add('is-loading');
      diversityLabel.textContent = label.toUpperCase();
      diversityResult.alt = label + ' editing result';
      diversityResult.addEventListener('load', function () {
        if (request === diversityRequest) diversityResult.classList.remove('is-loading');
      }, { once: true });
      diversityResult.addEventListener('error', function () {
        if (request === diversityRequest) diversityResult.classList.remove('is-loading');
      }, { once: true });
      diversityResult.src = button.dataset.src;
    });
  });

  renderBenchmarkTables();

  ['t2i-table', 'edit-table'].forEach(function (tableId) {
    var table = document.getElementById(tableId);
    if (!table) return;
    var headers = Array.from(table.querySelectorAll('thead th'));
    var labels = headers.map(function (header) { return header.textContent.trim(); });
    var activeIndex = -1;
    var ascending = true;

    headers.forEach(function (header, index) {
      header.tabIndex = 0;
      header.setAttribute('role', 'button');
      header.addEventListener('click', function () { sortBy(index); });
      header.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          sortBy(index);
        }
      });
    });

    function sortBy(index) {
      var rows = Array.from(table.querySelectorAll('tbody tr'));
      var nextAscending = activeIndex === index ? !ascending : true;
      rows.sort(function (a, b) {
        var left = cellValue(a, index);
        var right = cellValue(b, index);
        var leftNumber = parseFloat(left);
        var rightNumber = parseFloat(right);
        if (!Number.isNaN(leftNumber) && !Number.isNaN(rightNumber)) {
          return nextAscending ? leftNumber - rightNumber : rightNumber - leftNumber;
        }
        return nextAscending ? left.localeCompare(right) : right.localeCompare(left);
      });
      rows.forEach(function (row) { table.tBodies[0].appendChild(row); });
      headers.forEach(function (item, itemIndex) {
        item.textContent = labels[itemIndex];
        item.removeAttribute('aria-sort');
      });
      headerState(headers[index], labels[index], nextAscending);
      activeIndex = index;
      ascending = nextAscending;
    }
  });
});

function renderBenchmarkTables() {
  var benchmarks = window.MAGE_BENCHMARKS;
  if (!benchmarks) return;
  renderBenchmarkTable('t2i-table', benchmarks.generation);
  renderBenchmarkTable('edit-table', benchmarks.editing);
}

function renderBenchmarkTable(tableId, dataset) {
  var table = document.getElementById(tableId);
  if (!table || !dataset) return;

  var headerRow = document.createElement('tr');
  dataset.columns.forEach(function (label) {
    var header = document.createElement('th');
    header.textContent = label;
    headerRow.appendChild(header);
  });
  table.tHead.replaceChildren(headerRow);

  var fragment = document.createDocumentFragment();
  dataset.rows.forEach(function (row) {
    var tr = document.createElement('tr');
    if (row.ours) tr.classList.add('is-selected');
    [row.type].concat(row.cells).forEach(function (value, index) {
      var td = document.createElement('td');
      if (index === 0) td.classList.add('rf-type-cell');
      if (index === 1 && row.ours) {
        var strong = document.createElement('strong');
        strong.textContent = value;
        td.appendChild(strong);
      } else {
        td.textContent = value;
      }
      tr.appendChild(td);
    });
    fragment.appendChild(tr);
  });
  table.tBodies[0].replaceChildren(fragment);
}

function cellValue(row, index) {
  var cell = row.children[index];
  return cell ? cell.textContent.replace(/[★↑↓]/g, '').trim() : '';
}

function headerState(header, label, ascending) {
  header.textContent = label + (ascending ? ' ↑' : ' ↓');
  header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
}
