/**
 * DynamicGallery — Zoom-driven masonry layout with virtualization.
 * Controls: Ctrl+Scroll / Trackpad Pinch / Touch Pinch to zoom.
 * Normal scroll scrolls. Column count snaps to integer steps.
 */
class DynamicGallery {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.items = []; // { filename, thumb_url, full_url, width, height }
        this.options = Object.assign({
            minCols: 1,
            maxCols: 12,
            gap: 6,
            buffer: 800,   // px to render outside viewport
        }, options);

        // Responsive default columns
        const w = window.innerWidth;
        this.colCount = w < 576 ? 3 : w < 992 ? 4 : 5;

        this.containerWidth = 0;
        this.itemPositions = []; // { top, left, width, height, data }
        this.totalHeight = 0;
        this.visibleIndices = new Set();
        this.domPool = new Map(); // index -> element

        // Create viewport (the tall absolutely-positioned child)
        this.viewport = null;
        this.isActive = false;
        this._resizeObserver = null;
        this._rafId = null;
        this._pendingRender = false;

        // Touch pinch state
        this._lastPinchDist = 0;
        this._pinchAccum = 0;

        // Bind handlers
        this._onScroll = this._onScroll.bind(this);
        this._onWheel = this._onWheel.bind(this);
        this._onTouchStart = this._onTouchStart.bind(this);
        this._onTouchMove = this._onTouchMove.bind(this);
        this._onTouchEnd = this._onTouchEnd.bind(this);
    }

    // ── Public API ──────────────────────────────────────────────

    init() {
        if (this.isActive || !this.container) return;
        this.isActive = true;

        // Clear container
        this.container.innerHTML = '';
        this.viewport = document.createElement('div');
        this.viewport.className = 'dynamic-viewport';
        this.viewport.style.cssText = 'position:relative;width:100%;overflow:hidden;';
        this.container.appendChild(this.viewport);

        // Event listeners
        window.addEventListener('scroll', this._onScroll, { passive: true });
        this.container.addEventListener('wheel', this._onWheel, { passive: false });
        this.container.addEventListener('touchstart', this._onTouchStart, { passive: false });
        this.container.addEventListener('touchmove', this._onTouchMove, { passive: false });
        this.container.addEventListener('touchend', this._onTouchEnd, { passive: true });

        this._resizeObserver = new ResizeObserver(() => {
            this._layout();
            this._scheduleRender();
        });
        this._resizeObserver.observe(this.container);

        this._layout();
        this._scheduleRender();
    }

    destroy() {
        if (!this.isActive) return;
        this.isActive = false;

        window.removeEventListener('scroll', this._onScroll);
        this.container.removeEventListener('wheel', this._onWheel);
        this.container.removeEventListener('touchstart', this._onTouchStart);
        this.container.removeEventListener('touchmove', this._onTouchMove);
        this.container.removeEventListener('touchend', this._onTouchEnd);

        if (this._resizeObserver) this._resizeObserver.disconnect();
        if (this._rafId) cancelAnimationFrame(this._rafId);

        this.viewport.innerHTML = '';
        this.viewport.style.height = '0';
        this.domPool.clear();
        this.visibleIndices.clear();
    }

    /** Append items (e.g. from paginated API). */
    addItems(newItems) {
        this.items = this.items.concat(newItems);
        this._layout();
        this._scheduleRender();
    }

    /** Replace all items. */
    setItems(items) {
        this.items = items;
        this._layout();
        this._scheduleRender();
    }

    // ── Layout ──────────────────────────────────────────────────

    _layout() {
        if (!this.container) return;
        this.containerWidth = this.container.clientWidth;
        if (this.containerWidth <= 0 || this.items.length === 0) {
            this.totalHeight = 0;
            this.itemPositions = [];
            if (this.viewport) this.viewport.style.height = '0px';
            return;
        }

        const gap = this.options.gap;
        const cols = this.colCount;
        const colW = (this.containerWidth - (cols - 1) * gap) / cols;
        const rowH = colW; // Unified height for grid

        this.itemPositions = this.items.map((item, idx) => {
            const row = Math.floor(idx / cols);
            const col = idx % cols;
            const left = col * (colW + gap);
            const top = row * (rowH + gap);
            return { left, top, width: colW, height: rowH, data: item };
        });

        const numRows = Math.ceil(this.items.length / cols);
        this.totalHeight = numRows * (rowH + gap) - gap;
        if (this.viewport) this.viewport.style.height = `${Math.max(0, this.totalHeight)}px`;
    }

    // ── Render (virtualization) ─────────────────────────────────

    _scheduleRender() {
        if (this._pendingRender) return;
        this._pendingRender = true;
        this._rafId = requestAnimationFrame(() => {
            this._pendingRender = false;
            this._render();
        });
    }

    _render() {
        if (!this.isActive) return;
        const scrollY = window.scrollY || window.pageYOffset;
        const vpH = window.innerHeight;
        const buf = this.options.buffer;

        // Offset of the container relative to page
        const containerTop = this.container.getBoundingClientRect().top + scrollY;
        const startY = scrollY - containerTop - buf;
        const endY = scrollY - containerTop + vpH + buf;

        const newVisible = new Set();

        for (let i = 0; i < this.itemPositions.length; i++) {
            const p = this.itemPositions[i];
            if (p.top + p.height > startY && p.top < endY) {
                newVisible.add(i);
            }
        }

        // Remove old
        this.visibleIndices.forEach(idx => {
            if (!newVisible.has(idx)) {
                const el = this.domPool.get(idx);
                if (el) { el.remove(); this.domPool.delete(idx); }
            }
        });

        // Add new
        newVisible.forEach(idx => {
            if (!this.visibleIndices.has(idx)) {
                const el = this._createEl(idx);
                if (el) { this.viewport.appendChild(el); this.domPool.set(idx, el); }
            } else {
                // Update position if layout changed
                const el = this.domPool.get(idx);
                if (el) this._positionEl(el, idx);
            }
        });

        this.visibleIndices = newVisible;
    }

    _createEl(idx) {
        const pos = this.itemPositions[idx];
        if (!pos) return null;
        const item = pos.data;

        const el = document.createElement('div');
        el.className = 'dynamic-item';
        el.dataset.index = idx;

        this._positionEl(el, idx);

        const link = document.createElement('a');
        link.href = item.full_url;
        link.target = '_blank';
        link.style.cssText = 'display:block;width:100%;height:100%;border-radius:8px;overflow:hidden;background:#1a1a1a;';

        const img = document.createElement('img');
        img.src = item.thumb_url;
        img.alt = item.filename || '';
        img.loading = 'lazy';
        img.style.cssText = 'width:100%;height:100%;object-fit:cover;opacity:0;transition:opacity .25s;';
        img.onload = () => { img.style.opacity = '1'; };

        link.appendChild(img);
        el.appendChild(link);
        return el;
    }

    _positionEl(el, idx) {
        const pos = this.itemPositions[idx];
        if (!pos) return;
        el.style.cssText = `position:absolute;left:${pos.left}px;top:${pos.top}px;width:${pos.width}px;height:${pos.height}px;transition:left .25s,top .25s,width .25s,height .25s;`;
    }

    // ── Scroll ──────────────────────────────────────────────────

    _onScroll() {
        this._scheduleRender();
    }

    // ── Zoom (Desktop: Ctrl+Wheel / Trackpad Pinch) ─────────────

    _onWheel(e) {
        // Ctrl+Wheel === trackpad pinch on most platforms
        if (!e.ctrlKey && !e.metaKey) return;
        e.preventDefault();

        const delta = e.deltaY;
        let newCols = this.colCount;
        if (delta > 0) newCols++;      // zoom out → more columns
        else if (delta < 0) newCols--; // zoom in  → fewer columns

        newCols = this._clampCols(newCols);
        if (newCols !== this.colCount) {
            this._zoomTo(newCols, e.clientX, e.clientY);
        }
    }

    // ── Zoom (Mobile: Touch Pinch) ──────────────────────────────

    _onTouchStart(e) {
        if (e.touches.length === 2) {
            e.preventDefault();
            this._lastPinchDist = this._touchDist(e.touches);
            this._pinchAccum = 0;
        }
    }

    _onTouchMove(e) {
        if (e.touches.length !== 2) return;
        e.preventDefault();
        const dist = this._touchDist(e.touches);
        const diff = dist - this._lastPinchDist;
        this._pinchAccum += diff;
        this._lastPinchDist = dist;

        // Threshold before snapping
        const threshold = 60;
        if (Math.abs(this._pinchAccum) > threshold) {
            let newCols = this.colCount;
            if (this._pinchAccum < 0) newCols++;  // pinch in  → more cols
            else newCols--;                        // pinch out → fewer cols
            newCols = this._clampCols(newCols);
            this._pinchAccum = 0;

            if (newCols !== this.colCount) {
                const cx = (e.touches[0].clientX + e.touches[1].clientX) / 2;
                const cy = (e.touches[0].clientY + e.touches[1].clientY) / 2;
                this._zoomTo(newCols, cx, cy);
            }
        }
    }

    _onTouchEnd() {
        this._lastPinchDist = 0;
        this._pinchAccum = 0;
    }

    _touchDist(touches) {
        const dx = touches[0].clientX - touches[1].clientX;
        const dy = touches[0].clientY - touches[1].clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    // ── Core zoom logic ─────────────────────────────────────────

    _clampCols(n) {
        return Math.max(this.options.minCols, Math.min(this.options.maxCols, n));
    }

    _zoomTo(newCols, anchorX, anchorY) {
        // Subtle haptic feedback
        if (navigator.vibrate) navigator.vibrate(5);

        const scrollY = window.scrollY || window.pageYOffset;
        const rect = this.container.getBoundingClientRect();
        const containerTop = rect.top + scrollY;
        const containerLeft = rect.left + (window.scrollX || 0);

        const absX = (anchorX || window.innerWidth / 2) - containerLeft;
        const absY = scrollY + (anchorY || window.innerHeight / 2) - containerTop;

        // Find anchor item (the one under the cursor/focal point)
        let anchorIdx = -1;
        let anchorRatioY = 0.5; // Default to center

        for (const i of this.visibleIndices) {
            const p = this.itemPositions[i];
            if (p && absX >= p.left && absX <= p.left + p.width &&
                absY >= p.top && absY <= p.top + p.height) {
                anchorIdx = i;
                anchorRatioY = (absY - p.top) / p.height;
                break;
            }
        }

        // Fallback: If no item is directly under cursor, find the closest one
        if (anchorIdx === -1) {
            let minDist = Infinity;
            for (const i of this.visibleIndices) {
                const p = this.itemPositions[i];
                if (!p) continue;
                const midX = p.left + p.width / 2;
                const midY = p.top + p.height / 2;
                const dist = Math.sqrt(Math.pow(absX - midX, 2) + Math.pow(absY - midY, 2));
                if (dist < minDist) {
                    minDist = dist;
                    anchorIdx = i;
                    anchorRatioY = (absY - p.top) / p.height;
                }
            }
        }

        // Re-layout with new cols
        this.colCount = newCols;

        // Clear all DOM and re-render cleanly after layout change
        this.domPool.forEach(el => el.remove());
        this.domPool.clear();
        this.visibleIndices.clear();

        this._layout();

        // Restore scroll so the focal point stays under the cursor
        if (anchorIdx !== -1 && this.itemPositions[anchorIdx]) {
            const newP = this.itemPositions[anchorIdx];
            const newAbsY = newP.top + (anchorRatioY * newP.height);
            const targetScrollY = newAbsY - (anchorY || window.innerHeight / 2) + containerTop;
            window.scrollTo(0, Math.max(0, targetScrollY));
        }

        this._render();
    }
}

// Expose globally
window.DynamicGallery = DynamicGallery;
