document.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.getElementById('settings-sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    const toggleBtn = document.getElementById('settings-toggle');
    const closeBtn = document.getElementById('sidebar-close');
    const darkModeToggle = document.getElementById('dark-mode-toggle');
    const colCountSelect = document.getElementById('col-count-select');
    const sortSelect = document.getElementById('sort-select');
    const viewModeSelect = document.getElementById('view-mode-select');

    // Sidebar Toggle Logic
    function openSidebar() {
        sidebar.classList.add('open');
        backdrop.classList.add('show');
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        backdrop.classList.remove('show');
    }

    if (toggleBtn) toggleBtn.addEventListener('click', openSidebar);
    if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
    if (backdrop) backdrop.addEventListener('click', closeSidebar);

    // Dark Mode Logic
    function applyDarkMode(isDark) {
        if (isDark) {
            document.body.classList.add('dark-mode');
        } else {
            document.body.classList.remove('dark-mode');
        }
        localStorage.setItem('darkMode', isDark);
    }

    // Init Dark Mode
    const savedDarkMode = localStorage.getItem('darkMode');
    const systemDarkMode = window.matchMedia('(prefers-color-scheme: dark)');

    function setTheme(isDark) {
        darkModeToggle.checked = isDark;
        applyDarkMode(isDark);
    }

    if (darkModeToggle) {
        if (savedDarkMode !== null) {
            // User override exists
            setTheme(savedDarkMode === 'true');
        } else {
            // Default to system
            setTheme(systemDarkMode.matches);
        }

        // Listen for toggle changes (User override)
        darkModeToggle.addEventListener('change', function () {
            applyDarkMode(this.checked);
        });

        // Listen for system changes (Only if no override)
        systemDarkMode.addEventListener('change', (e) => {
            if (localStorage.getItem('darkMode') === null) {
                setTheme(e.matches);
            }
        });
    }

    // Masonry Helper
    function getMasonry() {
        const grid = document.getElementById('gallery-grid');
        return grid && window.Masonry ? Masonry.data(grid) : null;
    }

    // Initialize Masonry safely
    function initMasonry() {
        const grid = document.getElementById('gallery-grid');
        if (!grid) return;

        // Prevent double init
        if (getMasonry()) return;

        var msnry = new Masonry(grid, {
            itemSelector: '[class*="col-"]',
            percentPosition: true
        });

        // Relayout as each image loads (Critical for preventing overlaps)
        imagesLoaded(grid).on('progress', function () {
            msnry.layout();
        });
    }

    // ── Dynamic View Integration ───────────────────────────────

    /** Show/hide containers based on whether we're in dynamic mode */
    function setDynamicVisible(show) {
        const grid = document.getElementById('gallery-grid');
        const dynContainer = document.getElementById('dynamic-gallery-container');
        const sentinel = document.getElementById('scroll-sentinel');
        const loader = document.getElementById('loading');

        if (grid) grid.style.display = show ? 'none' : '';
        if (dynContainer) dynContainer.style.display = show ? '' : 'none';
        if (sentinel) sentinel.style.display = show ? 'none' : '';
        if (loader) loader.style.display = show ? 'none' : '';
    }

    function initDynamicView() {
        if (!window.DynamicGallery) return;
        const dynContainer = document.getElementById('dynamic-gallery-container');
        if (!dynContainer) return;

        // Create if not already created
        if (!window._dynamicGallery) {
            window._dynamicGallery = new DynamicGallery('dynamic-gallery-container');
        }
        window._dynamicGallery.init();

        // Feed the initial server-rendered data
        if (window._dynamicInitialData && window._dynamicInitialData.length > 0) {
            window._dynamicGallery.setItems(window._dynamicInitialData);
            // Also load remaining pages
            loadAllPagesForDynamic();
        }
    }

    function destroyDynamicView() {
        if (window._dynamicGallery) {
            window._dynamicGallery.destroy();
        }
    }

    /** Incrementally load all pages and feed into dynamic gallery */
    function loadAllPagesForDynamic() {
        if (!window._dynamicGallery || !window._dynamicEventPath) return;
        const eventPath = window._dynamicEventPath;
        const key = window._dynamicKey || '';

        let page = 2; // Page 1 was already embedded
        let loading = false;

        function loadNextPage() {
            if (loading) return;
            loading = true;
            fetch(`/api/e/${eventPath}?page=${page}&key=${key}`)
                .then(r => r.json())
                .then(data => {
                    if (data.media && data.media.length > 0) {
                        const items = data.media.map(m => ({
                            filename: m.filename,
                            thumb_url: m.thumb_route === 'thumb_file'
                                ? `/e/${eventPath}/t/${m.thumb_filename}?key=${key}`
                                : `/thumbs/${m.thumb_filename}`,
                            full_url: `/e/${eventPath}/m/${m.filename}?key=${key}`,
                            width: m.width || 800,
                            height: m.height || 600
                        }));
                        window._dynamicGallery.addItems(items);
                    }
                    if (data.next_page) {
                        page = data.next_page;
                        loading = false;
                        // Continue loading next page after a brief delay
                        setTimeout(loadNextPage, 100);
                    }
                })
                .catch(err => {
                    console.error('Dynamic view: page load error', err);
                })
                .finally(() => { loading = false; });
        }

        loadNextPage();
    }

    // ── View Mode Logic ────────────────────────────────────────

    function applyViewMode(mode) {
        const grid = document.getElementById('gallery-grid');

        // 1. Clean up previous mode
        destroyDynamicView();
        if (grid) grid.classList.remove('view-grid', 'view-list');

        if (mode === 'dynamic') {
            // Dynamic View
            setDynamicVisible(true);
            initDynamicView();

            // Hide column/sort controls (Dynamic manages its own)
            if (colCountSelect) colCountSelect.parentElement.style.display = 'none';
            if (sortSelect) sortSelect.parentElement.style.display = 'none';
        } else {
            // Standard views
            setDynamicVisible(false);

            if (mode === 'masonry') {
                if (!getMasonry()) initMasonry();
                else getMasonry().layout();
            } else {
                const msnry = getMasonry();
                if (msnry) msnry.destroy();
                if (grid) {
                    if (mode === 'grid') grid.classList.add('view-grid');
                    if (mode === 'list') grid.classList.add('view-list');
                }
            }

            // Show column/sort controls
            if (colCountSelect) colCountSelect.parentElement.style.display = (mode === 'list') ? 'none' : 'block';
            if (sortSelect) sortSelect.parentElement.style.display = 'block';
        }

        localStorage.setItem('viewMode', mode);
    }

    // Init View Mode — default to 'dynamic' if nothing saved
    const savedViewMode = localStorage.getItem('viewMode') || 'dynamic';
    if (viewModeSelect) {
        viewModeSelect.value = savedViewMode;
        applyViewMode(savedViewMode);

        viewModeSelect.addEventListener('change', function () {
            applyViewMode(this.value);
        });
    } else {
        if (savedViewMode === 'masonry') initMasonry();
    }

    // Column Count Logic
    function updateColumnCount(count) {
        const grid = document.getElementById('gallery-grid');
        if (!grid) return;

        // Reset classes
        const cols = grid.querySelectorAll('[class*="col-"]');
        cols.forEach(col => {
            col.className = col.className.replace(/col-(md|lg|xl|xxl)?-?\d+/g, '').trim();

            if (count === 'auto' || isNaN(count)) {
                col.classList.add('col-6', 'col-md-4', 'col-lg-3');
            } else {
                col.classList.add('col-' + (12 / count));
            }
            col.classList.add('mb-2');
        });

        // Trigger Layout only if in Masonry mode
        const mode = viewModeSelect ? viewModeSelect.value : 'masonry';
        if (mode === 'masonry') {
            var msnry = getMasonry();
            if (msnry) msnry.layout();
        }
    }

    // sorting logic
    function sortItems(criteria, order) {
        const grid = document.getElementById('gallery-grid');
        if (!grid) return;

        const items = Array.from(grid.children);

        items.sort((a, b) => {
            let valA = a.dataset.name || '';
            let valB = b.dataset.name || '';

            if (!valA) valA = a.querySelector('.filename-overlay')?.textContent || '';
            if (!valB) valB = b.querySelector('.filename-overlay')?.textContent || '';

            const comparison = valA.localeCompare(valB, undefined, { numeric: true, sensitivity: 'base' });
            return order === 'asc' ? comparison : -comparison;
        });

        items.forEach(item => grid.appendChild(item));

        const mode = viewModeSelect ? viewModeSelect.value : 'masonry';
        if (mode === 'masonry') {
            var msnry = getMasonry();
            if (msnry) { msnry.reloadItems(); msnry.layout(); }
        }
    }

    if (colCountSelect) {
        colCountSelect.addEventListener('change', function () {
            const val = this.value;
            updateColumnCount(val === 'auto' ? 'auto' : parseInt(val));
        });
    }

    if (sortSelect) {
        sortSelect.addEventListener('change', function () {
            const [criteria, order] = this.value.split('-');
            sortItems(criteria, order);
        });
    }

});
