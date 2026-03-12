'use strict';

// ============================================================
// State
// ============================================================

let allFolders = [];        // All bookmark folders (flat list with path info)
let filteredFolders = [];   // Currently visible in dropdown
let filteredMatchData = null; // Parallel to filteredFolders: { nameIndices, pathIndices } per entry
let selectedFolder = null;  // The chosen folder object
let highlightedIndex = -1;  // Keyboard-navigation index in filteredFolders
let isDropdownOpen = false;
let currentTab = null;
let existingBookmark = null;

// ============================================================
// DOM references
// ============================================================

let dom = {};

// ============================================================
// Entry point
// ============================================================

document.addEventListener('DOMContentLoaded', async () => {
  dom = {
    titleInput:     document.getElementById('title'),
    urlInput:       document.getElementById('url'),
    folderInput:    document.getElementById('folder-input'),
    folderPicker:   document.getElementById('folder-picker'),
    dropdown:       document.getElementById('dropdown'),
    submitBtn:      document.getElementById('submit-btn'),
    submitLabel:    document.getElementById('submit-label'),
    cancelBtn:      document.getElementById('cancel-btn'),
    removeBtn:      document.getElementById('remove-btn'),
    headerTitle:    document.getElementById('header-title'),
    chromeWarning:  document.getElementById('chrome-warning'),
    mainContent:    document.getElementById('main-content'),
    successOverlay: document.getElementById('success-overlay'),
    successMsg:     document.getElementById('success-msg'),
    nfBackdrop:     document.getElementById('nf-backdrop'),
    nfName:         document.getElementById('nf-name'),
    nfParent:       document.getElementById('nf-parent'),
    nfCancel:       document.getElementById('nf-cancel'),
    nfCreate:       document.getElementById('nf-create'),
  };

  await init();
});

// ============================================================
// Initialization
// ============================================================

async function init() {
  try {
    // 1. Get the active tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    currentTab = tab;

    const bookmarkable = isBookmarkableUrl(tab.url);

    // 2. Show warning + disable form for non-bookmarkable pages
    if (!bookmarkable) {
      dom.chromeWarning.style.display = 'flex';
      dom.mainContent.classList.add('main-content--disabled');
      dom.submitBtn.disabled = true;
    }

    // 3. Populate URL field
    dom.urlInput.value = tab.url || '';

    // 4. Check for an existing bookmark
    if (bookmarkable && tab.url) {
      const results = await chrome.bookmarks.search({ url: tab.url });
      existingBookmark = results.length > 0
        ? results.reduce((latest, b) => (b.dateAdded ?? 0) > (latest.dateAdded ?? 0) ? b : latest)
        : null;
    }

    // 5. Populate title field
    dom.titleInput.value = existingBookmark?.title ?? tab.title ?? '';

    // 6. Load all folders from the bookmark tree
    const tree = await chrome.bookmarks.getTree();
    allFolders = collectFolders(tree[0]);

    // 7. Determine the default folder
    if (existingBookmark) {
      selectedFolder =
        allFolders.find(f => f.id === existingBookmark.parentId) ??
        allFolders.find(f => f.id === '1') ??
        allFolders[0];
      dom.headerTitle.textContent = 'Edit Bookmark';
      dom.submitLabel.textContent = 'Update';
      dom.removeBtn.style.display = 'inline-flex';
    } else {
      // Default: Bookmarks Bar (id = '1')
      selectedFolder =
        allFolders.find(f => f.id === '1') ??
        allFolders[0];
    }

    updateFolderDisplay();
    setupEventListeners();

    // 8. Focus the title field
    if (bookmarkable) {
      dom.titleInput.focus();
      dom.titleInput.select();
    }

  } catch (err) {
    console.error('[Advanced Bookmarks] Init error:', err);
  }
}

// ============================================================
// Bookmark tree traversal
// ============================================================

/**
 * Recursively collect every folder node from the bookmark tree.
 * Returns a flat array of { id, title, pathParts, fullPath }.
 *
 * @param {chrome.bookmarks.BookmarkTreeNode} node
 * @param {string[]} pathParts  Ancestor folder titles (used for display)
 * @returns {Array<{id:string, title:string, pathParts:string[], fullPath:string}>}
 */
function collectFolders(node, pathParts = []) {
  const results = [];

  // A node with `children` is a folder (bookmarks have no `children` property)
  if (node.children !== undefined) {
    if (node.id !== '0') { // Skip the invisible virtual root
      results.push({
        id: node.id,
        title: node.title,
        pathParts: [...pathParts],
        fullPath: pathParts.length > 0
          ? `${pathParts.join(' › ')} › ${node.title}`
          : node.title,
      });
    }

    const nextPath = node.id !== '0' ? [...pathParts, node.title] : pathParts;
    for (const child of node.children) {
      results.push(...collectFolders(child, nextPath));
    }
  }

  return results;
}

// ============================================================
// Folder input display
// ============================================================

function updateFolderDisplay() {
  if (!selectedFolder) return;
  dom.folderInput.value = selectedFolder.title;
  dom.folderInput.title = selectedFolder.fullPath; // native tooltip for long paths
}

// ============================================================
// Dropdown — open / close / render
// ============================================================

function openDropdown(query) {
  const q = (query ?? '').trim();
  const qCompact = q.replace(/\s+/g, '').toLowerCase();

  if (qCompact === '') {
    filteredFolders = [...allFolders];
    filteredMatchData = null;
    highlightedIndex = filteredFolders.findIndex(f => f.id === selectedFolder?.id);
    if (highlightedIndex < 0) highlightedIndex = 0;
  } else {
    const scored = [];
    for (const f of allFolders) {
      const nameMatch = fuzzyMatch(f.title, qCompact);
      const pathStr   = f.pathParts.join(' › ');
      const pathMatch = f.pathParts.length > 0 ? fuzzyMatch(pathStr, qCompact) : { matched: false, indices: [] };
      if (!nameMatch.matched && !pathMatch.matched) continue;
      // Prefer matches in the folder name; path-only matches get a score penalty
      const score = nameMatch.matched
        ? fuzzyScore(nameMatch.indices)
        : fuzzyScore(pathMatch.indices) + 10000;
      scored.push({ folder: f, score, nameIndices: nameMatch.indices, pathIndices: pathMatch.indices });
    }
    scored.sort((a, b) => a.score - b.score);
    filteredFolders  = scored.map(s => s.folder);
    filteredMatchData = scored.map(s => ({ nameIndices: s.nameIndices, pathIndices: s.pathIndices }));
    highlightedIndex = filteredFolders.length > 0 ? 0 : -1;
  }

  renderDropdown(q);

  dom.dropdown.style.display = 'block';
  dom.folderPicker.classList.add('folder-picker--open');
  dom.folderInput.setAttribute('aria-expanded', 'true');
  isDropdownOpen = true;

  // Expand popup height so the dropdown is fully visible
  requestAnimationFrame(() => {
    const rect = dom.dropdown.getBoundingClientRect();
    document.body.style.minHeight = `${rect.bottom + 16}px`;
    scrollHighlightedIntoView();
  });
}

function closeDropdown() {
  dom.dropdown.style.display = 'none';
  dom.folderPicker.classList.remove('folder-picker--open');
  dom.folderInput.setAttribute('aria-expanded', 'false');
  isDropdownOpen = false;
  highlightedIndex = -1;
  document.body.style.minHeight = '';
}

function renderDropdown(query) {
  let folderHtml;
  if (filteredFolders.length === 0) {
    folderHtml = '<div class="no-results">No folders found</div>';
  } else {
    folderHtml = filteredFolders.map((folder, index) => {
      const isHighlighted = index === highlightedIndex;
      const isSelected    = folder.id === selectedFolder?.id;

      const matchData = filteredMatchData?.[index];
      const nameHtml = matchData?.nameIndices?.length
        ? highlightFuzzy(folder.title, matchData.nameIndices)
        : escapeHtml(folder.title);

      const pathStr  = folder.pathParts.join(' › ');
      const pathHtml = folder.pathParts.length > 0
        ? `<div class="item-path">${matchData?.pathIndices?.length
            ? highlightFuzzy(pathStr, matchData.pathIndices)
            : escapeHtml(pathStr)}</div>`
        : '';

      const classes = [
        'dropdown-item',
        isHighlighted ? 'dropdown-item--highlighted' : '',
        isSelected    ? 'dropdown-item--selected'    : '',
      ].filter(Boolean).join(' ');

      return `<div class="${classes}" data-index="${index}" role="option" aria-selected="${isSelected}">
        <div class="item-name">${nameHtml}</div>
        ${pathHtml}
      </div>`;
    }).join('');
  }

  const newFolderHighlighted = highlightedIndex === filteredFolders.length;
  const newFolderHtml = `
    <div class="dropdown-divider"></div>
    <div class="dropdown-new-folder${newFolderHighlighted ? ' dropdown-new-folder--highlighted' : ''}" role="option">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M20 6h-8l-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-1 8h-3v3h-2v-3h-3v-2h3V9h2v3h3v2z"/>
      </svg>
      New folder…
    </div>`;

  dom.dropdown.innerHTML = folderHtml + newFolderHtml;

  // Attach mouse handlers to each folder item
  dom.dropdown.querySelectorAll('.dropdown-item').forEach(el => {
    el.addEventListener('mousedown', e => {
      e.preventDefault(); // Keep focus on the input
      chooseFolder(filteredFolders[parseInt(el.dataset.index, 10)]);
    });

    el.addEventListener('mouseover', () => {
      const i = parseInt(el.dataset.index, 10);
      if (i !== highlightedIndex) {
        highlightedIndex = i;
        updateHighlightClass();
      }
    });
  });

  // "New folder" item
  const nfEl = dom.dropdown.querySelector('.dropdown-new-folder');
  nfEl.addEventListener('mousedown', e => {
    e.preventDefault();
    openNewFolderDialog(dom.folderInput.value.trim());
  });
  nfEl.addEventListener('mouseover', () => {
    if (highlightedIndex !== filteredFolders.length) {
      highlightedIndex = filteredFolders.length;
      updateHighlightClass();
    }
  });
}

/** Efficiently toggle the highlighted class without a full re-render */
function updateHighlightClass() {
  dom.dropdown.querySelectorAll('.dropdown-item').forEach((el, i) => {
    el.classList.toggle('dropdown-item--highlighted', i === highlightedIndex);
  });
  const nfEl = dom.dropdown.querySelector('.dropdown-new-folder');
  if (nfEl) nfEl.classList.toggle('dropdown-new-folder--highlighted', highlightedIndex === filteredFolders.length);
}

function scrollHighlightedIntoView() {
  const el = dom.dropdown.querySelector('.dropdown-item--highlighted');
  if (el) el.scrollIntoView({ block: 'nearest', behavior: 'instant' });
}

function chooseFolder(folder) {
  selectedFolder = folder;
  closeDropdown();
  updateFolderDisplay();
}

// ============================================================
// Event listeners
// ============================================================

function setupEventListeners() {

  // ---- Folder input ----

  dom.folderInput.addEventListener('focus', () => {
    // Clear the displayed folder name so typing starts fresh
    if (dom.folderInput.value === selectedFolder?.title) {
      dom.folderInput.value = '';
    }
    openDropdown(dom.folderInput.value);
  });

  dom.folderInput.addEventListener('input', () => {
    openDropdown(dom.folderInput.value);
  });

  dom.folderInput.addEventListener('keydown', e => {
    if (!isDropdownOpen) {
      if (e.key === 'ArrowDown') { e.preventDefault(); openDropdown(''); }
      if (e.key === 'Enter')    { e.preventDefault(); saveBookmark(); }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        if (highlightedIndex < filteredFolders.length - 1) {
          highlightedIndex++;
          updateHighlightClass();
          scrollHighlightedIntoView();
        }
        break;

      case 'ArrowUp':
        e.preventDefault();
        if (highlightedIndex > 0) {
          highlightedIndex--;
          updateHighlightClass();
          scrollHighlightedIntoView();
        }
        break;

      case 'Enter':
        e.preventDefault();
        if (highlightedIndex === filteredFolders.length || filteredFolders.length === 0) {
          openNewFolderDialog(dom.folderInput.value.trim());
        } else if (highlightedIndex >= 0 && filteredFolders[highlightedIndex]) {
          chooseFolder(filteredFolders[highlightedIndex]);
        } else {
          closeDropdown();
          updateFolderDisplay();
        }
        break;

      case 'Escape':
        e.preventDefault();
        closeDropdown();
        updateFolderDisplay();
        break;

      case 'Tab':
        if (filteredFolders.length === 0) {
          e.preventDefault();
          highlightedIndex = 0; // == filteredFolders.length, highlights "New folder"
          updateHighlightClass();
        } else if (highlightedIndex >= 0 && filteredFolders[highlightedIndex]) {
          chooseFolder(filteredFolders[highlightedIndex]);
        } else {
          closeDropdown();
          updateFolderDisplay();
        }
        break;
    }
  });

  // Close dropdown on outside click
  document.addEventListener('mousedown', e => {
    if (!dom.folderPicker.contains(e.target)) {
      closeDropdown();
      updateFolderDisplay();
    }
  });

  // ---- Title: Enter to save, Escape to close popup ----
  dom.titleInput.addEventListener('keydown', e => {
    if (e.key === 'Enter')  { e.preventDefault(); saveBookmark(); }
    if (e.key === 'Escape') { window.close(); }
  });

  // ---- Global Escape closes popup (when dropdown and new-folder dialog are not open) ----
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !isDropdownOpen && dom.nfBackdrop.style.display === 'none') window.close();
  });

  // ---- Buttons ----
  dom.submitBtn.addEventListener('click', saveBookmark);
  dom.cancelBtn.addEventListener('click', () => window.close());
  dom.removeBtn.addEventListener('click', removeBookmark);

  // ---- New folder dialog ----
  dom.nfCancel.addEventListener('click', closeNewFolderDialog);
  dom.nfCreate.addEventListener('click', createNewFolder);
  dom.nfName.addEventListener('keydown', e => {
    if (e.key === 'Enter')  { e.preventDefault(); createNewFolder(); }
    if (e.key === 'Escape') { e.preventDefault(); closeNewFolderDialog(); }
  });
  // Click outside dialog to dismiss
  dom.nfBackdrop.addEventListener('mousedown', e => {
    if (e.target === dom.nfBackdrop) closeNewFolderDialog();
  });
}

// ============================================================
// New folder dialog
// ============================================================

function openNewFolderDialog(prefillName = '') {
  closeDropdown();
  dom.nfParent.innerHTML = allFolders.map(f =>
    `<option value="${escapeHtml(f.id)}" ${f.id === selectedFolder?.id ? 'selected' : ''}>${escapeHtml(f.fullPath)}</option>`
  ).join('');
  dom.nfName.value = prefillName;
  dom.nfName.classList.remove('input--error');
  dom.nfCreate.disabled = false;
  dom.nfBackdrop.style.display = 'flex';
  requestAnimationFrame(() => dom.nfName.focus());
}

function closeNewFolderDialog() {
  dom.nfBackdrop.style.display = 'none';
}

async function createNewFolder() {
  const name = dom.nfName.value.trim();
  if (!name) {
    dom.nfName.classList.add('input--error');
    dom.nfName.addEventListener('input', () => dom.nfName.classList.remove('input--error'), { once: true });
    dom.nfName.focus();
    return;
  }
  const parentId = dom.nfParent.value;
  dom.nfCreate.disabled = true;
  try {
    const newNode = await chrome.bookmarks.create({ title: name, parentId });
    // Refresh folder list and auto-select the new folder
    const tree = await chrome.bookmarks.getTree();
    allFolders = collectFolders(tree[0]);
    selectedFolder = allFolders.find(f => f.id === newNode.id) ?? selectedFolder;
    updateFolderDisplay();
    closeNewFolderDialog();
  } catch (err) {
    console.error('[Advanced Bookmarks] Create folder error:', err);
    dom.nfCreate.disabled = false;
  }
}

// ============================================================
// Save / Update
// ============================================================

async function saveBookmark() {
  const title = dom.titleInput.value.trim();

  if (!title) {
    dom.titleInput.classList.add('input--error');
    dom.titleInput.focus();
    dom.titleInput.addEventListener('input', () => {
      dom.titleInput.classList.remove('input--error');
    }, { once: true });
    return;
  }

  if (!selectedFolder) return;

  dom.submitBtn.disabled = true;
  dom.cancelBtn.disabled = true;
  dom.submitLabel.textContent = existingBookmark ? 'Updating…' : 'Saving…';

  try {
    if (existingBookmark) {
      await chrome.bookmarks.update(existingBookmark.id, { title });
      if (existingBookmark.parentId !== selectedFolder.id) {
        await chrome.bookmarks.move(existingBookmark.id, { parentId: selectedFolder.id });
      }
    } else {
      await chrome.bookmarks.create({
        title,
        url: currentTab.url,
        parentId: selectedFolder.id,
      });
    }
    showSuccess(existingBookmark ? 'Bookmark updated!' : 'Bookmark saved!');
  } catch (err) {
    console.error('[Advanced Bookmarks] Save error:', err);
    dom.submitBtn.disabled = false;
    dom.cancelBtn.disabled = false;
    dom.submitLabel.textContent = existingBookmark ? 'Update' : 'Save';
  }
}

// ============================================================
// Remove
// ============================================================

async function removeBookmark() {
  if (!existingBookmark) return;
  try {
    dom.removeBtn.disabled = true;
    await chrome.bookmarks.remove(existingBookmark.id);
    showSuccess('Bookmark removed!');
  } catch (err) {
    console.error('[Advanced Bookmarks] Remove error:', err);
    dom.removeBtn.disabled = false;
  }
}

// ============================================================
// Success overlay
// ============================================================

function showSuccess(message) {
  dom.successMsg.textContent = message;
  dom.successOverlay.style.display = 'flex';
  setTimeout(() => window.close(), 900);
}

// ============================================================
// Utilities
// ============================================================

const NON_BOOKMARKABLE_PREFIXES = [
  'chrome://',
  'chrome-extension://',
  'devtools://',
  'about:',
  'data:',
  'javascript:',
];

function isBookmarkableUrl(url) {
  if (!url) return false;
  return !NON_BOOKMARKABLE_PREFIXES.some(p => url.startsWith(p));
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Fuzzy subsequence match.
 * `compactQuery` must already be lowercased with spaces removed.
 * Returns { matched: bool, indices: number[] } where indices are char positions in `text`.
 */
function fuzzyMatch(text, compactQuery) {
  const t = text.toLowerCase();
  const indices = [];
  let ti = 0;
  for (let qi = 0; qi < compactQuery.length; qi++) {
    const found = t.indexOf(compactQuery[qi], ti);
    if (found === -1) return { matched: false, indices: [] };
    indices.push(found);
    ti = found + 1;
  }
  return { matched: true, indices };
}

/**
 * Score a fuzzy match result — lower is better.
 * Rewards early starts and consecutive character runs.
 */
function fuzzyScore(indices) {
  if (indices.length === 0) return 0;
  let score = indices[0]; // penalty for starting late
  for (let i = 1; i < indices.length; i++) {
    score += (indices[i] - indices[i - 1] - 1); // gap penalty
  }
  return score;
}

/**
 * Wrap matched character positions in <mark> tags.
 * Consecutive matched chars are wrapped in a single <mark> for cleaner HTML.
 */
function highlightFuzzy(text, indices) {
  const indexSet = new Set(indices);
  let result = '';
  let inMark = false;
  for (let i = 0; i < text.length; i++) {
    const ch = escapeHtml(text[i]);
    if (indexSet.has(i)) {
      if (!inMark) { result += '<mark>'; inMark = true; }
      result += ch;
    } else {
      if (inMark) { result += '</mark>'; inMark = false; }
      result += ch;
    }
  }
  if (inMark) result += '</mark>';
  return result;
}
