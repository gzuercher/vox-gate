// Minimal, safe Markdown renderer for assistant bubbles.
// Builds a DOM tree using createElement / textContent only — never
// innerHTML — so backend strings cannot inject markup. Supports:
//   - GFM tables (| ... | with |---| separator, optional :--- alignment)
//   - unordered lists (- or *)  /  ordered lists (1.)
//   - paragraphs (blank-line separated, soft-joined)
//   - inline **bold** and `code`
// Anything else is emitted as text. Public entry: window.renderMarkdown.

(function () {
  'use strict';

  function isTableRow(s) {
    return /^\s*\|.*\|\s*$/.test(s);
  }
  function isTableSeparator(s) {
    return !!s && /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(s);
  }
  function parseRow(s) {
    return s.trim().replace(/^\|/, '').replace(/\|$/, '').split('|')
      .map(function (c) { return c.trim(); });
  }
  function parseAligns(s) {
    return s.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(function (c) {
      var t = c.trim();
      var l = t.charAt(0) === ':';
      var r = t.charAt(t.length - 1) === ':';
      if (l && r) return 'center';
      if (r) return 'right';
      if (l) return 'left';
      return '';
    });
  }

  function tokenizeInline(s) {
    var out = [];
    var buf = '';
    var i = 0;
    function flush() { if (buf) { out.push({ type: 'text', value: buf }); buf = ''; } }
    while (i < s.length) {
      if (s.charAt(i) === '`') {
        var endC = s.indexOf('`', i + 1);
        if (endC > i) {
          flush();
          out.push({ type: 'code', value: s.slice(i + 1, endC) });
          i = endC + 1;
          continue;
        }
      }
      if (s.charAt(i) === '*' && s.charAt(i + 1) === '*') {
        var endB = s.indexOf('**', i + 2);
        if (endB > i + 1) {
          flush();
          out.push({ type: 'bold', value: s.slice(i + 2, endB) });
          i = endB + 2;
          continue;
        }
      }
      buf += s.charAt(i);
      i++;
    }
    flush();
    return out;
  }

  function renderInline(s, target) {
    var toks = tokenizeInline(s);
    for (var i = 0; i < toks.length; i++) {
      var tok = toks[i];
      if (tok.type === 'text') {
        target.appendChild(document.createTextNode(tok.value));
      } else if (tok.type === 'bold') {
        var b = document.createElement('strong');
        b.textContent = tok.value;
        target.appendChild(b);
      } else if (tok.type === 'code') {
        var c = document.createElement('code');
        c.textContent = tok.value;
        target.appendChild(c);
      }
    }
  }

  function buildTable(headers, aligns, rows) {
    var tbl = document.createElement('table');
    var thead = document.createElement('thead');
    var trh = document.createElement('tr');
    for (var h = 0; h < headers.length; h++) {
      var th = document.createElement('th');
      if (aligns[h]) th.style.textAlign = aligns[h];
      renderInline(headers[h], th);
      trh.appendChild(th);
    }
    thead.appendChild(trh);
    tbl.appendChild(thead);
    var tbody = document.createElement('tbody');
    for (var r = 0; r < rows.length; r++) {
      var tr = document.createElement('tr');
      for (var ci = 0; ci < rows[r].length; ci++) {
        var td = document.createElement('td');
        if (aligns[ci]) td.style.textAlign = aligns[ci];
        renderInline(rows[r][ci], td);
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    tbl.appendChild(tbody);
    return tbl;
  }

  function isStructural(line, next) {
    if (/^\s*[-*]\s+/.test(line)) return true;
    if (/^\s*\d+\.\s+/.test(line)) return true;
    if (isTableRow(line) && isTableSeparator(next)) return true;
    return false;
  }

  function renderMarkdown(src, target) {
    target.replaceChildren();
    target.classList.add('md');
    var lines = String(src == null ? '' : src).replace(/\r\n?/g, '\n').split('\n');
    var i = 0;
    while (i < lines.length) {
      var line = lines[i];
      if (!line.trim()) { i++; continue; }

      if (isTableRow(line) && isTableSeparator(lines[i + 1])) {
        var headers = parseRow(line);
        var aligns = parseAligns(lines[i + 1]);
        i += 2;
        var rows = [];
        while (i < lines.length && isTableRow(lines[i])) {
          rows.push(parseRow(lines[i]));
          i++;
        }
        target.appendChild(buildTable(headers, aligns, rows));
        continue;
      }

      if (/^\s*[-*]\s+/.test(line)) {
        var ul = document.createElement('ul');
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
          var liU = document.createElement('li');
          renderInline(lines[i].replace(/^\s*[-*]\s+/, ''), liU);
          ul.appendChild(liU);
          i++;
        }
        target.appendChild(ul);
        continue;
      }

      if (/^\s*\d+\.\s+/.test(line)) {
        var ol = document.createElement('ol');
        while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
          var liO = document.createElement('li');
          renderInline(lines[i].replace(/^\s*\d+\.\s+/, ''), liO);
          ol.appendChild(liO);
          i++;
        }
        target.appendChild(ol);
        continue;
      }

      var buf = [];
      while (
        i < lines.length &&
        lines[i].trim() &&
        !isStructural(lines[i], lines[i + 1])
      ) {
        buf.push(lines[i]);
        i++;
      }
      var p = document.createElement('p');
      renderInline(buf.join(' '), p);
      target.appendChild(p);
    }
  }

  window.renderMarkdown = renderMarkdown;
})();
