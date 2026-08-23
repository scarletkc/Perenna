#!/usr/bin/env python3
# ruff: noqa: E501
"""Generate Perenna's SVG brand assets and local HTML preview."""

from __future__ import annotations

from pathlib import Path

# -------------------------------------------------------------
# 1. Primary Square Icon (Dark Canvas, 512x512)
# -------------------------------------------------------------
LOGO_DARK_SQUARE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <!-- Background Gradient -->
    <radialGradient id="bgGrad" cx="50%" cy="35%" r="68%">
      <stop offset="0%" stop-color="#191c38"/>
      <stop offset="55%" stop-color="#0c1022"/>
      <stop offset="100%" stop-color="#05070e"/>
    </radialGradient>

    <!-- Linear Gradients for Geometry -->
    <linearGradient id="pStemGrad" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="#4f46e5"/>
      <stop offset="45%" stop-color="#7c3aed"/>
      <stop offset="100%" stop-color="#06b6d4"/>
    </linearGradient>

    <linearGradient id="pLoopGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#06b6d4"/>
      <stop offset="28%" stop-color="#3b82f6"/>
      <stop offset="68%" stop-color="#8b5cf6"/>
      <stop offset="100%" stop-color="#f43f5e"/>
    </linearGradient>

    <linearGradient id="gitTraceGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#6366f1"/>
      <stop offset="35%" stop-color="#22d3ee"/>
      <stop offset="75%" stop-color="#ec4899"/>
      <stop offset="100%" stop-color="#fb7185"/>
    </linearGradient>

    <!-- Node Radial Glows -->
    <radialGradient id="cyanGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="35%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#0284c7" stop-opacity="0"/>
    </radialGradient>

    <radialGradient id="pinkGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="35%" stop-color="#fb7185"/>
      <stop offset="100%" stop-color="#e11d48" stop-opacity="0"/>
    </radialGradient>

    <radialGradient id="purpleGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="35%" stop-color="#c084fc"/>
      <stop offset="100%" stop-color="#7e22ce" stop-opacity="0"/>
    </radialGradient>

    <!-- Glow Filters -->
    <filter id="glowFilter" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="9" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <filter id="softAura" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="36" result="aura"/>
    </filter>

    <filter id="shadowFilter" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="16" stdDeviation="20" flood-color="#000000" flood-opacity="0.65"/>
    </filter>
  </defs>

  <!-- Base Rounded Container -->
  <rect width="512" height="512" rx="118" fill="url(#bgGrad)"/>
  <rect width="508" height="508" x="2" y="2" rx="116" fill="none" stroke="#ffffff" stroke-opacity="0.08" stroke-width="2"/>

  <!-- Subtle Internal Grid / Matrix Background -->
  <g opacity="0.04" stroke="#ffffff" stroke-width="1.2">
    <line x1="64" y1="128" x2="448" y2="128"/>
    <line x1="64" y1="192" x2="448" y2="192"/>
    <line x1="64" y1="256" x2="448" y2="256"/>
    <line x1="64" y1="320" x2="448" y2="320"/>
    <line x1="64" y1="384" x2="448" y2="384"/>
    <line x1="128" y1="64" x2="128" y2="448"/>
    <line x1="192" y1="64" x2="192" y2="448"/>
    <line x1="256" y1="64" x2="256" y2="448"/>
    <line x1="320" y1="64" x2="320" y2="448"/>
    <line x1="384" y1="64" x2="384" y2="448"/>
  </g>

  <!-- Ambient Color Auras -->
  <circle cx="230" cy="220" r="130" fill="#6366f1" opacity="0.22" filter="url(#softAura)"/>
  <circle cx="340" cy="210" r="95" fill="#f43f5e" opacity="0.18" filter="url(#softAura)"/>
  <circle cx="170" cy="340" r="95" fill="#06b6d4" opacity="0.16" filter="url(#softAura)"/>

  <!-- Logo Symbol Group -->
  <g filter="url(#shadowFilter)">

    <!-- Glowing Loop Outer Shadow -->
    <path d="M 172 124
             C 272 124, 368 160, 368 238
             C 368 316, 272 352, 172 352
             L 172 292
             C 240 292, 308 268, 308 238
             C 308 208, 240 184, 172 184
             Z"
          fill="url(#pLoopGrad)" opacity="0.3" filter="url(#glowFilter)"/>

    <!-- P-Loop Solid Ribbon -->
    <path d="M 172 124
             C 274 124, 368 160, 368 238
             C 368 316, 274 352, 172 352
             L 172 294
             C 238 294, 308 270, 308 238
             C 308 206, 238 182, 172 182
             Z"
          fill="url(#pLoopGrad)"/>

    <!-- P-Stem (Git Trunk) -->
    <rect x="136" y="124" width="50" height="268" rx="25" fill="url(#pStemGrad)"/>

    <!-- Git Branch Circuit Path 1: Fork from trunk, loops through the head, converges back -->
    <path d="M 161 340
             L 161 240
             C 161 176, 232 152, 285 174
             C 338 196, 338 274, 285 298
             C 238 318, 188 288, 161 254"
          fill="none"
          stroke="url(#gitTraceGrad)"
          stroke-width="8"
          stroke-linecap="round"
          stroke-linejoin="round"
          filter="url(#glowFilter)"/>

    <!-- Git Nodes / Neural Synapses -->

    <!-- 1. Root Commit (Bottom Trunk) -->
    <circle cx="161" cy="340" r="20" fill="url(#cyanGlow)" opacity="0.7"/>
    <circle cx="161" cy="340" r="13" fill="#0d1120" stroke="#4f46e5" stroke-width="4"/>
    <circle cx="161" cy="340" r="5" fill="#ffffff"/>

    <!-- 2. Fork Node (Mid Trunk) -->
    <circle cx="161" cy="228" r="24" fill="url(#cyanGlow)" opacity="0.85"/>
    <circle cx="161" cy="228" r="15" fill="#0d1120" stroke="#06b6d4" stroke-width="4"/>
    <circle cx="161" cy="228" r="6" fill="#ffffff"/>

    <!-- 3. Upper Node -->
    <circle cx="278" cy="160" r="20" fill="url(#purpleGlow)" opacity="0.7"/>
    <circle cx="278" cy="160" r="13" fill="#0d1120" stroke="#a855f7" stroke-width="3.5"/>
    <circle cx="278" cy="160" r="5" fill="#ffffff"/>

    <!-- 4. Outer Node -->
    <circle cx="342" cy="238" r="26" fill="url(#pinkGlow)" opacity="0.9"/>
    <circle cx="342" cy="238" r="16" fill="#0d1120" stroke="#f43f5e" stroke-width="4.5"/>
    <circle cx="342" cy="238" r="6.5" fill="#ffffff"/>

    <!-- Central Spark -->
    <g transform="translate(244, 238)">
      <polygon points="0,-12 3.5,-3.5 12,0 3.5,3.5 0,12 -3.5,3.5 -12,0 -3.5,-3.5" fill="#ffffff" opacity="0.65"/>
      <circle cx="0" cy="0" r="2.5" fill="#22d3ee" opacity="0.75"/>
    </g>

  </g>
</svg>"""

# -------------------------------------------------------------
# 2. Transparent Standalone Icon (512x512)
# -------------------------------------------------------------
LOGO_TRANSPARENT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <!-- Linear Gradients -->
    <linearGradient id="pStemGradT" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="#4f46e5"/>
      <stop offset="45%" stop-color="#7c3aed"/>
      <stop offset="100%" stop-color="#06b6d4"/>
    </linearGradient>

    <linearGradient id="pLoopGradT" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#06b6d4"/>
      <stop offset="28%" stop-color="#3b82f6"/>
      <stop offset="68%" stop-color="#8b5cf6"/>
      <stop offset="100%" stop-color="#f43f5e"/>
    </linearGradient>

    <linearGradient id="gitTraceGradT" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#6366f1"/>
      <stop offset="35%" stop-color="#22d3ee"/>
      <stop offset="75%" stop-color="#ec4899"/>
      <stop offset="100%" stop-color="#fb7185"/>
    </linearGradient>

    <!-- Node Radial Glows -->
    <radialGradient id="cyanGlowT" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="35%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#0284c7" stop-opacity="0"/>
    </radialGradient>

    <radialGradient id="pinkGlowT" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="35%" stop-color="#fb7185"/>
      <stop offset="100%" stop-color="#e11d48" stop-opacity="0"/>
    </radialGradient>

    <radialGradient id="purpleGlowT" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="35%" stop-color="#c084fc"/>
      <stop offset="100%" stop-color="#7e22ce" stop-opacity="0"/>
    </radialGradient>

    <filter id="glowFilterT" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <filter id="shadowFilterT" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#000000" flood-opacity="0.35"/>
    </filter>
  </defs>

  <!-- Logo Graphics Group -->
  <g filter="url(#shadowFilterT)">

    <!-- P-Loop Solid Ribbon -->
    <path d="M 172 124
             C 274 124, 368 160, 368 238
             C 368 316, 274 352, 172 352
             L 172 294
             C 238 294, 308 270, 308 238
             C 308 206, 238 182, 172 182
             Z"
          fill="url(#pLoopGradT)"/>

    <!-- P-Stem (Git Trunk) -->
    <rect x="136" y="124" width="50" height="268" rx="25" fill="url(#pStemGradT)"/>

    <!-- Git Branch Circuit Path 1 -->
    <path d="M 161 340
             L 161 240
             C 161 176, 232 152, 285 174
             C 338 196, 338 274, 285 298
             C 238 318, 188 288, 161 254"
          fill="none"
          stroke="url(#gitTraceGradT)"
          stroke-width="8"
          stroke-linecap="round"
          stroke-linejoin="round"
          filter="url(#glowFilterT)"/>

    <!-- Git Nodes / Neural Synapses -->
    <circle cx="161" cy="340" r="18" fill="url(#cyanGlowT)" opacity="0.7"/>
    <circle cx="161" cy="340" r="13" fill="#0f172a" stroke="#4f46e5" stroke-width="4"/>
    <circle cx="161" cy="340" r="5" fill="#ffffff"/>

    <circle cx="161" cy="228" r="22" fill="url(#cyanGlowT)" opacity="0.85"/>
    <circle cx="161" cy="228" r="15" fill="#0f172a" stroke="#06b6d4" stroke-width="4"/>
    <circle cx="161" cy="228" r="6" fill="#ffffff"/>

    <circle cx="278" cy="160" r="18" fill="url(#purpleGlowT)" opacity="0.7"/>
    <circle cx="278" cy="160" r="13" fill="#0f172a" stroke="#a855f7" stroke-width="3.5"/>
    <circle cx="278" cy="160" r="5" fill="#ffffff"/>

    <circle cx="342" cy="238" r="24" fill="url(#pinkGlowT)" opacity="0.9"/>
    <circle cx="342" cy="238" r="16" fill="#0f172a" stroke="#f43f5e" stroke-width="4.5"/>
    <circle cx="342" cy="238" r="6.5" fill="#ffffff"/>

    <!-- Central Spark -->
    <g transform="translate(244, 238)">
      <polygon points="0,-12 3.5,-3.5 12,0 3.5,3.5 0,12 -3.5,3.5 -12,0 -3.5,-3.5" fill="#ffffff" opacity="0.65"/>
      <circle cx="0" cy="0" r="2.5" fill="#22d3ee" opacity="0.75"/>
    </g>
  </g>
</svg>"""

# -------------------------------------------------------------
# 3. Primary Horizontal Brand Banner (1200 x 360, Dark Theme)
# -------------------------------------------------------------
LOGO_BANNER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 360" width="100%" height="100%">
  <defs>
    <!-- Background Gradient -->
    <radialGradient id="bannerBg" cx="20%" cy="50%" r="90%">
      <stop offset="0%" stop-color="#14172f"/>
      <stop offset="45%" stop-color="#0a0d18"/>
      <stop offset="100%" stop-color="#04060b"/>
    </radialGradient>

    <!-- Text Gradients -->
    <linearGradient id="textGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="40%" stop-color="#f8fafc"/>
      <stop offset="70%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#c084fc"/>
    </linearGradient>

    <linearGradient id="subtextGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="50%" stop-color="#818cf8"/>
      <stop offset="100%" stop-color="#f43f5e"/>
    </linearGradient>

    <linearGradient id="tagBgGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#1e1b4b" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#0f172a" stop-opacity="0.8"/>
    </linearGradient>

    <!-- Icon Gradients -->
    <linearGradient id="bStemGrad" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="#4f46e5"/>
      <stop offset="45%" stop-color="#7c3aed"/>
      <stop offset="100%" stop-color="#06b6d4"/>
    </linearGradient>

    <linearGradient id="bLoopGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#06b6d4"/>
      <stop offset="28%" stop-color="#3b82f6"/>
      <stop offset="68%" stop-color="#8b5cf6"/>
      <stop offset="100%" stop-color="#f43f5e"/>
    </linearGradient>

    <linearGradient id="bGitTrace" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#6366f1"/>
      <stop offset="35%" stop-color="#22d3ee"/>
      <stop offset="75%" stop-color="#ec4899"/>
      <stop offset="100%" stop-color="#fb7185"/>
    </linearGradient>

    <radialGradient id="bPinkGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="35%" stop-color="#fb7185"/>
      <stop offset="100%" stop-color="#e11d48" stop-opacity="0"/>
    </radialGradient>

    <radialGradient id="bCyanGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="35%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#0284c7" stop-opacity="0"/>
    </radialGradient>

    <!-- Filters -->
    <filter id="bGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <filter id="bAura" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="45" result="aura"/>
    </filter>
  </defs>

  <!-- Banner Container with Modern Border -->
  <rect width="1200" height="360" rx="28" fill="url(#bannerBg)"/>
  <rect width="1196" height="356" x="2" y="2" rx="26" fill="none" stroke="#ffffff" stroke-opacity="0.08" stroke-width="2"/>

  <!-- Tech Grid Overlay in Banner Background -->
  <g opacity="0.03" stroke="#ffffff" stroke-width="1">
    <line x1="0" y1="72" x2="1200" y2="72"/>
    <line x1="0" y1="144" x2="1200" y2="144"/>
    <line x1="0" y1="216" x2="1200" y2="216"/>
    <line x1="0" y1="288" x2="1200" y2="288"/>
    <line x1="200" y1="0" x2="200" y2="360"/>
    <line x1="400" y1="0" x2="400" y2="360"/>
    <line x1="600" y1="0" x2="600" y2="360"/>
    <line x1="800" y1="0" x2="800" y2="360"/>
    <line x1="1000" y1="0" x2="1000" y2="360"/>
  </g>

  <!-- Background Decorative Lights -->
  <circle cx="180" cy="180" r="140" fill="#6366f1" opacity="0.22" filter="url(#bAura)"/>
  <circle cx="280" cy="160" r="90" fill="#f43f5e" opacity="0.16" filter="url(#bAura)"/>
  <circle cx="950" cy="180" r="180" fill="#3b82f6" opacity="0.08" filter="url(#bAura)"/>

  <!-- ================= LOGO ICON GROUP (Scaled & Centered at x=80, y=55) ================= -->
  <g transform="translate(70, 55) scale(0.48)">
    <!-- P-Loop -->
    <path d="M 172 124
             C 274 124, 368 160, 368 238
             C 368 316, 274 352, 172 352
             L 172 294
             C 238 294, 308 270, 308 238
             C 308 206, 238 182, 172 182
             Z"
          fill="url(#bLoopGrad)"/>

    <!-- P-Stem -->
    <rect x="136" y="124" width="50" height="268" rx="25" fill="url(#bStemGrad)"/>

    <!-- Git Branch Circuit Path 1 -->
    <path d="M 161 340
             L 161 240
             C 161 176, 232 152, 285 174
             C 338 196, 338 274, 285 298
             C 238 318, 188 288, 161 254"
          fill="none"
          stroke="url(#bGitTrace)"
          stroke-width="8"
          stroke-linecap="round"
          stroke-linejoin="round"
          filter="url(#bGlow)"/>

    <!-- Nodes -->
    <circle cx="161" cy="340" r="22" fill="url(#bCyanGlow)" opacity="0.7"/>
    <circle cx="161" cy="340" r="13" fill="#0f172a" stroke="#4f46e5" stroke-width="4"/>
    <circle cx="161" cy="340" r="5" fill="#ffffff"/>

    <circle cx="161" cy="228" r="24" fill="url(#bCyanGlow)" opacity="0.85"/>
    <circle cx="161" cy="228" r="15" fill="#0f172a" stroke="#06b6d4" stroke-width="4"/>
    <circle cx="161" cy="228" r="6" fill="#ffffff"/>

    <circle cx="278" cy="160" r="13" fill="#0f172a" stroke="#a855f7" stroke-width="3.5"/>
    <circle cx="278" cy="160" r="5" fill="#ffffff"/>

    <circle cx="342" cy="238" r="26" fill="url(#bPinkGlow)" opacity="0.9"/>
    <circle cx="342" cy="238" r="16" fill="#0f172a" stroke="#f43f5e" stroke-width="4.5"/>
    <circle cx="342" cy="238" r="6.5" fill="#ffffff"/>

    <!-- Central Spark -->
    <g transform="translate(244, 238)">
      <polygon points="0,-12 3.5,-3.5 12,0 3.5,3.5 0,12 -3.5,3.5 -12,0 -3.5,-3.5" fill="#ffffff" opacity="0.65"/>
      <circle cx="0" cy="0" r="2.5" fill="#22d3ee" opacity="0.75"/>
    </g>
  </g>

  <!-- ================= TYPOGRAPHY & BRANDING LOCKUP ================= -->
  <g transform="translate(320, 0)">

    <!-- Top Badge / Pill -->
    <g transform="translate(0, 75)">
      <rect width="210" height="28" rx="14" fill="url(#tagBgGrad)" stroke="#4f46e5" stroke-opacity="0.4" stroke-width="1.2"/>
      <circle cx="14" cy="14" r="4" fill="#22d3ee"/>
      <text x="28" y="18" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', sans-serif" font-size="12" font-weight="600" fill="#38bdf8" letter-spacing="1.5">GIT-BACKED MEMORY</text>
    </g>

    <!-- Main Project Name -->
    <text x="0" y="172" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', sans-serif" font-size="74" font-weight="800" fill="url(#textGrad)" letter-spacing="2.5">
      Perenna
    </text>

    <!-- Tagline / Value Proposition -->
    <text x="2" y="222" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', sans-serif" font-size="20" font-weight="400" fill="#94a3b8" letter-spacing="0.5">
      A lightweight, Git-backed permanent memory for AI agents
    </text>

    <!-- Feature Highlights / Pills -->
    <g transform="translate(2, 252)">
      <!-- Pill 1: Markdown Git -->
      <rect x="0" y="0" width="138" height="28" rx="6" fill="#1e293b" stroke="#334155" stroke-width="1"/>
      <text x="12" y="18" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="500" fill="#cbd5e1">Markdown + Git</text>

      <!-- Pill 2: Multi-Agent MCP -->
      <rect x="150" y="0" width="168" height="28" rx="6" fill="#1e293b" stroke="#334155" stroke-width="1"/>
      <text x="162" y="18" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="500" fill="#cbd5e1">Shared via MCP</text>

      <!-- Pill 3: Self-Hosted & Free -->
      <rect x="330" y="0" width="124" height="28" rx="6" fill="#1e293b" stroke="#334155" stroke-width="1"/>
      <text x="342" y="18" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="500" fill="#cbd5e1">Self-hosted</text>
    </g>
  </g>

  <!-- Right Decorative Git Graph Accent -->
  <g transform="translate(1040, 100)" opacity="0.25">
    <path d="M 0 0 C 40 40, 60 80, 20 120 C -20 160, 40 180, 80 180" fill="none" stroke="url(#subtextGrad)" stroke-width="3"/>
    <circle cx="0" cy="0" r="6" fill="#38bdf8"/>
    <circle cx="20" cy="120" r="6" fill="#a855f7"/>
    <circle cx="80" cy="180" r="6" fill="#f43f5e"/>
  </g>
</svg>"""

# -------------------------------------------------------------
# 4. Transparent Horizontal Brand Lockup (900 x 200)
# -------------------------------------------------------------
LOGO_BANNER_TRANSPARENT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 200" width="100%" height="100%">
  <defs>
    <linearGradient id="btStemGrad" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="#4f46e5"/>
      <stop offset="45%" stop-color="#7c3aed"/>
      <stop offset="100%" stop-color="#06b6d4"/>
    </linearGradient>

    <linearGradient id="btLoopGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#06b6d4"/>
      <stop offset="28%" stop-color="#3b82f6"/>
      <stop offset="68%" stop-color="#8b5cf6"/>
      <stop offset="100%" stop-color="#f43f5e"/>
    </linearGradient>

    <linearGradient id="btGitTrace" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#6366f1"/>
      <stop offset="35%" stop-color="#22d3ee"/>
      <stop offset="75%" stop-color="#ec4899"/>
      <stop offset="100%" stop-color="#fb7185"/>
    </linearGradient>

    <linearGradient id="btTextGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#f8fafc"/>
      <stop offset="60%" stop-color="#e2e8f0"/>
      <stop offset="100%" stop-color="#38bdf8"/>
    </linearGradient>

    <radialGradient id="btCyanGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="35%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#0284c7" stop-opacity="0"/>
    </radialGradient>

    <radialGradient id="btPinkGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="35%" stop-color="#fb7185"/>
      <stop offset="100%" stop-color="#e11d48" stop-opacity="0"/>
    </radialGradient>

    <filter id="btGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <!-- Logo Mark -->
  <g transform="translate(10, 10) scale(0.36)">
    <path d="M 172 124
             C 274 124, 368 160, 368 238
             C 368 316, 274 352, 172 352
             L 172 294
             C 238 294, 308 270, 308 238
             C 308 206, 238 182, 172 182
             Z"
          fill="url(#btLoopGrad)"/>

    <rect x="136" y="124" width="50" height="268" rx="25" fill="url(#btStemGrad)"/>

    <path d="M 161 340
             L 161 240
             C 161 176, 232 152, 285 174
             C 338 196, 338 274, 285 298
             C 238 318, 188 288, 161 254"
          fill="none"
          stroke="url(#btGitTrace)"
          stroke-width="8"
          stroke-linecap="round"
          stroke-linejoin="round"
          filter="url(#btGlow)"/>

    <circle cx="161" cy="340" r="18" fill="url(#btCyanGlow)" opacity="0.7"/>
    <circle cx="161" cy="340" r="13" fill="#0f172a" stroke="#4f46e5" stroke-width="4"/>
    <circle cx="161" cy="340" r="5" fill="#ffffff"/>

    <circle cx="161" cy="228" r="22" fill="url(#btCyanGlow)" opacity="0.85"/>
    <circle cx="161" cy="228" r="15" fill="#0f172a" stroke="#06b6d4" stroke-width="4"/>
    <circle cx="161" cy="228" r="6" fill="#ffffff"/>

    <circle cx="278" cy="160" r="13" fill="#0f172a" stroke="#a855f7" stroke-width="3.5"/>
    <circle cx="278" cy="160" r="5" fill="#ffffff"/>

    <circle cx="342" cy="238" r="24" fill="url(#btPinkGlow)" opacity="0.9"/>
    <circle cx="342" cy="238" r="16" fill="#0f172a" stroke="#f43f5e" stroke-width="4.5"/>
    <circle cx="342" cy="238" r="6.5" fill="#ffffff"/>

    <g transform="translate(244, 238)">
      <polygon points="0,-12 3.5,-3.5 12,0 3.5,3.5 0,12 -3.5,3.5 -12,0 -3.5,-3.5" fill="#ffffff" opacity="0.65"/>
      <circle cx="0" cy="0" r="2.5" fill="#22d3ee" opacity="0.75"/>
    </g>
  </g>

  <!-- Typography -->
  <g transform="translate(195, 0)">
    <text x="0" y="105" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', sans-serif" font-size="70" font-weight="800" fill="url(#btTextGrad)" letter-spacing="2">
      Perenna
    </text>
    <text x="2" y="148" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', sans-serif" font-size="19" font-weight="400" fill="#94a3b8" letter-spacing="0.4">
      Git-backed permanent memory for AI agents
    </text>
  </g>
</svg>"""

# -------------------------------------------------------------
# 5. Interactive HTML Preview Showcase
# -------------------------------------------------------------
HTML_PREVIEW = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Perenna Logo & Brand Assets Showcase</title>
  <link rel="icon" type="image/svg+xml" href="favicon.svg" />
  <style>
    :root {
      --bg-dark: #090d16;
      --card-dark: #111726;
      --border-dark: rgba(255, 255, 255, 0.08);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent-cyan: #06b6d4;
      --accent-indigo: #6366f1;
      --accent-pink: #f43f5e;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg-dark);
      color: var(--text-main);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', sans-serif;
      line-height: 1.6;
      padding: 40px 24px;
      min-height: 100vh;
    }

    .container {
      max-width: 1200px;
      margin: 0 auto;
    }

    header {
      text-align: center;
      margin-bottom: 48px;
    }

    h1 {
      font-size: 2.75rem;
      font-weight: 800;
      background: linear-gradient(135deg, #fff 0%, #38bdf8 50%, #c084fc 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 12px;
      letter-spacing: -0.5px;
    }

    .subtitle {
      font-size: 1.15rem;
      color: var(--text-muted);
      max-width: 680px;
      margin: 0 auto 20px;
    }

    .theme-toggle {
      display: inline-flex;
      background: #1e293b;
      border-radius: 30px;
      padding: 4px;
      border: 1px solid var(--border-dark);
      margin-top: 10px;
    }

    .theme-toggle button {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 8px 18px;
      border-radius: 20px;
      cursor: pointer;
      font-weight: 600;
      font-size: 0.9rem;
      transition: all 0.2s ease;
    }

    .theme-toggle button.active {
      background: #3b82f6;
      color: #ffffff;
      box-shadow: 0 2px 10px rgba(59, 130, 246, 0.4);
    }

    /* Grid & Cards */
    .section-title {
      font-size: 1.4rem;
      font-weight: 700;
      margin: 40px 0 20px;
      display: flex;
      align-items: center;
      gap: 10px;
      border-bottom: 1px solid var(--border-dark);
      padding-bottom: 10px;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 24px;
    }

    .card {
      background: var(--card-dark);
      border: 1px solid var(--border-dark);
      border-radius: 20px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      align-items: center;
      transition: transform 0.2s, box-shadow 0.2s;
    }

    .card:hover {
      transform: translateY(-4px);
      box-shadow: 0 16px 32px rgba(0, 0, 0, 0.4);
    }

    .banner-card {
      grid-column: 1 / -1;
      padding: 32px;
    }

    .preview-box {
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 30px;
      border-radius: 14px;
      background: rgba(0, 0, 0, 0.25);
      margin-bottom: 20px;
      min-height: 240px;
    }

    .preview-box.light-mode {
      background: #f1f5f9;
    }

    .preview-box img, .preview-box svg {
      max-width: 100%;
      height: auto;
    }

    .icon-preview {
      width: 200px;
      height: 200px;
    }

    .banner-preview {
      width: 100%;
      max-width: 1000px;
    }

    .size-strip {
      display: flex;
      align-items: center;
      gap: 24px;
      margin-top: 10px;
    }

    .card-footer {
      width: 100%;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: auto;
      padding-top: 16px;
      border-top: 1px solid var(--border-dark);
    }

    .card-info h3 {
      font-size: 1.1rem;
      font-weight: 600;
      margin-bottom: 4px;
    }

    .card-info p {
      font-size: 0.85rem;
      color: var(--text-muted);
    }

    .btn {
      background: #1e293b;
      color: #38bdf8;
      border: 1px solid #334155;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      transition: all 0.2s ease;
    }

    .btn:hover {
      background: #38bdf8;
      color: #090d16;
    }

    /* Design Concept / Story Section */
    .story-card {
      background: linear-gradient(135deg, rgba(30, 27, 75, 0.5) 0%, rgba(15, 23, 42, 0.7) 100%);
      border: 1px solid rgba(99, 102, 241, 0.25);
      border-radius: 20px;
      padding: 32px;
      margin-top: 40px;
    }

    .story-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 24px;
      margin-top: 20px;
    }

    .story-item {
      background: rgba(0, 0, 0, 0.3);
      padding: 20px;
      border-radius: 12px;
      border-left: 4px solid var(--accent-cyan);
    }

    .story-item:nth-child(2) { border-left-color: var(--accent-indigo); }
    .story-item:nth-child(3) { border-left-color: var(--accent-pink); }

    .story-item h4 {
      font-size: 1.05rem;
      margin-bottom: 8px;
      color: #f1f5f9;
    }

    .story-item p {
      font-size: 0.9rem;
      color: var(--text-muted);
    }

  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Perenna Logo & Visual Identity</h1>
      <p class="subtitle">Reusable SVG assets for Perenna's Git-backed memory service.</p>
      <div class="theme-toggle">
        <button id="btnDark" class="active" onclick="setTheme('dark')">🌙 Dark Mode</button>
        <button id="btnLight" onclick="setTheme('light')">☀️ Light Mode</button>
      </div>
    </header>

    <!-- SECTION 1: Header Banner -->
    <div class="section-title">✨ Header Banner</div>
    <div class="card banner-card">
      <div class="preview-box" id="bannerBox">
        <img src="logo-banner.svg" alt="Perenna Banner" class="banner-preview" />
      </div>
      <div class="card-footer">
        <div class="card-info">
          <h3>Full Brand Banner (logo-banner.svg)</h3>
          <p>1200 × 360 px · Dark-background project banner</p>
        </div>
        <a href="logo-banner.svg" download class="btn">Download SVG</a>
      </div>
    </div>

    <div class="card banner-card">
      <div class="preview-box">
        <img src="logo-banner-transparent.svg" alt="Perenna transparent brand lockup" class="banner-preview" />
      </div>
      <div class="card-footer">
        <div class="card-info">
          <h3>Transparent Brand Lockup (logo-banner-transparent.svg)</h3>
          <p>900 × 200 px · Transparent horizontal lockup for dark backgrounds</p>
        </div>
        <a href="logo-banner-transparent.svg" download class="btn">Download SVG</a>
      </div>
    </div>

    <!-- SECTION 2: Icons & Badges -->
    <div class="section-title">💎 Icons & Monograms</div>
    <div class="grid">

      <!-- Card 1: App Icon -->
      <div class="card">
        <div class="preview-box" id="box1">
          <img src="logo.svg" alt="Perenna primary icon" class="icon-preview" />
        </div>
        <div class="card-footer">
          <div class="card-info">
            <h3>Primary Icon (logo.svg)</h3>
            <p>512 × 512 px · Dark container with ambient glow</p>
          </div>
          <a href="logo.svg" download class="btn">Download SVG</a>
        </div>
      </div>

      <!-- Card 2: Transparent Icon -->
      <div class="card">
        <div class="preview-box" id="box2">
          <img src="logo-transparent.svg" alt="Perenna Transparent Icon" class="icon-preview" />
        </div>
        <div class="card-footer">
          <div class="card-info">
            <h3>Transparent Icon (logo-transparent.svg)</h3>
            <p>512 × 512 px · Transparent vector mark for flexible placement</p>
          </div>
          <a href="logo-transparent.svg" download class="btn">Download SVG</a>
        </div>
      </div>

      <!-- Card 3: Favicon & Multi-size -->
      <div class="card">
        <div class="preview-box" id="box3">
          <div class="size-strip">
            <img src="favicon.svg" width="64" height="64" alt="64px" title="64px" />
            <img src="favicon.svg" width="48" height="48" alt="48px" title="48px" />
            <img src="favicon.svg" width="32" height="32" alt="32px" title="32px" />
            <img src="favicon.svg" width="16" height="16" alt="16px" title="16px" />
          </div>
        </div>
        <div class="card-footer">
          <div class="card-info">
            <h3>Favicon & Small Sizes (favicon.svg)</h3>
            <p>The primary mark previewed at 16, 32, 48, and 64 px</p>
          </div>
          <a href="favicon.svg" download class="btn">Download SVG</a>
        </div>
      </div>

    </div>

    <!-- SECTION 3: Visual Elements -->
    <div class="story-card">
      <h2>🎨 Visual Elements</h2>
      <p style="color: #94a3b8; margin-top: 6px;">Stable visual cues used across the asset set:</p>

      <div class="story-grid">
        <div class="story-item">
          <h4>1. P Mark</h4>
          <p>The curved mark forms the letter <strong>P</strong> and suggests memory that persists across agent sessions.</p>
        </div>

        <div class="story-item">
          <h4>2. Git History</h4>
          <p>The vertical spine and branching paths reference Perenna's Git-backed Markdown history.</p>
        </div>

        <div class="story-item">
          <h4>3. Shared MCP Access</h4>
          <p>The connected nodes represent MCP clients accessing shared memory, with the central glow referencing semantic retrieval.</p>
        </div>
      </div>
    </div>

  </div>

  <script>
    function setTheme(mode) {
      const boxes = ['bannerBox', 'box1', 'box2', 'box3'];
      const btnDark = document.getElementById('btnDark');
      const btnLight = document.getElementById('btnLight');

      if (mode === 'light') {
        btnDark.classList.remove('active');
        btnLight.classList.add('active');
        boxes.forEach(id => document.getElementById(id).classList.add('light-mode'));
      } else {
        btnLight.classList.remove('active');
        btnDark.classList.add('active');
        boxes.forEach(id => document.getElementById(id).classList.remove('light-mode'));
      }
    }
  </script>
</body>
</html>"""


def main() -> int:
    """Write the complete brand asset set relative to the repository root."""
    repo_root = Path(__file__).resolve().parents[1]
    assets_dir = repo_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "logo.svg": LOGO_DARK_SQUARE,
        "logo-transparent.svg": LOGO_TRANSPARENT,
        "logo-banner.svg": LOGO_BANNER,
        "logo-banner-transparent.svg": LOGO_BANNER_TRANSPARENT,
        "favicon.svg": LOGO_DARK_SQUARE,
        "preview.html": HTML_PREVIEW,
    }

    for filename, content in files.items():
        path = assets_dir / filename
        path.write_text(content + "\n", encoding="utf-8")
        print(f"Generated assets/{filename}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
