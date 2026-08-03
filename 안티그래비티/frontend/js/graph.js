/**
 * 지식 그래프 탐색기 (Interactive Knowledge Graph Explorer)
 * 전체 아티클 간의 유기적 상호 연결망을 안정적인 물리 시뮬레이션과 HUD 툴팁으로 시각화합니다.
 */

class KnowledgeGraph {
  constructor(canvasId, articles, categories, onNodeClick) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.articles = articles || [];
    this.categories = categories || [];
    this.onNodeClick = onNodeClick;

    // 카테고리별 컬러 팔레트 & 라벨
    this.categoryInfo = {
      'part-1': { color: '#3B82F6', name: '1. 개념/제도' },
      'part-2': { color: '#8B5CF6', name: '2. 사업 비교' },
      'part-3': { color: '#10B981', name: '3. 절차/동의' },
      'part-4': { color: '#F59E0B', name: '4. 혜택/인센티브' },
      'part-5': { color: '#EF4444', name: '5. 갈등/보상' },
      'part-6': { color: '#06B6D4', name: '6. 투자/자격' },
      'part-7': { color: '#EC4899', name: '7. 주요 후보지' },
      'part-8': { color: '#6366F1', name: '8. 미래 전망' }
    };

    this.nodes = [];
    this.links = [];
    this.activeCategory = 'all';
    this.hoveredNode = null;
    this.draggedNode = null;
    this.transform = { x: 0, y: 0, k: 1 };
    this.isDraggingCanvas = false;
    this.dragStart = { x: 0, y: 0 };
    this.animId = null;
    this.simulationRunning = true;
    this.simTicks = 0;

    // DOM Tooltip
    this.tooltipEl = document.getElementById('graphTooltip');

    this.init();
  }

  setArticles(articles, categories) {
    if (articles && articles.length > 0) {
      this.articles = articles;
    }
    if (categories && categories.length > 0) {
      this.categories = categories;
    }
    this.buildGraph();
    this.resetView();
  }

  init() {
    this.resize();
    this.buildGraph();
    this.bindEvents();
    this.startSimulation();
  }

  resize() {
    if (!this.canvas) return;
    const parent = this.canvas.parentElement;
    const parentW = parent ? parent.clientWidth : 0;
    const parentH = parent ? parent.clientHeight : 0;

    this.width = parentW > 50 ? parentW : 880;
    this.height = parentH > 50 ? parentH : 560;

    const dpr = window.devicePixelRatio || 1;
    this.dpr = dpr;
    this.canvas.width = Math.floor(this.width * dpr);
    this.canvas.height = Math.floor(this.height * dpr);
    this.canvas.style.width = '100%';
    this.canvas.style.height = '100%';

    this.draw();
  }

  buildGraph() {
    if (!this.articles || this.articles.length === 0) {
      if (typeof window !== 'undefined' && window.ARTICLES_DB && window.ARTICLES_DB.length > 0) {
        this.articles = window.ARTICLES_DB;
      } else {
        return;
      }
    }

    const centerX = this.width / 2;
    const centerY = this.height / 2;
    const catKeys = Object.keys(this.categoryInfo);

    // 1. 카테고리별 클러스터 중심점 계산 (원형 배치)
    const catCenters = {};
    catKeys.forEach((k, i) => {
      const angle = (i / catKeys.length) * Math.PI * 2 - Math.PI / 2;
      const radius = Math.min(this.width, this.height) * 0.32;
      catCenters[k] = {
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius
      };
    });
    this.catCenters = catCenters;

    // 2. 노드 생성 (클러스터 주변에 안정적으로 분산)
    this.nodes = this.articles.map((art, idx) => {
      const catId = art.categoryId || 'part-1';
      const c = catCenters[catId] || { x: centerX, y: centerY };
      const catItems = this.articles.filter(a => a.categoryId === catId);
      const subIdx = Math.max(0, catItems.findIndex(a => a.id === art.id));
      const totalInCat = Math.max(1, catItems.length);
      const subAngle = (subIdx / totalInCat) * Math.PI * 2;
      const subRadius = 45 + (subIdx % 3) * 18;

      const info = this.categoryInfo[catId] || { color: '#3B82F6', name: art.category };

      return {
        id: art.id,
        order: art.order || (idx + 1),
        title: art.title || `글 ${idx + 1}`,
        category: art.category || info.name,
        categoryId: catId,
        summary: art.easySummary || art.summary || '',
        readingTime: art.readingTime || '4분',
        color: info.color,
        radius: 14,
        x: c.x + Math.cos(subAngle) * subRadius,
        y: c.y + Math.sin(subAngle) * subRadius,
        vx: 0,
        vy: 0,
        related: art.relatedPostIds || []
      };
    });

    // 3. 엣지(연결선) 생성
    this.links = [];
    const nodeMap = new Map(this.nodes.map(n => [n.id, n]));

    this.nodes.forEach(source => {
      source.related.forEach(targetId => {
        const target = nodeMap.get(targetId);
        if (target && source.id !== target.id) {
          this.links.push({
            source,
            target,
            color: source.color
          });
        }
      });
    });

    this.simTicks = 0;
    this.simulationRunning = true;
  }

  startSimulation() {
    const tick = () => {
      if (this.simulationRunning || this.draggedNode) {
        this.stepSimulation();
        this.simTicks++;
        if (this.simTicks > 200 && !this.draggedNode) {
          this.simulationRunning = false;
        }
      }
      this.draw();
      this.animId = requestAnimationFrame(tick);
    };

    if (this.animId) cancelAnimationFrame(this.animId);
    this.animId = requestAnimationFrame(tick);
  }

  stepSimulation() {
    const len = this.nodes.length;
    if (len === 0) return;

    const centerX = this.width / 2;
    const centerY = this.height / 2;
    const catCenters = this.catCenters || {};

    // 1. 노드 간 반발력 (충돌 방지 및 최소 간격 유지)
    for (let i = 0; i < len; i++) {
      const n1 = this.nodes[i];
      for (let j = i + 1; j < len; j++) {
        const n2 = this.nodes[j];
        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const dist = Math.hypot(dx, dy) || 1;
        const minDist = 40;
        
        if (dist < minDist) {
          const force = ((minDist - dist) / dist) * 0.05;
          const fx = dx * force;
          const fy = dy * force;
          n1.vx -= fx;
          n1.vy -= fy;
          n2.vx += fx;
          n2.vy += fy;
        }
      }
    }

    // 2. 링크 스프링 장력 (정규화된 안정 인력)
    for (let i = 0; i < this.links.length; i++) {
      const link = this.links[i];
      const dx = link.target.x - link.source.x;
      const dy = link.target.y - link.source.y;
      const dist = Math.hypot(dx, dy) || 1;
      const idealDist = 70;
      
      const force = (dist - idealDist) * 0.002;
      const nx = dx / dist;
      const ny = dy / dist;
      
      link.source.vx += nx * force * 8;
      link.source.vy += ny * force * 8;
      link.target.vx -= nx * force * 8;
      link.target.vy -= ny * force * 8;
    }

    // 3. 카테고리 클러스터 복원력 & 감쇠
    for (let i = 0; i < len; i++) {
      const node = this.nodes[i];
      if (node === this.draggedNode) continue;

      const cluster = catCenters[node.categoryId] || { x: centerX, y: centerY };

      // 클러스터 중심으로 부드럽게 유도
      const cdx = cluster.x - node.x;
      const cdy = cluster.y - node.y;
      node.vx += cdx * 0.015;
      node.vy += cdy * 0.015;

      // 속도 제한 및 마찰
      node.vx = Math.max(-6, Math.min(6, node.vx * 0.85));
      node.vy = Math.max(-6, Math.min(6, node.vy * 0.85));

      node.x += node.vx;
      node.y += node.vy;
    }
  }

  draw() {
    if (!this.ctx) return;

    const dpr = this.dpr || 1;
    this.ctx.save();
    this.ctx.scale(dpr, dpr);
    this.ctx.clearRect(0, 0, this.width, this.height);

    const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark';

    // 줌/팬 변환 적용
    this.ctx.save();
    this.ctx.translate(this.transform.x, this.transform.y);
    this.ctx.scale(this.transform.k, this.transform.k);

    const activeHover = this.hoveredNode;
    const activeCat = this.activeCategory;

    // 0. 카테고리 클러스터 배경 허브 표시
    if (this.catCenters) {
      Object.keys(this.categoryInfo).forEach(catId => {
        const c = this.catCenters[catId];
        if (!c) return;
        const info = this.categoryInfo[catId];
        const isCatMatch = activeCat === 'all' || activeCat === catId;

        this.ctx.save();
        this.ctx.globalAlpha = isCatMatch ? (isDarkMode ? 0.08 : 0.05) : 0.02;
        this.ctx.beginPath();
        this.ctx.arc(c.x, c.y, 80, 0, Math.PI * 2);
        this.ctx.fillStyle = info.color;
        this.ctx.fill();

        // 허브 텍스트
        this.ctx.globalAlpha = isCatMatch ? (isDarkMode ? 0.5 : 0.4) : 0.15;
        this.ctx.fillStyle = info.color;
        this.ctx.font = 'bold 11px Pretendard, sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(info.name, c.x, c.y - 88);
        this.ctx.restore();
      });
    }

    // 1. 엣지(연결선) 렌더링
    for (let i = 0; i < this.links.length; i++) {
      const link = this.links[i];
      const s = link.source;
      const t = link.target;

      const isConnectedToHover = activeHover && (s.id === activeHover.id || t.id === activeHover.id);
      const isCatMatch = activeCat === 'all' || s.categoryId === activeCat || t.categoryId === activeCat;

      this.ctx.beginPath();
      this.ctx.moveTo(s.x, s.y);
      this.ctx.lineTo(t.x, t.y);

      if (isConnectedToHover) {
        this.ctx.strokeStyle = '#F59E0B';
        this.ctx.lineWidth = 2.5;
        this.ctx.globalAlpha = 1.0;
      } else if (activeHover) {
        this.ctx.strokeStyle = isDarkMode ? '#334155' : '#CBD5E1';
        this.ctx.lineWidth = 0.5;
        this.ctx.globalAlpha = 0.08;
      } else if (!isCatMatch) {
        this.ctx.strokeStyle = isDarkMode ? '#1E293B' : '#E2E8F0';
        this.ctx.lineWidth = 0.4;
        this.ctx.globalAlpha = 0.06;
      } else {
        this.ctx.strokeStyle = isDarkMode ? '#475569' : '#94A3B8';
        this.ctx.lineWidth = 1.0;
        this.ctx.globalAlpha = 0.35;
      }
      this.ctx.stroke();
    }

    // 2. 노드 렌더링
    for (let i = 0; i < this.nodes.length; i++) {
      const node = this.nodes[i];
      const isHovered = activeHover && activeHover.id === node.id;
      const isNeighbor = activeHover && activeHover.related && activeHover.related.includes(node.id);
      const isCatMatch = activeCat === 'all' || node.categoryId === activeCat;

      let alpha = 1.0;
      if (activeHover) {
        alpha = isHovered ? 1.0 : (isNeighbor ? 0.9 : 0.15);
      } else if (!isCatMatch) {
        alpha = 0.2;
      }

      this.ctx.save();
      this.ctx.globalAlpha = alpha;

      const nodeRadius = isHovered ? node.radius + 5 : (isNeighbor ? node.radius + 2 : node.radius);

      // 글로우 링 (호버/인접 노드)
      if (isHovered || isNeighbor) {
        this.ctx.beginPath();
        this.ctx.arc(node.x, node.y, nodeRadius + 4, 0, Math.PI * 2);
        this.ctx.fillStyle = isHovered ? '#F59E0B' : node.color;
        this.ctx.globalAlpha = isHovered ? 0.45 : 0.25;
        this.ctx.fill();
        this.ctx.globalAlpha = alpha;
      }

      // 바깥 원 (카테고리 컬러)
      this.ctx.beginPath();
      this.ctx.arc(node.x, node.y, nodeRadius, 0, Math.PI * 2);
      this.ctx.fillStyle = node.color;
      this.ctx.fill();

      // 안쪽 배경 원
      this.ctx.beginPath();
      this.ctx.arc(node.x, node.y, nodeRadius - 3.5, 0, Math.PI * 2);
      this.ctx.fillStyle = isDarkMode ? '#0B0F19' : '#FFFFFF';
      this.ctx.fill();

      // 글 번호 (VOL 번호)
      this.ctx.fillStyle = isDarkMode ? '#FFFFFF' : '#0F172A';
      this.ctx.font = `bold ${isHovered ? 11 : 9}px Inter, sans-serif`;
      this.ctx.textAlign = 'center';
      this.ctx.textBaseline = 'middle';
      this.ctx.fillText(`${node.order}`, node.x, node.y);

      // 글 제목 라벨 (호버, 인접, 또는 줌인 시 노출)
      if (isHovered || isNeighbor || this.transform.k > 1.25) {
        this.ctx.font = isHovered ? 'bold 12px Pretendard, sans-serif' : '10px Pretendard, sans-serif';
        
        let label = node.title;
        if (label.length > 20 && !isHovered) {
          label = label.substring(0, 18) + '…';
        }
        
        const metrics = this.ctx.measureText(label);
        const pad = 4;
        this.ctx.fillStyle = isDarkMode ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.95)';
        this.ctx.fillRect(node.x - metrics.width / 2 - pad, node.y + nodeRadius + 3, metrics.width + pad * 2, 16);

        this.ctx.fillStyle = isHovered ? '#2563EB' : (isDarkMode ? '#F8FAFC' : '#0F172A');
        this.ctx.fillText(label, node.x, node.y + nodeRadius + 11);
      }

      this.ctx.restore();
    }

    this.ctx.restore(); // restore zoom & pan
    this.ctx.restore(); // restore dpr
  }

  bindEvents() {
    let clickCandidate = null;
    let mouseDownPos = { x: 0, y: 0 };

    const getCanvasPos = (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      const rawX = clientX - rect.left;
      const rawY = clientY - rect.top;

      return {
        x: (rawX - this.transform.x) / this.transform.k,
        y: (rawY - this.transform.y) / this.transform.k,
        rawX,
        rawY,
        clientX,
        clientY
      };
    };

    const findNodeAt = (x, y) => {
      for (let i = this.nodes.length - 1; i >= 0; i--) {
        const n = this.nodes[i];
        const dx = n.x - x;
        const dy = n.y - y;
        const hitR = n.radius + 8;
        if (dx * dx + dy * dy < hitR * hitR) {
          return n;
        }
      }
      return null;
    };

    this.canvas.addEventListener('mousedown', (e) => {
      const pos = getCanvasPos(e);
      mouseDownPos = { x: pos.rawX, y: pos.rawY };
      const node = findNodeAt(pos.x, pos.y);

      if (node) {
        this.draggedNode = node;
        clickCandidate = node;
        this.simulationRunning = true;
      } else {
        this.isDraggingCanvas = true;
        this.dragStart = { x: pos.rawX - this.transform.x, y: pos.rawY - this.transform.y };
        clickCandidate = null;
      }
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.canvas) return;
      const pos = getCanvasPos(e);

      if (this.draggedNode) {
        this.draggedNode.x = pos.x;
        this.draggedNode.y = pos.y;
        this.draggedNode.vx = 0;
        this.draggedNode.vy = 0;
        const moveDist = Math.hypot(pos.rawX - mouseDownPos.x, pos.rawY - mouseDownPos.y);
        if (moveDist > 6) {
          clickCandidate = null;
        }
        this.hideTooltip();
      } else if (this.isDraggingCanvas) {
        this.transform.x = pos.rawX - this.dragStart.x;
        this.transform.y = pos.rawY - this.dragStart.y;
        const moveDist = Math.hypot(pos.rawX - mouseDownPos.x, pos.rawY - mouseDownPos.y);
        if (moveDist > 6) {
          clickCandidate = null;
        }
        this.hideTooltip();
      } else {
        const hovered = findNodeAt(pos.x, pos.y);
        if (this.hoveredNode !== hovered) {
          this.hoveredNode = hovered;
          this.canvas.style.cursor = hovered ? 'pointer' : 'grab';
          if (hovered) {
            this.showTooltip(hovered, pos.rawX, pos.rawY);
          } else {
            this.hideTooltip();
          }
        }
      }
    });

    window.addEventListener('mouseup', () => {
      if (clickCandidate && this.onNodeClick) {
        this.onNodeClick(clickCandidate.id);
      }
      this.draggedNode = null;
      this.isDraggingCanvas = false;
      clickCandidate = null;
    });

    // Zoom on wheel
    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const pos = getCanvasPos(e);
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
      const newScale = Math.max(0.35, Math.min(3.5, this.transform.k * zoomFactor));

      this.transform.x = pos.rawX - (pos.rawX - this.transform.x) * (newScale / this.transform.k);
      this.transform.y = pos.rawY - (pos.rawY - this.transform.y) * (newScale / this.transform.k);
      this.transform.k = newScale;
      this.hideTooltip();
    }, { passive: false });

    // Window resize
    window.addEventListener('resize', () => {
      this.resize();
    });
  }

  showTooltip(node, x, y) {
    if (!this.tooltipEl) return;
    this.tooltipEl.innerHTML = `
      <div style="display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.3rem;">
        <span style="font-size: 0.72rem; font-weight: 800; color: ${node.color}; background: rgba(0,0,0,0.06); padding: 0.15rem 0.4rem; border-radius: 4px;">VOL.${String(node.order).padStart(2, '0')}</span>
        <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">${node.category}</span>
      </div>
      <div style="font-size: 0.92rem; font-weight: 800; color: var(--text-primary); line-height: 1.35; margin-bottom: 0.4rem;">${node.title}</div>
      <div style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.4; margin-bottom: 0.5rem;">${(node.summary || '').substring(0, 70)}…</div>
      <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-color); padding-top: 0.4rem; font-size: 0.75rem;">
        <span style="color: #2563EB; font-weight: 700;">🔗 연계 글 ${node.related.length}편</span>
        <span style="color: var(--text-muted); font-weight: 600;">👉 클릭하여 글 읽기</span>
      </div>
    `;
    this.tooltipEl.style.display = 'block';

    const ttWidth = 280;
    const ttHeight = 130;
    let left = x + 18;
    let top = y + 18;

    if (left + ttWidth > this.width) {
      left = x - ttWidth - 18;
    }
    if (top + ttHeight > this.height) {
      top = y - ttHeight - 18;
    }

    this.tooltipEl.style.left = `${Math.max(10, left)}px`;
    this.tooltipEl.style.top = `${Math.max(10, top)}px`;
  }

  hideTooltip() {
    if (this.tooltipEl) {
      this.tooltipEl.style.display = 'none';
    }
  }

  zoomIn() {
    this.transform.k = Math.min(3.5, this.transform.k * 1.25);
  }

  zoomOut() {
    this.transform.k = Math.max(0.35, this.transform.k * 0.8);
  }

  resetView() {
    this.transform = { x: 0, y: 0, k: 1 };
    this.activeCategory = 'all';
    this.hoveredNode = null;
    this.hideTooltip();
    this.simulationRunning = true;
    this.simTicks = 0;
  }

  focusCategory(categoryId) {
    this.activeCategory = categoryId;
    this.hideTooltip();
    if (categoryId === 'all') {
      this.hoveredNode = null;
      return;
    }
    const match = this.nodes.find(n => n.categoryId === categoryId);
    if (match) {
      this.hoveredNode = match;
    }
  }

  searchNode(keyword) {
    if (!keyword) {
      this.activeCategory = 'all';
      this.hoveredNode = null;
      return;
    }
    const q = keyword.toLowerCase().trim();
    const found = this.nodes.find(n => n.title.toLowerCase().includes(q) || String(n.order) === q);
    if (found) {
      this.hoveredNode = found;
      this.transform.x = this.width / 2 - found.x * this.transform.k;
      this.transform.y = this.height / 2 - found.y * this.transform.k;
      this.showTooltip(found, this.width / 2, this.height / 2);
    }
  }
}

if (typeof window !== 'undefined') {
  window.KnowledgeGraph = KnowledgeGraph;
}
