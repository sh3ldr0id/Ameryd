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

    // View Mode Logic
    function applyViewMode(mode) {
        const grid = document.getElementById('gallery-grid');
        if (!grid) return;

        // Remove existing view classes
        grid.classList.remove('view-grid', 'view-list');

        const msnry = getMasonry();

        if (mode === 'masonry') {
            if (!msnry) {
                initMasonry();
            } else {
                msnry.layout();
            }
        } else {
            // Disable Masonry for Grid/List
            if (msnry) {
                msnry.destroy();
            }
            // Add View Class
            if (mode === 'grid') grid.classList.add('view-grid');
            if (mode === 'list') grid.classList.add('view-list');
        }

        localStorage.setItem('viewMode', mode);

        // Update Column Control Visibility
        if (colCountSelect) {
            colCountSelect.parentElement.style.display = (mode === 'list') ? 'none' : 'block';
        }
    }

    // Init View Mode
    const savedViewMode = localStorage.getItem('viewMode') || 'masonry';
    if (viewModeSelect) {
        viewModeSelect.value = savedViewMode;
        // Apply immediately (no timeout needed if we manage init correctly)
        applyViewMode(savedViewMode);

        viewModeSelect.addEventListener('change', function () {
            applyViewMode(this.value);
        });
    } else {
        // Fallback if sidebar is not present but grid exists (e.g. public view without sidebar?)
        // Currently sidebar is always present. But good to be safe.
        // If no selector, default to masonry init if mode is masonry
        if (savedViewMode === 'masonry') initMasonry();
    }

    // Column Count Logic
    function updateColumnCount(count) {
        const grid = document.getElementById('gallery-grid');
        if (!grid) return;

        // Reset classes
        const cols = grid.querySelectorAll('[class*="col-"]');
        cols.forEach(col => {
            // Remove existing col-md, col-lg, etc. classes related to width
            // We want to force a specific width based on count/per row
            // Simple approach: remove all responsive col classes and add standard ones
            // But we actually just want to override.
            // Let's rely on adding/removing specific classes from a list logic or simple CSS variable?
            // Actually, manipulating bootstrap classes is tricky if we want to retain responsiveness.
            // EASIER: remove all col-* classes and replace with specific usage based on selection.

            // However, sticking to the user request: "Column count controls"
            // Let's apply a class to the GRID container and use CSS overrides if possible,
            // OR brute force the classes on items. Brute force is reliable.

            // Regex to clear column classes
            col.className = col.className.replace(/col-(md|lg|xl|xxl)?-?\d+/g, '').trim();

            if (count === 'auto' || isNaN(count)) {
                // Auto / Responsive Mode (2 on mobile, 3 on md, 4 on lg)
                col.classList.add('col-6', 'col-md-4', 'col-lg-3');
            } else {
                // Fixed Count Mode
                col.classList.add('col-' + (12 / count));
            }
            col.classList.add('mb-2'); // Restore margin
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
            // Use dataset.name for reliable sorting
            let valA = a.dataset.name || '';
            let valB = b.dataset.name || '';

            // Fallback just in case
            if (!valA) valA = a.querySelector('.filename-overlay')?.textContent || '';
            if (!valB) valB = b.querySelector('.filename-overlay')?.textContent || '';

            // Natural sort (numeric: true)
            // sensitivity: 'base' ignores simple case differences (a vs A)
            // which is good for filenames.

            const comparison = valA.localeCompare(valB, undefined, { numeric: true, sensitivity: 'base' });

            return order === 'asc' ? comparison : -comparison;
        });

        // Re-append
        items.forEach(item => grid.appendChild(item));

        // Layout if masonry is active
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
