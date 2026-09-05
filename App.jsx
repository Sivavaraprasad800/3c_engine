import { useState, useEffect, useRef, useCallback, useMemo, Fragment } from "react";

const API_BASE = "";

// Format person ID as 10-digit zero-padded string
const fmtId = (id) => id != null ? String(id).padStart(10, "0") : "—";

const fetchAPI = async (endpoint, options = {}) => {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, options);
    if (!res.ok) {
      console.warn(`[API] ${endpoint} -> ${res.status}`);
      return null;
    }
    return await res.json();
  } catch (e) {
    console.warn(`[API] ${endpoint} failed:`, e.message);
    return null;
  }
};

const Icon = ({ path, size = 16, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d={path} />
  </svg>
);

const icons = {
  home: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10",
  entry: "M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z M13 2v7h7",
  checkin: "M9 11l3 3L22 4 M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
  humans: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M23 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75",
  unknown: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  dashboard: "M18 20V10 M12 20V4 M6 20v-6",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z M21 21l-4.35-4.35",
  edit: "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7 M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
  trash: "M3 6h18 M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6 M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2",
  image: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 0 2 2z",
  refresh: "M23 4v6h-6 M1 20v-6h6 M3.51 9a9 9 0 0 1 14.85-3.36L23 10 M1 14l4.64 4.36A9 9 0 0 0 20.49 15",
  chevron: "M9 18l6-6-6-6",
  plus: "M12 5v14 M5 12h14",
  enroll: "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0z M12 14a7 7 0 0 0-7 7h14a7 7 0 0 0-7-7z",
  camera: "M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z M12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  upload: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M17 8l-5-5-5 5 M12 3v12",
  x: "M18 6L6 18 M6 6l12 12",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9",
  eye: "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M12 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z",
  compare: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
};

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:       #1a1d21;
    --sidebar:  #22262b;
    --surface:  #2a2f35;
    --surface2: #32383f;
    --border:   #3a4048;
    --border2:  #454d56;
    --text:     #d4d8dd;
    --text2:    #8a9099;
    --text3:    #5a6270;
    --accent:   #4a9eff;
    --green:    #3dba6e;
    --orange:   #e8943a;
    --red:      #e05252;
    --header:   #1e2227;
    --row-alt:  #262b31;
    --sans:     'Inter', sans-serif;
  }
  body { background: var(--bg); color: var(--text); font-family: var(--sans); font-size: 13px; min-height: 100vh; overflow: hidden; }
  .app { display: flex; height: 100vh; overflow: hidden; }

  /* ── SIDEBAR ── */
  .sidebar { width: 200px; background: var(--sidebar); border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; height: 100vh; overflow-y: auto; position: fixed; top: 0; left: 0; z-index: 100; }
  .sidebar-brand { padding: 14px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
  .brand-logo { width: 28px; height: 28px; background: var(--accent); border-radius: 6px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 12px; color: #fff; }
  .brand-name { font-size: 13px; font-weight: 600; color: var(--text); }
  .nav { flex: 1; padding: 8px 0; overflow-y: auto; }
  .nav-section { padding: 10px 14px 4px; font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--text3); font-weight: 600; }
  .nav-item { display: flex; align-items: center; gap: 9px; padding: 7px 14px; cursor: pointer; color: var(--text2); font-size: 12.5px; transition: all .12s; border-left: 2px solid transparent; }
  .nav-item:hover { background: var(--surface); color: var(--text); }
  .nav-item.active { background: rgba(74,158,255,.1); color: var(--accent); border-left-color: var(--accent); }
  .nav-item.sub { padding-left: 36px; font-size: 12px; }
  .nav-item.sub.active { background: rgba(74,158,255,.08); }
  .sidebar-footer { padding: 12px 14px; border-top: 1px solid var(--border); }
  .status-row { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--text2); }
  .status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); }
  .status-dot.off { background: var(--red); }

  /* ── TOPBAR ── */
  .topbar { height: 44px; background: var(--header); border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 16px; gap: 12px; flex-shrink: 0; position: sticky; top: 0; z-index: 50; }
  .topbar-title { font-size: 13px; font-weight: 500; color: var(--text); flex: 1; }
  .topbar-breadcrumb { font-size: 11px; color: var(--text2); display: flex; align-items: center; gap: 4px; }

  /* ── MAIN ── */
  .main { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; margin-left: 200px; height: 100vh; }
  .content { flex: 1; overflow-y: auto; padding: 16px; height: 0; }

  /* ── PAGE HEADER ── */
  .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; flex-wrap: wrap; gap: 10px; }
  .page-title { font-size: 14px; font-weight: 600; color: var(--text); display: flex; align-items: center; gap: 8px; }
  .page-title-icon { color: var(--text2); }

  /* ── TOOLBAR ── */
  .toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
  .toolbar-group { display: flex; align-items: center; gap: 6px; }
  .toolbar-label { font-size: 11px; color: var(--text2); white-space: nowrap; }
  select, input[type="text"], input[type="date"], input[type="number"] {
    background: var(--surface2); border: 1px solid var(--border); border-radius: 4px;
    color: var(--text); font-family: var(--sans); font-size: 12px; padding: 5px 8px;
    outline: none; transition: border .12s;
  }
  select:focus, input:focus { border-color: var(--accent); }
  select option { background: var(--surface2); }

  /* ── BUTTONS ── */
  .btn { display: inline-flex; align-items: center; gap: 5px; padding: 5px 12px; border-radius: 4px; border: 1px solid var(--border); background: var(--surface2); color: var(--text); font-family: var(--sans); font-size: 12px; font-weight: 500; cursor: pointer; transition: all .12s; white-space: nowrap; }
  .btn:hover { background: var(--surface); border-color: var(--border2); }
  .btn-primary { background: var(--accent); border-color: var(--accent); color: #fff; }
  .btn-primary:hover { opacity: .9; }
  .btn-sm { padding: 3px 8px; font-size: 11px; }
  .btn-icon { padding: 4px 6px; }
  .btn:disabled { opacity: .4; cursor: not-allowed; }

  /* ── TABLE ── */
  .table-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
  .table-info { padding: 8px 14px; border-bottom: 1px solid var(--border); font-size: 11px; color: var(--text2); display: flex; align-items: center; justify-content: space-between; }
  table { width: 100%; border-collapse: collapse; }
  thead tr { background: var(--surface2); }
  th { padding: 9px 12px; text-align: left; font-size: 11px; font-weight: 600; color: var(--text2); text-transform: uppercase; letter-spacing: .06em; border-bottom: 1px solid var(--border); white-space: nowrap; }
  td { padding: 8px 12px; border-bottom: 1px solid var(--border); color: var(--text); vertical-align: middle; font-size: 12.5px; }
  tr:last-child td { border-bottom: none; }
  tr:nth-child(even) td { background: var(--row-alt); }
  tr:hover td { background: rgba(74,158,255,.05); }

  /* ── BADGES ── */
  .badge { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 500; }
  .badge-green { background: rgba(61,186,110,.15); color: var(--green); }
  .badge-orange { background: rgba(232,148,58,.15); color: var(--orange); }
  .badge-red { background: rgba(224,82,82,.15); color: var(--red); }
  .badge-blue { background: rgba(74,158,255,.15); color: var(--accent); }
  .badge-grey { background: var(--surface2); color: var(--text2); }

  /* ── AVATAR ── */
  .avatar { width: 34px; height: 34px; border-radius: 50%; background: var(--surface2); border: 1px solid var(--border); overflow: hidden; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .avatar img { width: 100%; height: 100%; object-fit: cover; }
  .avatar-sm { width: 26px; height: 26px; border-radius: 4px; }

  /* ── STATS ROW ── */
  .stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px,1fr)); gap: 10px; margin-bottom: 16px; }
  .stat-box { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 14px 16px; }
  .stat-box-label { font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--text2); margin-bottom: 6px; }
  .stat-box-value { font-size: 26px; font-weight: 600; color: var(--text); line-height: 1; }
  .stat-box-sub { font-size: 11px; color: var(--text2); margin-top: 4px; }

  /* ── MODAL ── */
  .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.6); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 20px; }
  .modal { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; width: 100%; max-width: 480px; max-height: 90vh; overflow-y: auto; }
  .modal-header { padding: 14px 18px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
  .modal-title { font-size: 13px; font-weight: 600; color: var(--text); }
  .modal-body { padding: 18px; }
  .modal-footer { padding: 12px 18px; border-top: 1px solid var(--border); display: flex; gap: 8px; justify-content: flex-end; }
  .form-group { margin-bottom: 12px; }
  .form-label { font-size: 11px; color: var(--text2); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 5px; display: block; }
  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  input[type="text"], input[type="date"], select { width: 100%; }

  /* ── ENROLL DROP ── */
  .drop-zone { border: 2px dashed var(--border); border-radius: 6px; padding: 28px; text-align: center; cursor: pointer; transition: all .15s; }
  .drop-zone:hover { border-color: var(--accent); background: rgba(74,158,255,.04); }
  .drop-zone-text { font-size: 12px; color: var(--text2); margin-top: 8px; }

  /* ── PROGRESS ── */
  .progress-bar { height: 3px; background: var(--surface2); border-radius: 2px; overflow: hidden; margin-top: 6px; }
  .progress-fill { height: 100%; background: var(--accent); border-radius: 2px; transition: width .3s; }

  /* ── SEARCH ── */
  .search-box { position: relative; }
  .search-box input { padding-left: 28px; width: 200px; }
  .search-icon { position: absolute; left: 8px; top: 50%; transform: translateY(-50%); color: var(--text3); pointer-events: none; }

  /* ── EMPTY ── */
  .empty { text-align: center; padding: 40px; color: var(--text2); font-size: 12px; }

  /* ── MOBILE ── */
  .mobile-topbar { display: none; }

  /* ── MOBILE RESPONSIVE ── */
  @media (max-width: 768px) {
    body { overflow: hidden; }

    /* Sidebar — slide-in drawer */
    .sidebar { position: fixed; left: -200px; top: 0; height: 100vh; z-index: 200; transition: left .25s ease; box-shadow: 4px 0 20px rgba(0,0,0,.5); }
    .sidebar.open { left: 0; }
    .sidebar-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.6); z-index: 199; }
    .sidebar-overlay.open { display: block; }

    /* Mobile topbar */
    .mobile-topbar { display: flex !important; align-items: center; gap: 10px; padding: 10px 14px; background: var(--header); border-bottom: 1px solid var(--border); flex-shrink: 0; }

    /* Main layout */
    .main { margin-left: 0; }
    .topbar { display: none; }
    .page-header { display: none; }
    .content { padding: 10px; }

    /* Stats — 2 columns */
    .stats-row { grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 12px; }
    .stat-box { padding: 10px 12px; }
    .stat-box-value { font-size: 22px; }
    .stat-box-label { font-size: 9px; }
    .stat-box-sub { font-size: 10px; }

    /* Tables — horizontal scroll */
    .table-wrap { overflow-x: auto; }
    table { font-size: 11px; min-width: 500px; }
    th, td { padding: 7px 8px; }

    /* Toolbar — wrap */
    .toolbar { flex-wrap: wrap; gap: 6px; }
    .search-box input { width: 130px; }

    /* Forms */
    .form-row { grid-template-columns: 1fr; }

    /* Modal — bottom sheet */
    .modal-overlay { padding: 0; align-items: flex-end; }
    .modal { max-width: 100%; border-radius: 14px 14px 0 0; max-height: 90vh; }

    /* Persons grid */
    .persons-grid { grid-template-columns: repeat(3, 1fr); gap: 8px; }
    .person-photo { width: 40px; height: 40px; }
    .person-name { font-size: 10px; }

    /* Camera config — stack vertically */
    .two-col-config { grid-template-columns: 1fr !important; }

    /* Buttons */
    .btn { padding: 6px 10px; font-size: 11px; }
    .btn-sm { padding: 4px 7px; font-size: 10px; }

    /* Chart */
    .bar-chart { height: 55px; }
  }

  /* Small phones */
  @media (max-width: 400px) {
    .stats-row { grid-template-columns: 1fr 1fr; gap: 6px; }
    .stat-box-value { font-size: 20px; }
    .persons-grid { grid-template-columns: repeat(2, 1fr); }
    .content { padding: 8px; }
  }

  /* Tablet */
  @media (min-width: 769px) and (max-width: 1024px) {
    .sidebar { width: 180px; }
    .main { margin-left: 180px; }
    .stats-row { grid-template-columns: repeat(3, 1fr); }
    .stat-box-value { font-size: 24px; }
  }

  /* ── CAMERA PULSE MONITOR ── */
  .pulse-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
    gap: 16px;
    margin-top: 10px;
  }
  .pulse-card {
    background: #14171a;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  }
  .pulse-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    padding-bottom: 8px;
  }
  .pulse-title {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text);
  }
  .pulse-subtitle {
    font-size: 10.5px;
    color: var(--text2);
    font-family: monospace;
    margin-top: 2px;
  }
  .pulse-readout-wrap {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }
  .pulse-fps-label {
    font-size: 10px;
    color: var(--text3);
    text-transform: uppercase;
    letter-spacing: .08em;
  }
  .pulse-fps-val {
    font-family: 'Inter', monospace;
    font-size: 32px;
    font-weight: 700;
    line-height: 1;
  }
  .pulse-fps-target {
    font-size: 11px;
    color: var(--text3);
    margin-top: 4px;
  }
  .pulse-graph-box {
    background: #0d0f11;
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 4px;
    height: 70px;
    position: relative;
    overflow: hidden;
  }
  .pulse-graph-grid {
    position: absolute;
    inset: 0;
    background-image: 
      linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
    background-size: 10px 10px;
    pointer-events: none;
  }
  .pulse-status-indicator {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
  }
  .status-dot.pulsing {
    background: var(--green);
    box-shadow: 0 0 8px var(--green);
    animation: pulse-glow-indicator 1.5s infinite;
  }
  .status-dot.flatline {
    background: var(--red);
    box-shadow: 0 0 8px var(--red);
  }
  @keyframes pulse-glow-indicator {
    0% { transform: scale(0.9); opacity: 0.6; }
    50% { transform: scale(1.15); opacity: 1; }
    100% { transform: scale(0.9); opacity: 0.6; }
  }
  .pulse-details-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    font-size: 11px;
    color: var(--text2);
    cursor: pointer;
    background: none;
    border: none;
    outline: none;
    padding: 6px;
    transition: color 0.15s;
  }
  .pulse-details-btn:hover {
    color: var(--accent);
  }
  .pulse-details-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px 16px;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.03);
    border-radius: 4px;
    padding: 10px;
    font-size: 11px;
    margin-top: 4px;
  }
  .pulse-detail-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .pulse-detail-lbl {
    color: var(--text3);
    font-size: 9.5px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .pulse-detail-val {
    color: var(--text);
    font-weight: 500;
  }

  /* ── FRS MODEL COMPARISON DASHBOARD STYLES ── */
  .compare-grid-2 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 16px;
    margin-bottom: 16px;
  }
  .compare-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    position: relative;
    box-shadow: 0 4px 12px rgba(0,0,0,0.25);
  }
  .compare-card.our-frs {
    border-top: 3px solid #3b82f6;
  }
  .compare-card.kloudspot {
    border-top: 3px solid #f97316;
  }
  .compare-metric-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    font-size: 12px;
  }
  .compare-metric-row:last-child {
    border-bottom: none;
  }
  .compare-metric-val {
    font-weight: 600;
    font-family: monospace;
    font-size: 13px;
  }
  .pill-matched {
    background: rgba(16, 185, 129, 0.15);
    color: #10b981;
    border: 1px solid rgba(16, 185, 129, 0.3);
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .pill-ks-only {
    background: rgba(249, 115, 22, 0.15);
    color: #f97316;
    border: 1px solid rgba(249, 115, 22, 0.3);
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .pill-our-only {
    background: rgba(59, 130, 246, 0.15);
    color: #3b82f6;
    border: 1px solid rgba(59, 130, 246, 0.3);
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .pill-mismatch {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .meter-track {
    width: 100%;
    height: 6px;
    background: rgba(255,255,255,0.08);
    border-radius: 3px;
    overflow: hidden;
    margin-top: 4px;
  }
  .meter-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s ease;
  }
  .tab-btn {
    padding: 8px 16px;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text2);
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
  }
  .tab-btn.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
    background: rgba(74, 158, 255, 0.05);
  }
  .tab-btn:hover:not(.active) {
    color: var(--text);
  }
`;

// ─── LINE CHART ──────────────────────────────────────────────
function OccupancyChart({ data }) {
  const W = 900, H = 260, PL = 48, PR = 48, PT = 16, PB = 36;
  const cW = W - PL - PR, cH = H - PT - PB;
  const [tooltip, setTooltip] = useState(null);

  if (!data || data.length === 0) {
    return <div style={{ height: H, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text2)", fontSize: 12 }}>No data yet</div>;
  }

  const maxEntry = Math.max(...data.map(d => d.entry), 1);
  const maxOcc = Math.max(...data.map(d => d.occupancy), 1);
  const xStep = cW / 23;

  const toX = h => PL + h * xStep;
  const toYE = v => PT + cH - (v / maxEntry) * cH;
  const toYO = v => PT + cH - (v / maxOcc) * cH;

  // Smooth bezier curve path
  const smoothPath = (points) => {
    if (points.length < 2) return "";
    let d = `M${points[0][0].toFixed(1)},${points[0][1].toFixed(1)}`;
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const curr = points[i];
      const cpx = (prev[0] + curr[0]) / 2;
      d += ` C${cpx.toFixed(1)},${prev[1].toFixed(1)} ${cpx.toFixed(1)},${curr[1].toFixed(1)} ${curr[0].toFixed(1)},${curr[1].toFixed(1)}`;
    }
    return d;
  };

  const entryPts = data.map(d => [toX(d.hour), toYE(d.entry)]);
  const exitPts = data.map(d => [toX(d.hour), toYE(d.exit)]);
  const occPts = data.map(d => [toX(d.hour), toYO(d.occupancy)]);

  const entryPath = smoothPath(entryPts);
  const exitPath = smoothPath(exitPts);
  const occPath = smoothPath(occPts);

  // Area fill under occupancy
  const occArea = occPath + ` L${toX(23)},${PT + cH} L${toX(0)},${PT + cH} Z`;

  // Y axis ticks (5 levels)
  const yTicks = [0, 0.25, 0.5, 0.75, 1.0];

  // X axis labels — every 2 hours
  const xLabels = [
    "12am", "2am", "4am", "6am", "8am", "10am",
    "12pm", "2pm", "4pm", "6pm", "8pm", "10pm"
  ];

  return (
    <div style={{ position: "relative", overflowX: "auto" }}>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: "block", minWidth: 480 }}>
        {/* Grid lines */}
        {yTicks.map((t, i) => {
          const y = PT + cH * (1 - t);
          return (
            <g key={i}>
              <line x1={PL} y1={y} x2={W - PR} y2={y}
                stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
              {/* Left Y axis — Entry */}
              <text x={PL - 6} y={y + 4} textAnchor="end" fontSize="9" fill="rgba(255,255,255,0.35)">
                {Math.round(maxEntry * t)}
              </text>
              {/* Right Y axis — Occupancy */}
              <text x={W - PR + 6} y={y + 4} textAnchor="start" fontSize="9" fill="rgba(255,255,255,0.35)">
                {Math.round(maxOcc * t)}
              </text>
            </g>
          );
        })}

        {/* Vertical grid lines */}
        {xLabels.map((_, i) => (
          <line key={i} x1={toX(i * 2)} y1={PT} x2={toX(i * 2)} y2={PT + cH}
            stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
        ))}

        {/* Axis labels */}
        <text x={12} y={PT + cH / 2} textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)"
          transform={`rotate(-90,12,${PT + cH / 2})`}>Entry</text>
        <text x={W - 10} y={PT + cH / 2} textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)"
          transform={`rotate(90,${W - 10},${PT + cH / 2})`}>Occupancy</text>

        {/* X axis time labels */}
        {xLabels.map((lbl, i) => (
          <text key={i} x={toX(i * 2)} y={PT + cH + 14} textAnchor="middle" fontSize="8.5" fill="rgba(255,255,255,0.35)">
            {lbl}
          </text>
        ))}
        <text x={W / 2} y={H - 2} textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.3)">Time</text>

        {/* Occupancy area fill */}
        <path d={occArea} fill="rgba(74,158,255,0.06)" />

        {/* Smooth lines */}
        <path d={occPath} fill="none" stroke="#4a9eff" strokeWidth="1.5" strokeLinejoin="round" />
        <path d={entryPath} fill="none" stroke="#a8d060" strokeWidth="1.5" strokeLinejoin="round" />
        <path d={exitPath} fill="none" stroke="#e05252" strokeWidth="1.5" strokeLinejoin="round" strokeDasharray="4,3" />

        {/* Small dots */}
        {data.map((d, i) => (
          <g key={i}>
            <circle cx={toX(d.hour)} cy={toYE(d.entry)} r="2.5" fill="#a8d060" />
            <circle cx={toX(d.hour)} cy={toYE(d.exit)} r="2.5" fill="#e05252" />
            <circle cx={toX(d.hour)} cy={toYO(d.occupancy)} r="2.5" fill="#4a9eff" />
            {/* Hover area */}
            <rect x={toX(d.hour) - xStep / 2} y={PT} width={xStep} height={cH}
              fill="transparent"
              onMouseEnter={() => setTooltip({ d, x: toX(d.hour), y: toYE(d.entry) })}
              onMouseLeave={() => setTooltip(null)} />
          </g>
        ))}

        {/* Tooltip */}
        {tooltip && (() => {
          const tx = Math.min(tooltip.x + 10, W - 130);
          const ty = PT + 10;
          return (
            <g>
              <line x1={tooltip.x} y1={PT} x2={tooltip.x} y2={PT + cH}
                stroke="rgba(255,255,255,0.2)" strokeWidth="1" strokeDasharray="3,3" />
              <rect x={tx} y={ty} width={118} height={68} rx="4"
                fill="#1e2227" stroke="rgba(255,255,255,0.12)" />
              <text x={tx + 8} y={ty + 14} fontSize="9.5" fill="rgba(255,255,255,0.6)">
                {String(tooltip.d.hour).padStart(2, "0")}:00
              </text>
              <circle cx={tx + 10} cy={ty + 28} r="3.5" fill="#a8d060" />
              <text x={tx + 18} y={ty + 32} fontSize="9.5" fill="#e8edf2">Entry: {tooltip.d.entry}</text>
              <circle cx={tx + 10} cy={ty + 44} r="3.5" fill="#e05252" />
              <text x={tx + 18} y={ty + 48} fontSize="9.5" fill="#e8edf2">Exit: {tooltip.d.exit}</text>
              <circle cx={tx + 10} cy={ty + 60} r="3.5" fill="#4a9eff" />
              <text x={tx + 18} y={ty + 64} fontSize="9.5" fill="#e8edf2">Occupancy: {tooltip.d.occupancy}</text>
            </g>
          );
        })()}

        {/* Axes */}
        <line x1={PL} y1={PT} x2={PL} y2={PT + cH} stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
        <line x1={PL} y1={PT + cH} x2={W - PR} y2={PT + cH} stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
        <line x1={W - PR} y1={PT} x2={W - PR} y2={PT + cH} stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
      </svg>

      {/* Legend */}
      <div style={{ display: "flex", gap: 20, justifyContent: "center", marginTop: 6, fontSize: 11, color: "rgba(255,255,255,0.5)" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#a8d060" strokeWidth="1.5" /><circle cx="10" cy="4" r="2.5" fill="#a8d060" /></svg>
          Entry
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#e05252" strokeWidth="1.5" strokeDasharray="4,3" /><circle cx="10" cy="4" r="2.5" fill="#e05252" /></svg>
          Exit
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#4a9eff" strokeWidth="1.5" /><circle cx="10" cy="4" r="2.5" fill="#4a9eff" /></svg>
          Occupancy
        </span>
      </div>
    </div>
  );
}

// ─── DASHBOARD PAGE ───────────────────────────────────────────
// ─── DASHBOARD PAGE ───────────────────────────────────────────
function DashboardPage({ onNavigate }) {
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().slice(0, 10));
  const [stats, setStats] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [headcount, setHeadcount] = useState([]);

  const loadAll = useCallback(() => {
    const d = selectedDate;
    fetchAPI(`/api/v1/dashboard?date=${d}`).then(r => {
      if (r) {
        setStats(r);
        setChartData(r.occupancy || []);
        setHeadcount(r.headcount || []);
      }
    });
  }, [selectedDate]);

  useEffect(() => {
    loadAll();
    const t = setInterval(loadAll, 30000);
    return () => clearInterval(t);
  }, [loadAll]);

  return (
    <div>
      {/* Date filter bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
        <span style={{ fontSize: 11, color: "var(--text2)", textTransform: "uppercase", letterSpacing: ".06em" }}>Date Filter</span>
        <input type="date" value={selectedDate}
          onChange={e => setSelectedDate(e.target.value)}
          style={{ width: 150 }} />
        <button className="btn btn-sm"
          onClick={() => setSelectedDate(new Date().toISOString().slice(0, 10))}>
          Today
        </button>
        <button className="btn btn-sm"
          onClick={() => {
            const d = new Date(); d.setDate(d.getDate() - 1);
            setSelectedDate(d.toISOString().slice(0, 10));
          }}>
          Yesterday
        </button>
        <span style={{ fontSize: 11, color: "var(--text2)", marginLeft: "auto" }}>
          Showing data for <b style={{ color: "var(--text)" }}>{selectedDate}</b>
        </span>
        <button className="btn btn-sm" onClick={loadAll}><Icon path={icons.refresh} size={12} /> Refresh</button>
        <button className="btn btn-sm btn-primary" onClick={() => onNavigate?.("pulse")} style={{ background: "var(--accent)", color: "#fff", border: "none", marginLeft: 4 }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4, display: "inline-block", verticalAlign: "middle" }}>
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
          </svg>
          ⚡ Camera Pulse
        </button>
      </div>

      {/* Stat boxes — Interactive Working Cards */}
      <div className="stats-row">
        <div className="stat-box" onClick={() => onNavigate?.("entry")} style={{ cursor: "pointer", transition: "transform 0.15s, border-color 0.15s" }} title="Click to view Entry/Exit Log">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div className="stat-box-label">Currently Inside</div>
            <span className="badge badge-green" style={{ fontSize: 9 }}>Inside Now</span>
          </div>
          <div className="stat-box-value" style={{ color: "var(--green)" }}>{stats?.currently_in ?? 0}</div>
          <div className="stat-box-sub">Active check-ins →</div>
        </div>

        <div className="stat-box" onClick={() => onNavigate?.("entry")} style={{ cursor: "pointer" }} title="Click to view Entry/Exit Log">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div className="stat-box-label">Checked Out Today</div>
            <span className="badge badge-blue" style={{ fontSize: 9 }}>Completed</span>
          </div>
          <div className="stat-box-value" style={{ color: "var(--accent)" }}>{stats?.checked_out_today ?? 0}</div>
          <div className="stat-box-sub">Checked out today →</div>
        </div>

        <div className="stat-box" onClick={() => onNavigate?.("entry")} style={{ cursor: "pointer" }} title="Click to view Entry/Exit Log">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div className="stat-box-label">Total Today</div>
            <span className="badge badge-grey" style={{ fontSize: 9 }}>Attendance Log</span>
          </div>
          <div className="stat-box-value">{stats?.total_today ?? 0}</div>
          <div className="stat-box-sub">Unique attendance records →</div>
        </div>

        <div className="stat-box" onClick={() => onNavigate?.("entry")} style={{ cursor: "pointer" }} title="Click to view All Detections">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div className="stat-box-label">Total Detections</div>
            <span className="badge badge-grey" style={{ fontSize: 9 }}>Recognitions</span>
          </div>
          <div className="stat-box-value">{stats?.total_detections ?? 0}</div>
          <div className="stat-box-sub">All face scans on {selectedDate} →</div>
        </div>

        <div className="stat-box" onClick={() => onNavigate?.("humans")} style={{ cursor: "pointer" }} title="Click to view Enrolled Humans">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div className="stat-box-label">Enrolled Staff</div>
            <span className="badge badge-blue" style={{ fontSize: 9 }}>Staff DB</span>
          </div>
          <div className="stat-box-value" style={{ color: "var(--accent)" }}>{stats?.enrolled ?? 0}</div>
          <div className="stat-box-sub">Registered employees →</div>
        </div>

        <div className="stat-box" onClick={() => onNavigate?.("unregistered")} style={{ cursor: "pointer" }} title="Click to view Unregistered Faces">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div className="stat-box-label">Unregistered</div>
            <span className="badge badge-orange" style={{ fontSize: 9 }}>Needs Review</span>
          </div>
          <div className="stat-box-value" style={{ color: "var(--orange)" }}>{stats?.unknown ?? 0}</div>
          <div className="stat-box-sub">Unmatched faces →</div>
        </div>
      </div>

      {/* Occupancy Chart */}
      <div className="table-wrap" style={{ padding: 0 }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 8 }}>
          <Icon path={icons.dashboard} size={14} color="var(--text2)" />
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>Camera Occupancy Trends Over Time</span>
          <span style={{ fontSize: 11, color: "var(--text2)", marginLeft: "auto" }}>{selectedDate}</span>
        </div>
        <div style={{ padding: "16px", overflowX: "auto" }}>
          <OccupancyChart data={chartData} />
        </div>
      </div>

      {/* Head Count per Zone */}
      {headcount.length > 0 && (
        <div className="table-wrap" style={{ marginTop: 16 }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", fontSize: 13, fontWeight: 600, color: "var(--text)", display: "flex", alignItems: "center", gap: 8 }}>
            <Icon path={icons.humans} size={14} color="var(--text2)" />
            Zone Head Count — {selectedDate}
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ minWidth: 480 }}>
              <thead>
                <tr>
                  <th>Camera</th>
                  <th>Type</th>
                  <th>Zone</th>
                  <th>Total Passed</th>
                  <th>Known Staff</th>
                  <th>Unrecognized</th>
                </tr>
              </thead>
              <tbody>
                {headcount.map((c, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500, whiteSpace: "nowrap" }}>
                      {c.camera_name}
                      <div style={{ fontSize: 10, color: "var(--text2)", fontFamily: "monospace" }}>{c.camera_id}</div>
                    </td>
                    <td>
                      <span className={`badge ${c.camera_type === "checkout" ? "badge-red" : c.camera_type === "checkin" ? "badge-green" : "badge-blue"}`}>
                        {c.camera_type === "checkout" ? "Exit" : c.camera_type === "checkin" ? "Entry" : "Both"}
                      </span>
                    </td>
                    <td style={{textAlign:"center"}}>{c.total_passed}</td>
                    <td style={{textAlign:"center",color:"var(--green)"}}>{c.known_count}</td>
                    <td style={{textAlign:"center",color:"var(--orange)"}}>{c.unknown_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// --- ENTRY EXIT PAGE (ALL DETECTED PERSONS) ---
function EntryExitPage() {
  const [events, setEvents] = useState([]);
  const [cameras, setCameras] = useState({});
  const [cameraList, setCameraList] = useState([]);
  const [selectedCam, setSelectedCam] = useState("all");
  const [search, setSearch] = useState("");
  const [hours, setHours] = useState(24);
  const [filterTab, setFilterTab] = useState("all");
  const [selected, setSelected] = useState(new Set());
  const [deleting, setDeleting] = useState(false);
  const [captureKnownOnly, setCaptureKnownOnly] = useState(false);
  const [togglingSetting, setTogglingSetting] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const load = useCallback(() => {
    const params = new URLSearchParams();
    params.set("limit", "10");
    params.set("page", String(page));
    params.set("hours", String(hours));
    if (selectedCam !== "all") params.set("camera_id", selectedCam);
    if (search) params.set("search", search);
    if (filterTab === "known_suspected") params.set("matched", "true");
    else if (filterTab === "employee") params.set("person_type", "employee");
    else if (filterTab === "visitor") params.set("person_type", "visitor");
    else if (filterTab === "blacklist") params.set("person_type", "blacklisted");
    else if (filterTab === "suspected") params.set("suspected", "true");
    else if (filterTab === "unregistered") params.set("matched", "false");

    fetchAPI(`/api/v1/events?${params.toString()}`)
      .then(d => {
        if (d) {
          setEvents(d.events || []);
          setTotalCount(d.total_count || 0);
          setTotalPages(d.total_pages || 1);
          setSelected(new Set());
        }
      });
  }, [page, hours, selectedCam, search, filterTab]);

  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);

  useEffect(() => {
    fetchAPI("/api/v1/cameras").then(d => {
      if (d?.cameras) {
        const map = {};
        d.cameras.forEach(c => { map[c.id] = c.camera_type; });
        setCameras(map);
        setCameraList(d.cameras || []);
      }
    });
    fetchAPI("/api/v1/system/settings").then(d => {
      if (d?.settings) {
        const val = String(d.settings.capture_known_only || "false").toLowerCase();
        setCaptureKnownOnly(val === "true" || val === "1" || val === "yes");
      }
    });
  }, []);

  const handleToggleCaptureKnownOnly = async () => {
    const nextVal = !captureKnownOnly;
    setTogglingSetting(true);
    try {
      const res = await fetchAPI("/api/v1/system/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ capture_known_only: nextVal ? "true" : "false" })
      });
      if (res && res.success) {
        setCaptureKnownOnly(nextVal);
      } else {
        alert("Failed to update system setting.");
      }
    } catch (err) {
      console.error(err);
      alert("Error saving setting.");
    } finally {
      setTogglingSetting(false);
    }
  };

  const toggleSelect = (id) => setSelected(prev => {
    const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s;
  });
  const toggleAll = () => setSelected(prev =>
    prev.size === events.length ? new Set() : new Set(events.map(e => e.id))
  );

  const deleteSelected = async () => {
    if (!selected.size) return;
    if (!window.confirm(`Delete ${selected.size} event(s)? This cannot be undone.`)) return;
    setDeleting(true);
    for (const id of selected) {
      await fetchAPI(`/api/v1/events/${id}`, { method: "DELETE" });
    }
    setDeleting(false);
    load();
  };

  const deleteSingle = async (id) => {
    await fetchAPI(`/api/v1/events/${id}`, { method: "DELETE" });
    load();
  };

  const getDirection = (event) => {
    const type = cameras[event.camera_id];
    if (type === "checkout") return { label: "Exit", cls: "badge-red" };
    if (type === "checkin") return { label: "Entry", cls: "badge-green" };
    if (type === "headcount") return { label: "Headcount", cls: "badge-purple" };
    return { label: "Detection", cls: "badge-blue" };
  };

  const camStats = useMemo(() => {
    const stats = {};
    events.forEach(e => {
      const cid = e.camera_id || "unknown";
      if (!stats[cid]) {
        stats[cid] = { total: 0, entries: 0, exits: 0, known: 0, suspected: 0, unknown: 0 };
      }
      stats[cid].total += 1;
      const type = cameras[cid];
      if (type === "checkin") stats[cid].entries += 1;
      else if (type === "checkout") stats[cid].exits += 1;
      if (e.matched) stats[cid].known += 1;
      else if (e.suspected) stats[cid].suspected += 1;
      else stats[cid].unknown += 1;
    });
    return stats;
  }, [events, cameras]);

  return (
    <div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center", justifyContent: "space-between", marginBottom: 14, background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8, padding: "12px 16px" }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14, display: "flex", alignItems: "center", gap: 8 }}>
            <span>👤 Person Capture & Entry/Exit Tracking</span>
            {captureKnownOnly ? (
              <span className="badge badge-green" style={{ fontSize: 10, padding: "2px 8px" }}>
                ✓ CAPTURING KNOWN & SUSPECTED ONLY
              </span>
            ) : (
              <span className="badge badge-blue" style={{ fontSize: 10, padding: "2px 8px" }}>
                ALL DETECTIONS ACTIVE
              </span>
            )}
          </div>
          <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 4 }}>
            {captureKnownOnly
              ? "Ignoring unknown faces in database — capturing and storing ONLY registered persons & suspected matches."
              : "Capturing all detected faces (both known and unknown)."}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, background: "var(--bg-dark)", padding: "6px 12px", borderRadius: 6, border: "1px solid var(--border)" }}>
          <span style={{ fontSize: 12, fontWeight: 500, color: captureKnownOnly ? "var(--green)" : "var(--text2)" }}>
            Capture Known & Suspected Only:
          </span>
          <button
            onClick={handleToggleCaptureKnownOnly}
            disabled={togglingSetting}
            className={`btn btn-sm ${captureKnownOnly ? "btn-primary" : ""}`}
            style={{
              minWidth: 70,
              fontWeight: 600,
              fontSize: 11,
              background: captureKnownOnly ? "var(--green)" : "rgba(255,255,255,0.06)",
              borderColor: captureKnownOnly ? "var(--green)" : "var(--border)",
              color: captureKnownOnly ? "#000" : "var(--text)"
            }}
          >
            {togglingSetting ? "..." : captureKnownOnly ? "ON" : "OFF"}
          </button>
        </div>
      </div>

      {cameraList.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 14 }}>
          <div
            onClick={() => { setSelectedCam("all"); setPage(1); }}
            style={{
              cursor: "pointer",
              padding: "6px 12px",
              borderRadius: 6,
              fontSize: 12,
              background: selectedCam === "all" ? "var(--accent)" : "var(--bg-card)",
              color: selectedCam === "all" ? "#fff" : "var(--text)",
              border: "1px solid " + (selectedCam === "all" ? "var(--accent)" : "var(--border)"),
              display: "flex",
              alignItems: "center",
              gap: 6
            }}
          >
            <span style={{ fontWeight: 600 }}>All Cameras</span>
            <span className="badge badge-grey" style={{ fontSize: 10 }}>{totalCount}</span>
          </div>

          {cameraList.map(c => {
            const stat = camStats[c.id] || { total: 0, entries: 0, exits: 0, known: 0, suspected: 0, unknown: 0 };
            const isSel = selectedCam === c.id;
            const dirLabel = c.camera_type === "checkin" ? "Entry" : c.camera_type === "checkout" ? "Exit" : c.camera_type;
            return (
              <div
                key={c.id}
                onClick={() => { setSelectedCam(c.id); setPage(1); }}
                style={{
                  cursor: "pointer",
                  padding: "6px 12px",
                  borderRadius: 6,
                  fontSize: 12,
                  background: isSel ? "var(--accent)" : "var(--bg-card)",
                  color: isSel ? "#fff" : "var(--text)",
                  border: "1px solid " + (isSel ? "var(--accent)" : "var(--border)"),
                  display: "flex",
                  alignItems: "center",
                  gap: 6
                }}
              >
                <span>📹 {c.name || c.id} <small style={{ opacity: 0.7 }}>({dirLabel})</small></span>
                <span className="badge badge-grey" style={{ fontSize: 10 }}>{stat.total}</span>
              </div>
            );
          })}
        </div>
      )}

      <div className="toolbar" style={{ flexWrap: "wrap", gap: 10 }}>
        <div className="toolbar-group">
          {[
            { id: "all", label: "All Events" },
            { id: "known_suspected", label: "Known & Suspected" },
            { id: "entry", label: "Entry" },
            { id: "exit", label: "Exit" },
            { id: "employee", label: "Employees" },
            { id: "visitor", label: "Visitors" },
            { id: "blacklist", label: "Blacklist" },
            { id: "suspected", label: "Suspected" },
            { id: "unregistered", label: "Unregistered" },
          ].map(tab => (
            <button
              key={tab.id}
              className={`btn btn-sm ${filterTab === tab.id ? "btn-primary" : ""}`}
              onClick={() => { setFilterTab(tab.id); setPage(1); }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <select
          value={selectedCam}
          onChange={e => { setSelectedCam(e.target.value); setPage(1); }}
          style={{ padding: "4px 8px", borderRadius: 4, background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text)", fontSize: 12 }}
        >
          <option value="all">All Cameras ({cameraList.length})</option>
          {cameraList.map(c => (
            <option key={c.id} value={c.id}>
              {c.name || c.id} ({c.camera_type === "checkin" ? "Entry" : c.camera_type === "checkout" ? "Exit" : c.camera_type})
            </option>
          ))}
        </select>

        <div className="search-box">
          <span className="search-icon"><Icon path={icons.search} size={13} /></span>
          <input
            type="text"
            placeholder="Search person or camera..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
          />
        </div>

        <div className="toolbar-group">
          {[
            { label: "1h", val: 1 },
            { label: "6h", val: 6 },
            { label: "24h", val: 24 },
            { label: "7d", val: 168 },
            { label: "All", val: 8760 },
          ].map(r => (
            <button
              key={r.val}
              className={`btn btn-sm ${hours === r.val ? "btn-primary" : ""}`}
              onClick={() => { setHours(r.val); setPage(1); }}
            >
              {r.label}
            </button>
          ))}
        </div>

        {selected.size > 0 && (
          <button className="btn btn-sm btn-danger" onClick={deleteSelected} disabled={deleting}>
            <Icon path={icons.trash} size={12} />
            {deleting ? "Deleting..." : `Delete (${selected.size})`}
          </button>
        )}

        <button className="btn btn-sm" onClick={load}>
          <Icon path={icons.refresh} size={12} /> Refresh
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th style={{ width: 36 }}>
                <input type="checkbox" checked={events.length > 0 && selected.size === events.length} onChange={toggleAll} />
              </th>
              <th>Snapshot</th>
              <th>Person ID</th>
              <th>Name</th>
              <th>Category</th>
              <th>Direction</th>
              <th>Time</th>
              <th>Confidence</th>
              <th>Camera Location</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {events.map((e, i) => {
              const dir = getDirection(e);
              const isBlack = e.person_type === "blacklisted";
              const isVis = e.person_type === "visitor";
              const isEmp = e.matched && e.person_type === "employee";
              const isSuspected = e.suspected === true && !e.matched;

              return (
                <tr key={i} style={{ background: isBlack ? "rgba(224,82,82,0.08)" : selected.has(e.id) ? "rgba(74,158,255,0.07)" : "" }}>
                  <td>
                    <input type="checkbox" checked={selected.has(e.id)} onChange={() => toggleSelect(e.id)} />
                  </td>
                  <td>
                    <div className="avatar" style={{ width: 38, height: 38, borderRadius: "50%", border: isBlack ? "2px solid var(--red)" : "1px solid var(--border)" }}>
                      {e.id
                        ? <img src={`/api/v1/events/${e.id}/snapshot`} alt="" loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover" }} onError={err => { err.target.style.display = 'none'; }} />
                        : <Icon path={icons.enroll} size={16} color="var(--text3)" />}
                    </div>
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 11, color: "var(--text2)" }}>
                    {e.person_id ? `${fmtId(e.person_id)}` : "Unregistered"}
                  </td>
                  <td style={{ fontWeight: 600, color: isBlack ? "var(--red)" : isSuspected ? "var(--orange)" : "var(--text)" }}>
                    {isSuspected ? `~${e.person_name}` : (e.person_name || "Unknown")}
                  </td>
                  <td>
                    {isBlack ? (
                      <span className="badge badge-red">⚠ Blacklisted</span>
                    ) : isVis ? (
                      <span className="badge badge-orange">Visitor</span>
                    ) : isEmp ? (
                      <span className="badge badge-green">Employee</span>
                    ) : isSuspected ? (
                      <span className="badge badge-orange" title={`Suspected match: ${((e.confidence ?? 0) * 100).toFixed(0)}%`}>⚠ Suspected</span>
                    ) : (
                      <span className="badge badge-grey">Unregistered</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${dir.cls}`}>{dir.label}</span>
                  </td>
                  <td style={{ fontSize: 11, color: "var(--text2)", whiteSpace: "nowrap" }}>
                    {new Date(e.timestamp).toLocaleString("en-IN", {
                      day: "2-digit", month: "2-digit", year: "numeric",
                      hour: "2-digit", minute: "2-digit", second: "2-digit"
                    })}
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 11, color: e.confidence >= 0.7 ? "var(--green)" : "var(--text2)" }}>
                    {e.confidence ? `${(e.confidence * 100).toFixed(0)}%` : "—"}
                  </td>
                  <td style={{ fontSize: 11 }}>
                    <span className="badge badge-grey">{e.camera_id}</span>
                  </td>
                  <td>
                    <button className="btn btn-sm btn-icon" title="Delete event"
                      style={{ color: "var(--red)" }} onClick={() => deleteSingle(e.id)}>
                      <Icon path={icons.trash} size={12} />
                    </button>
                  </td>
                </tr>
              );
            })}
            {events.length === 0 && <tr><td colSpan={10}><div className="empty">No detection events found for selected filters</div></td></tr>}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 14, padding: "8px 4px" }}>
        <div style={{ fontSize: 12, color: "var(--text2)" }}>
          Showing page <strong>{page}</strong> of <strong>{totalPages}</strong> ({totalCount} total events)
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button className="btn btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>
            ← Previous
          </button>
          <span style={{ fontSize: 12, fontWeight: 600, padding: "0 6px" }}>
            {page} / {totalPages}
          </span>
          <button className="btn btn-sm" disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))}>
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── CHECKIN/CHECKOUT PAGE ────────────────────────────────────
function CheckinPage() {
  const [attendance, setAttendance] = useState([]);
  const [currentlyIn, setCurrentlyIn] = useState([]);
  const [cameras, setCameras] = useState({});
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    const dateParam = date ? `&date=${date}` : "";
    const [a, c] = await Promise.all([
      fetchAPI(`/api/v1/attendance?limit=500${dateParam}`),
      fetchAPI("/api/v1/attendance/currently-in")
    ]);
    if (a) setAttendance(a.attendance || []);
    if (c) setCurrentlyIn(c.persons || []);
  }, [date]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    fetchAPI("/api/v1/cameras").then(d => {
      if (d?.cameras) {
        const map = {};
        d.cameras.forEach(c => { map[c.id] = c.camera_type; });
        setCameras(map);
      }
    });
  }, []);

  const checkout = async (person_id) => {
    setLoading(true);
    await fetchAPI("/api/v1/attendance/checkout", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ person_id })
    });
    await load();
    setLoading(false);
  };

  const toggleSelectAtt = (id) => setSelected(prev => {
    const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s;
  });
  const toggleAllAtt = () => setSelected(prev =>
    prev.size === filtered.length ? new Set() : new Set(filtered.map(a => a.id))
  );

  const deleteSingleAtt = async (id) => {
    await fetchAPI(`/api/v1/attendance/${id}`, { method: "DELETE" });
    setAttendance(prev => prev.filter(a => a.id !== id));
    setCurrentlyIn(prev => prev.filter(a => a.id !== id));
  };

  const deleteSelectedAtt = async () => {
    if (!selected.size) return;
    if (!window.confirm(`Delete ${selected.size} attendance record(s)?`)) return;
    setDeleting(true);
    for (const id of selected) {
      await fetchAPI(`/api/v1/attendance/${id}`, { method: "DELETE" });
    }
    setDeleting(false);
    load();
  };

  const clearAll = async () => {
    const d = date || "all dates";
    if (!window.confirm(`Clear ALL attendance records for ${d}? This cannot be undone.`)) return;
    setDeleting(true);
    await fetchAPI(`/api/v1/attendance/clear${date ? `?date=${date}` : ""}`, { method: "DELETE" });
    setDeleting(false);
    load();
  };

  const filtered = attendance.filter(a =>
    !search || (a.person_name || "").toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      {/* Currently Inside */}
      {currentlyIn.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: "var(--text2)", marginBottom: 8, textTransform: "uppercase", letterSpacing: ".06em", display: "flex", alignItems: "center", gap: 6 }}>
            <div className="status-dot" />
            Currently Inside — {currentlyIn.length} present
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Profile</th><th>Name</th><th>Camera</th><th>Check-in Time</th><th>Duration</th><th>Action</th></tr></thead>
              <tbody>
                {currentlyIn.map((a, i) => {
                  const secs = Math.floor((Date.now() - new Date(a.checkin_time).getTime()) / 1000);
                  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60);
                  const dur = h > 0 ? `${h}h ${m}m` : `${m}m`;
                  return (
                    <tr key={i}>
                      <td>
                        <div className="avatar">
                          {a.id
                            ? <img src={`/api/v1/attendance/${a.id}/snapshot`} alt="" loading="lazy" onError={e => e.target.style.display = 'none'} />
                            : <Icon path={icons.enroll} size={14} color="var(--text3)" />}
                        </div>
                      </td>
                      <td style={{ fontWeight: 500 }}>{a.person_name}</td>
                      <td><span className="badge badge-grey">{a.camera_id}</span></td>
                      <td style={{ fontSize: 11, color: "var(--text2)" }}>{new Date(a.checkin_time).toLocaleTimeString()}</td>
                      <td style={{ color: "var(--green)", fontSize: 12, fontWeight: 600 }}>{dur}</td>
                      <td>
                        <button className="btn btn-sm" disabled={loading} onClick={() => checkout(a.person_id)}
                          style={{ color: "var(--orange)", borderColor: "rgba(232,148,58,.3)" }}>
                          <Icon path={icons.logout} size={11} /> Manual Checkout
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Attendance Log */}
      <div className="toolbar">
        <div className="toolbar-group">
          <span className="toolbar-label">Date Filter</span>
          <input type="date" value={date} onChange={e => setDate(e.target.value)} style={{ width: 150 }} />
          <button className="btn btn-sm" onClick={() => setDate(new Date().toISOString().slice(0, 10))}>Today</button>
          <button className="btn btn-sm" onClick={() => setDate("")}>All Dates</button>
        </div>
        <div className="search-box">
          <span className="search-icon"><Icon path={icons.search} size={13} /></span>
          <input type="text" placeholder="Search name..." value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <button className="btn btn-sm" onClick={load}><Icon path={icons.refresh} size={12} /> Refresh</button>
        {selected.size > 0 && (
          <button className="btn btn-sm" style={{ background: "var(--red)", color: "#fff", border: "none" }}
            disabled={deleting} onClick={deleteSelectedAtt}>
            {deleting ? "Deleting..." : `🗑 Delete ${selected.size}`}
          </button>
        )}
        <button className="btn btn-sm" style={{ color: "var(--red)", borderColor: "rgba(224,82,82,.3)" }}
          disabled={deleting} onClick={clearAll}>
          🗑 Clear {date ? date : "All"}
        </button>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text2)" }}>Total: {filtered.length}</span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th style={{ width: 32 }}>
                <input type="checkbox"
                  checked={filtered.length > 0 && selected.size === filtered.length}
                  onChange={toggleAllAtt} />
              </th>
              <th>Profile</th>
              <th>Human ID</th>
              <th>Name</th>
              <th>Identity</th>
              <th>Status</th>
              <th>Check-in / Out Time</th>
              <th>Duration</th>
              <th>Location</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 200).map((a, i) => {
              const identity = `${(a.person_name || "").toLowerCase().replace(/ /g, ".")}@station-s.org`;
              const isCheckedIn = a.status === "checked_in";
              return (
                <tr key={i} style={{ background: selected.has(a.id) ? "rgba(74,158,255,0.07)" : "" }}>
                  <td>
                    <input type="checkbox" checked={selected.has(a.id)} onChange={() => toggleSelectAtt(a.id)} />
                  </td>
                  <td>
                    <div style={{ position: "relative", width: 38, height: 38, flexShrink: 0 }}>
                      <div style={{ width: 38, height: 38, borderRadius: "50%", background: "var(--surface2)", border: "1px solid var(--border)", overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center" }}>
                        {a.id
                          ? <img src={`/api/v1/attendance/${a.id}/snapshot`} alt="" loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover" }} onError={e => e.target.style.display = 'none'} />
                          : <Icon path={icons.enroll} size={16} color="var(--text3)" />}
                      </div>
                    </div>
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 11, color: "var(--text2)", whiteSpace: "nowrap" }}>
                    #{a.person_id}
                  </td>
                  <td style={{ fontWeight: 600, color: "var(--text)" }}>{a.person_name}</td>
                  <td style={{ fontSize: 11, color: "var(--accent)" }}>{identity}</td>
                  <td>
                    <span className={`badge ${isCheckedIn ? "badge-green" : "badge-grey"}`}>
                      {isCheckedIn ? "Inside" : "Checked Out"}
                    </span>
                  </td>
                  <td style={{ fontSize: 11, color: "var(--text2)", whiteSpace: "nowrap" }}>
                    {new Date(a.checkin_time).toLocaleString("en-IN", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })}
                    {a.checkout_time && ` → ${new Date(a.checkout_time).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}`}
                  </td>
                  <td style={{ fontSize: 11, color: a.duration_str ? "var(--green)" : "var(--text2)" }}>
                    {a.duration_str || "Active"}
                  </td>
                  <td style={{ fontSize: 11 }}>
                    <span className="badge badge-grey">{a.camera_id}</span>
                  </td>
                  <td>
                    <button className="btn btn-sm btn-icon" title="Delete record"
                      style={{ color: "var(--red)" }} onClick={() => deleteSingleAtt(a.id)}>
                      <Icon path={icons.trash} size={12} />
                    </button>
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && <tr><td colSpan={10}><div className="empty">No attendance records found</div></td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── UNREGISTERED PERSONS PAGE ────────────────────────────────
function UnregisteredPage() {
  const [viewTab, setViewTab] = useState("grouped"); // "grouped" | "raw"
  const [unknowns, setUnknowns] = useState([]);
  const [events, setEvents] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const loadData = useCallback(async () => {
    setLoading(true);
    if (viewTab === "grouped") {
      const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
      const uRes = await fetchAPI(`/api/v1/unknown-persons?resolved=false&page=${page}&limit=10${searchParam}`);
      if (uRes) {
        setUnknowns(uRes.unknown_persons || []);
        setTotalCount(uRes.total_count || 0);
        setTotalPages(uRes.total_pages || 1);
      }
    } else {
      const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
      const eRes = await fetchAPI(`/api/v1/events?limit=10&page=${page}&matched=false${searchParam}`);
      if (eRes) {
        setEvents(eRes.events || []);
        setTotalCount(eRes.total_count || 0);
        setTotalPages(eRes.total_pages || 1);
      }
    }
    setLoading(false);
  }, [viewTab, page, search]);

  useEffect(() => { loadData(); const t = setInterval(loadData, 20000); return () => clearInterval(t); }, [loadData]);

  const deleteRawEvent = async (id) => {
    await fetchAPI(`/api/v1/events/${id}`, { method: "DELETE" });
    loadData();
  };

  const dismissUnknown = async (id) => {
    await fetchAPI(`/api/v1/unknown-persons/${id}/delete`, { method: "DELETE" });
    loadData();
  };

  return (
    <div>
      {/* Top controls */}
      <div className="toolbar" style={{ marginBottom: 12 }}>
        <div className="toolbar-group">
          <button
            className={`btn btn-sm ${viewTab === "grouped" ? "btn-primary" : ""}`}
            onClick={() => { setViewTab("grouped"); setPage(1); }}
          >
            👥 Grouped Unregistered Faces
          </button>
          <button
            className={`btn btn-sm ${viewTab === "raw" ? "btn-primary" : ""}`}
            onClick={() => { setViewTab("raw"); setPage(1); }}
          >
            ⚡ Raw Detection Logs
          </button>
        </div>
        <div className="search-box">
          <span className="search-icon"><Icon path={icons.search} size={13} /></span>
          <input
            type="text"
            placeholder="Search tracking ID or camera..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
          />
        </div>
        <button className="btn btn-sm" onClick={loadData}>
          <Icon path={icons.refresh} size={12} /> Refresh
        </button>
      </div>

      {viewTab === "grouped" ? (
        /* ── Tracked Grouped Unknown Persons ── */
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Face Snapshot</th>
                <th>Tracking ID</th>
                <th>Total Sightings / Count</th>
                <th>Camera Locations</th>
                <th>First Seen</th>
                <th>Last Seen</th>
                <th style={{ textAlign: "right" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {unknowns.map((u, i) => (
                <tr key={i}>
                  <td>
                    <div className="avatar" style={{ width: 42, height: 42, borderRadius: 6 }}>
                      {u.id
                        ? <img src={`/api/v1/unknowns/${u.id}/snapshot`} alt="" loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover" }} onError={e => e.target.style.display = 'none'} />
                        : <Icon path={icons.unknown} size={18} color="var(--orange)" />}
                    </div>
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 12, fontWeight: 600, color: "var(--text)" }}>
                    {u.tracking_id}
                  </td>
                  <td>
                    <span className="badge badge-orange" style={{ fontWeight: 600, fontSize: 11, padding: "3px 8px" }}>
                      {u.event_count || 1} sighting(s)
                    </span>
                  </td>
                  <td>
                    {(u.camera_ids || []).map((cid, j) => (
                      <span key={j} className="badge badge-grey" style={{ marginRight: 4, fontSize: 10 }}>{cid}</span>
                    ))}
                  </td>
                  <td style={{ fontSize: 11, color: "var(--text2)", whiteSpace: "nowrap" }}>
                    {u.first_seen ? new Date(u.first_seen).toLocaleString() : "—"}
                  </td>
                  <td style={{ fontSize: 11, color: "var(--text2)", whiteSpace: "nowrap" }}>
                    {u.last_seen ? new Date(u.last_seen).toLocaleString() : "—"}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      className="btn btn-sm btn-icon"
                      style={{ color: "var(--red)" }}
                      title="Delete / Dismiss"
                      onClick={() => dismissUnknown(u.id)}
                    >
                      <Icon path={icons.trash} size={13} />
                    </button>
                  </td>
                </tr>
              ))}
              {unknowns.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <div className="empty">
                      No unregistered persons currently tracked.
                      <br />
                      <span style={{ fontSize: 11, color: "var(--text3)" }}>New unknown faces detected on CCTV will automatically appear here.</span>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        /* ── Raw Unmatched Events ── */
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Profile Crop</th>
                <th>Camera</th>
                <th>Confidence</th>
                <th>Time</th>
                <th style={{ textAlign: "right" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e, i) => (
                <tr key={i}>
                  <td>
                    <div className="avatar">
                      {e.id
                        ? <img src={`/api/v1/events/${e.id}/snapshot`} alt="" loading="lazy" onError={err => err.target.style.display = 'none'} />
                        : <Icon path={icons.enroll} size={14} color="var(--text3)" />}
                    </div>
                  </td>
                  <td><span className="badge badge-grey">{e.camera_id}</span></td>
                  <td style={{ fontSize: 11, color: "var(--text2)" }}>
                    {e.confidence ? `${(e.confidence * 100).toFixed(0)}%` : "—"}
                  </td>
                  <td style={{ fontSize: 11, color: "var(--text2)", whiteSpace: "nowrap" }}>
                    {new Date(e.timestamp).toLocaleString()}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn btn-sm btn-icon" style={{ color: "var(--red)" }} title="Delete Log" onClick={() => deleteRawEvent(e.id)}>
                      <Icon path={icons.trash} size={11} />
                    </button>
                  </td>
                </tr>
              ))}
              {events.length === 0 && <tr><td colSpan={5}><div className="empty">No raw unregistered detection logs found</div></td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination Controls */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 14, padding: "8px 4px" }}>
        <div style={{ fontSize: 12, color: "var(--text2)" }}>
          Showing page <strong>{page}</strong> of <strong>{totalPages}</strong> ({totalCount} total records)
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button className="btn btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>
            ← Previous
          </button>
          <span style={{ fontSize: 12, fontWeight: 600, padding: "0 6px" }}>
            {page} / {totalPages}
          </span>
          <button className="btn btn-sm" disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))}>
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── SYSTEM SETTINGS PAGE ─────────────────────────────────────
function SettingsPage() {
  const [settings, setSettings] = useState({
    face_threshold: 0.50,
    blacklist_threshold: 0.35,
    visitor_threshold: 0.50,
    dedup_threshold: 0.65,
    camera_cooldown: 120,
    global_cooldown: 300,
    dedup_seconds: 120,
    known_suppress_seconds: 120,
    camera_unknown_cooldown: 15,
  });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  const faceVal = Number(settings.face_threshold);
  const safeFaceVal = !isNaN(faceVal) && faceVal > 0 ? faceVal : 0.50;

  const loadSettings = useCallback(async () => {
    const data = await fetchAPI("/api/v1/settings/system");
    if (data) {
      setSettings({
        ...data,
        face_threshold: Number(data.face_threshold || 0.50),
        blacklist_threshold: Number(data.blacklist_threshold || 0.35),
        visitor_threshold: Number(data.visitor_threshold || 0.50),
        dedup_threshold: Number(data.dedup_threshold || 0.65),
        camera_cooldown: Number(data.camera_cooldown || 120),
        global_cooldown: Number(data.global_cooldown || 300),
        dedup_seconds: Number(data.dedup_seconds || 120),
        known_suppress_seconds: Number(data.known_suppress_seconds || 120),
        camera_unknown_cooldown: Number(data.camera_unknown_cooldown || 15),
      });
    }
  }, []);

  useEffect(() => { loadSettings(); }, [loadSettings]);

  const saveSettings = async () => {
    setSaving(true);
    setMsg(null);
    const res = await fetchAPI("/api/v1/settings/system", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    setSaving(false);
    if (res) {
      setSettings(res);
      setMsg("✓ System settings & face threshold values saved successfully!");
      setTimeout(() => setMsg(null), 3000);
    } else {
      setMsg("❌ Failed to save settings.");
    }
  };

  return (
    <div style={{ maxWidth: 850 }}>
      {/* Notification banner */}
      {msg && (
        <div style={{
          padding: "10px 14px", borderRadius: 6, marginBottom: 16, fontSize: 13, fontWeight: 500,
          background: msg.startsWith("✓") ? "rgba(61,186,110,0.15)" : "rgba(224,82,82,0.15)",
          border: msg.startsWith("✓") ? "1px solid rgba(61,186,110,0.4)" : "1px solid rgba(224,82,82,0.4)",
          color: msg.startsWith("✓") ? "var(--green)" : "var(--red)"
        }}>
          {msg}
        </div>
      )}

      {/* Main Face Recognition Threshold Card */}
      <div className="table-wrap" style={{ padding: 20, marginBottom: 20 }}>
        <div style={{ borderBottom: "1px solid var(--border)", paddingBottom: 12, marginBottom: 18, display: "flex", alignItems: "center", gap: 10 }}>
          <Icon path={icons.settings} size={18} color="var(--accent)" />
          <span style={{ fontSize: 15, fontWeight: 600, color: "var(--text)" }}>
            Face Recognition Match Threshold Settings
          </span>
        </div>

        {/* Dynamic Face Threshold Slider */}
        <div style={{ marginBottom: 24, background: "var(--surface2)", padding: 16, borderRadius: 6, border: "1px solid var(--border)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <label className="form-label" style={{ fontWeight: 600, color: "var(--text)", fontSize: 13 }}>
              Face Match Similarity Threshold
            </label>
            <span className="badge badge-blue" style={{ fontSize: 13, fontFamily: "monospace", padding: "4px 10px" }}>
              {(safeFaceVal * 100).toFixed(0)}% ({safeFaceVal.toFixed(2)})
            </span>
          </div>

          <input
            type="range"
            min="0.30"
            max="0.85"
            step="0.01"
            value={safeFaceVal}
            onChange={e => setSettings({ ...settings, face_threshold: parseFloat(e.target.value) })}
            style={{ width: "100%", accentColor: "var(--accent)", cursor: "pointer" }}
          />

          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text2)", marginTop: 6 }}>
            <span>0.30 (Lenient / High Recall)</span>
            <span style={{ color: "var(--green)", fontWeight: 600 }}>0.50 (Recommended Standard)</span>
            <span>0.85 (Strict Precision)</span>
          </div>

          <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 10, lineHeight: "1.4em" }}>
            💡 <b>How it works:</b> Higher threshold requires a stricter facial match before identifying employees. Lower threshold helps recognize faces under dim lighting or side angles.
          </div>
        </div>

        {/* Blacklist Threshold & Visitor Threshold */}
        <div className="form-row" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 16, marginBottom: 18 }}>
          <div className="form-group">
            <label className="form-label">Suspected Match Threshold</label>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="number"
                step="0.01"
                min="0.25"
                max="0.49"
                value={settings.suspected_threshold ?? 0.37}
                onChange={e => setSettings({ ...settings, suspected_threshold: parseFloat(e.target.value) })}
                style={{ width: 120 }}
              />
              <span style={{ fontSize: 11, color: "var(--text2)" }}>Default: 0.37</span>
            </div>
            <div style={{ fontSize: 10, color: "var(--orange)", marginTop: 4 }}>
              ⚠ Below main threshold — assigns same ID but marks as "Suspected"
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Blacklist Alert Threshold</label>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="number"
                step="0.01"
                min="0.20"
                max="0.80"
                value={settings.blacklist_threshold}
                onChange={e => setSettings({ ...settings, blacklist_threshold: parseFloat(e.target.value) })}
                style={{ width: 120 }}
              />
              <span style={{ fontSize: 11, color: "var(--text2)" }}>Default: 0.35</span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Visitor Match Threshold</label>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="number"
                step="0.01"
                min="0.30"
                max="0.85"
                value={settings.visitor_threshold}
                onChange={e => setSettings({ ...settings, visitor_threshold: parseFloat(e.target.value) })}
                style={{ width: 120 }}
              />
              <span style={{ fontSize: 11, color: "var(--text2)" }}>Default: 0.50</span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Deduplication Similarity Limit</label>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="number"
                step="0.01"
                min="0.40"
                max="0.90"
                value={settings.dedup_threshold}
                onChange={e => setSettings({ ...settings, dedup_threshold: parseFloat(e.target.value) })}
                style={{ width: 120 }}
              />
              <span style={{ fontSize: 11, color: "var(--text2)" }}>Default: 0.65</span>
            </div>
          </div>
        </div>

        <div className="form-row" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div className="form-group">
            <label className="form-label">Camera Cooldown Window (Seconds)</label>
            <input
              type="number"
              value={settings.camera_cooldown}
              onChange={e => setSettings({ ...settings, camera_cooldown: parseInt(e.target.value) || 0 })}
              style={{ width: "100%" }}
            />
            <span style={{ fontSize: 10, color: "var(--text2)" }}>Prevents duplicate logs for same person on a camera</span>
          </div>

          <div className="form-group">
            <label className="form-label">Global Re-Entry Cooldown (Seconds)</label>
            <input
              type="number"
              value={settings.global_cooldown}
              onChange={e => setSettings({ ...settings, global_cooldown: parseInt(e.target.value) || 0 })}
              style={{ width: "100%" }}
            />
            <span style={{ fontSize: 10, color: "var(--text2)" }}>Time window before triggering new attendance visit</span>
          </div>
        </div>

        {/* Dedup & Timing Settings */}
        <div style={{ marginTop: 18, borderTop: "1px solid var(--border)", paddingTop: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
            <Icon path={icons.settings} size={14} color="var(--accent)" />
            Deduplication & Timing
          </div>
          <div className="form-row" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
            <div className="form-group">
              <label className="form-label">Person Dedup Cooldown (sec)</label>
              <input
                type="number"
                min="30"
                max="600"
                value={settings.dedup_seconds}
                onChange={e => setSettings({ ...settings, dedup_seconds: parseInt(e.target.value) || 30 })}
                style={{ width: "100%" }}
              />
              <span style={{ fontSize: 10, color: "var(--text2)" }}>Min time before same person is logged again (default: 120)</span>
            </div>

            <div className="form-group">
              <label className="form-label">Known Person Suppress (sec)</label>
              <input
                type="number"
                min="30"
                max="600"
                value={settings.known_suppress_seconds}
                onChange={e => setSettings({ ...settings, known_suppress_seconds: parseInt(e.target.value) || 30 })}
                style={{ width: "100%" }}
              />
              <span style={{ fontSize: 10, color: "var(--text2)" }}>Suppress unknown alerts near a known person (default: 120)</span>
            </div>

            <div className="form-group">
              <label className="form-label">Unknown Save Cooldown (sec)</label>
              <input
                type="number"
                min="5"
                max="120"
                value={settings.camera_unknown_cooldown}
                onChange={e => setSettings({ ...settings, camera_unknown_cooldown: parseInt(e.target.value) || 5 })}
                style={{ width: "100%" }}
              />
              <span style={{ fontSize: 10, color: "var(--text2)" }}>Time between unknown person saves per camera (default: 15)</span>
            </div>
          </div>
        </div>

        {/* Action Button */}
        <div style={{ marginTop: 20, paddingTop: 14, borderTop: "1px solid var(--border)", display: "flex", justifyContent: "flex-end" }}>
          <button className="btn btn-primary" onClick={saveSettings} disabled={saving}>
            {saving ? "Saving Changes..." : "Save System Settings"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── FLOOR FLOW VIEW (camera map + per-camera head counts) ───
function FloorFlowView({ onOpenPerson }) {
  const [cams, setCams] = useState([]);
  const [flows, setFlows] = useState([]);
  const [tracks, setTracks] = useState([]);
  const [camStats, setCamStats] = useState({});
  const [positions, setPositions] = useState({});
  const [placingCam, setPlacingCam] = useState(null);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [flowMode, setFlowMode] = useState(false);
  const [flowFrom, setFlowFrom] = useState(null);
  const [selectedCam, setSelectedCam] = useState(null);   // small popup box
  const canvasRef = useRef(null);
  const dragRef = useRef(null);

  const loadAll = useCallback(async () => {
    const [c, f, t, cs, rm] = await Promise.all([
      fetchAPI("/api/v1/cameras"),
      fetchAPI("/api/v1/tracking/flows"),
      fetchAPI("/api/v1/tracking/live?active_seconds=120"),
      fetchAPI("/api/v1/tracking/cam-stats"),
      fetchAPI("/api/v1/tracking/room-map").catch(() => null),
    ]);
    if (c && c.cameras) {
      const list = c.cameras || [];
      setCams(list);
      setPositions(prev => {
        const next = { ...prev };
        list.forEach(cam => { if (cam.map_x != null && cam.map_y != null) next[cam.id] = { x: cam.map_x, y: cam.map_y }; });
        return next;
      });
    }
    if (f && f.success) setFlows(f.flows || []);
    if (t && t.success) setTracks(t.tracks || []);
    if (cs && cs.success) setCamStats(cs.cameras || {});
    // restore room zone positions saved earlier (kept so old positions are not lost)
    if (rm && rm.success && rm.positions) {
      const first = Object.entries(rm.positions || {})[0];
      if (first && !window.__roomPosSeen) window.__roomPosSeen = true;
    }
  }, []);

  useEffect(() => {
    loadAll();
    const t = setInterval(loadAll, 4000);
    return () => clearInterval(t);
  }, [loadAll]);

  const savePos = async (camId, x, y) => {
    setPositions(p => ({ ...p, [camId]: { x, y } }));
    await fetchAPI(`/api/v1/cameras/${encodeURIComponent(camId)}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ map_x: Math.round(x * 10) / 10, map_y: Math.round(y * 10) / 10 }),
    });
  };

  const placeOnCanvas = (e) => {
    if (!placingCam) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.min(96, Math.max(4, ((e.clientX - rect.left) / rect.width) * 100));
    const y = Math.min(88, Math.max(12, ((e.clientY - rect.top) / rect.height) * 100));
    savePos(placingCam, x, y);
    setPlacingCam(null);
  };

  const itemMouseDown = (e, camId) => {
    e.stopPropagation();
    const pos = positions[camId] || { x: 50, y: 50 };
    dragRef.current = { camId, startX: e.clientX, startY: e.clientY, origX: pos.x, origY: pos.y, moved: false };
  };

  const canvasMouseMove = (e) => {
    const d = dragRef.current;
    if (!d || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const dx = ((e.clientX - d.startX) / rect.width) * 100;
    const dy = ((e.clientY - d.startY) / rect.height) * 100;
    if (Math.abs(dx) + Math.abs(dy) > 1.5) d.moved = true;
    setPositions(p => ({ ...p, [d.camId]: {
      x: Math.min(96, Math.max(4, d.origX + dx)),
      y: Math.min(88, Math.max(8, d.origY + dy)),
    } }));
  };

  const canvasMouseUp = () => {
    const d = dragRef.current;
    if (d && d.moved) {
      const pos = positions[d.camId];
      if (pos) savePos(d.camId, pos.x, pos.y);
    }
    dragRef.current = null;
  };

  const poleClick = (cam) => {
    if (flowMode) {
      if (!flowFrom) { setFlowFrom(cam.id); return; }
      if (flowFrom !== cam.id) {
        const exists = flows.some(f => (f.from_cam === flowFrom && f.to_cam === cam.id));
        if (!exists) {
          const next = [...flows, { from_cam: flowFrom, to_cam: cam.id }];
          setFlows(next);
          fetchAPI("/api/v1/tracking/flows", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ flows: next }) });
        }
        setFlowFrom(cam.id === flowFrom ? null : cam.id);
      }
      return;
    }
    setSelectedCam(cam);
  };

  const saveFlows = (next) => {
    setFlows(next);
    fetchAPI("/api/v1/tracking/flows", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ flows: next }) });
  };

  const placed = cams.filter(c => positions[c.id]);
  const unplaced = cams.filter(c => !positions[c.id]);
  const ensureImg = (img) => img ? (img.startsWith("data:") || img.startsWith("http") || img.startsWith("/") ? img : `data:image/jpeg;base64,${img}`) : null;

  const statsFor = (camId) => camStats[camId] || { in: 0, out: 0, inside_count: 0 };
  // faces of people detected at this camera right now
  const facesHere = selectedCam ? tracks.filter(t => t.last_camera === selectedCam.id) : [];

  const typeLabel = (t) => t === "frs" ? "FRS" : t === "headcount" ? "Head Count" : t === "both" ? "FRS + Head Count"
    : t === "checkin" ? "Entry (legacy)" : t === "checkout" ? "Exit (legacy)" : (t || "FRS");

  return (
    <div className="table-wrap" style={{ padding: 14, marginBottom: 16 }}>
      {/* Toolbar */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12.5, fontWeight: 600 }}>
          <Icon path={icons.camera} size={13} color="var(--accent)" /> Camera Floor Flow
        </span>
        <span style={{ fontSize: 10, color: "var(--text3)" }}>badge = head count at that camera · click a camera for faces</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6, position: "relative" }}>
          <button className={`btn btn-sm ${flowMode ? "btn-primary" : ""}`}
            onClick={() => { setFlowMode(f => !f); setFlowFrom(null); }}>
            🔗 {flowMode ? (flowFrom ? `From: ${flowFrom} — pick target` : "Connect flow (click 2 poles)") : "Connect Flow"}
          </button>
          <button className="btn btn-sm btn-primary" onClick={() => setShowAddMenu(s => !s)}>
            <Icon path={icons.plus} size={11} /> Add Camera
          </button>
          {showAddMenu && (
            <div style={{ position: "absolute", top: "100%", right: 0, zIndex: 50, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6, minWidth: 220, maxHeight: 220, overflowY: "auto", boxShadow: "0 8px 24px rgba(0,0,0,.5)" }}>
              {unplaced.length === 0 && <div style={{ padding: 10, fontSize: 11, color: "var(--text3)" }}>All cameras are already placed</div>}
              {unplaced.map(c => (
                <div key={c.id} style={{ padding: "8px 12px", cursor: "pointer", fontSize: 12 }} className="nav-item"
                  onClick={() => { setPlacingCam(c.id); setShowAddMenu(false); }}>
                  📹 {c.name || c.id} <span style={{ color: "var(--text3)", fontSize: 10 }}>({c.id})</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {placingCam && (
        <div style={{ padding: "7px 12px", marginBottom: 8, borderRadius: 6, background: "rgba(74,158,255,.12)", border: "1px solid rgba(74,158,255,.4)", fontSize: 12, color: "var(--accent)" }}>
          📍 Click anywhere on the canvas to place <b>{placingCam}</b> there
          <button className="btn btn-sm" style={{ marginLeft: 10 }} onClick={() => setPlacingCam(null)}>Cancel</button>
        </div>
      )}

      {/* Canvas */}
      <div ref={canvasRef}
        onMouseDown={placeOnCanvas}
        onMouseMove={canvasMouseMove}
        onMouseUp={canvasMouseUp}
        onMouseLeave={canvasMouseUp}
        onClick={() => setSelectedCam(null)}
        style={{
          position: "relative", width: "100%", height: 340, borderRadius: 8, cursor: placingCam ? "crosshair" : "default",
          background: "linear-gradient(180deg,#f7f8fa 0%,#eef1f5 100%)",
          backgroundImage: "linear-gradient(rgba(0,0,0,.06) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,.06) 1px, transparent 1px)",
          backgroundSize: "28px 28px", border: "1px solid var(--border)", overflow: "hidden", userSelect: "none",
        }}>
        {/* Flow arrows */}
        <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
          <defs>
            <marker id="arrowhead" markerWidth="8" markerHeight="7" refX="7" refY="3.5" orient="auto">
              <polygon points="0 0, 8 3.5, 0 7" fill="#3b82f6" />
            </marker>
          </defs>
          {flows.map((f, i) => {
            const a = positions[f.from_cam], b = positions[f.to_cam];
            if (!a || !b) return null;
            return <line key={i} x1={`${a.x}%`} y1={`${a.y - 4}%`} x2={`${b.x}%`} y2={`${b.y - 4}%`}
              stroke="#3b82f6" strokeWidth={2.5} markerEnd="url(#arrowhead)" strokeDasharray="7 4" opacity={0.85} />;
          })}
        </svg>

        {/* Camera poles — badge = THIS camera's head count */}
        {placed.map(cam => {
          const pos = positions[cam.id];
          const running = cam.running;
          const st = statsFor(cam.id);
          const count = st.inside_count || 0;
          const isSel = selectedCam && selectedCam.id === cam.id;
          const isFlowSrc = flowFrom === cam.id;
          const isHC = cam.camera_type === "headcount" || cam.camera_type === "both";
          return (
            <div key={cam.id}
              onMouseDown={e => itemMouseDown(e, cam.id)}
              onClick={e => { e.stopPropagation(); poleClick(cam); }}
              style={{
                position: "absolute", left: `${pos.x}%`, top: `${pos.y}%`, transform: "translate(-50%,-100%)",
                cursor: flowMode ? "pointer" : "grab", textAlign: "center", zIndex: isFlowSrc ? 20 : 10,
                filter: isFlowSrc ? "drop-shadow(0 0 6px #3b82f6)" : isSel ? "drop-shadow(0 0 5px var(--green))" : "none",
              }}>
              <svg width="34" height="52" viewBox="0 0 34 52">
                <line x1="17" y1="16" x2="17" y2="50" stroke="#5a6472" strokeWidth={3} />
                <ellipse cx="17" cy="50" rx="7" ry="2.4" fill="#5a6472" />
                <rect x="6" y="2" width="22" height="13" rx={3} fill={running ? "#16a34a" : "#94a3b8"} stroke={isSel ? "#22c55e" : "#334155"} strokeWidth={isSel ? 2 : 1} />
                <circle cx="17" cy="8.5" r={3.2} fill="#0f172a" />
                <circle cx="17" cy="8.5" r={1.6} fill={running ? "#f87171" : "#cbd5e1"} />
              </svg>
              {isHC && (
                <div title={`${cam.name || cam.id} — head count (people who crossed IN on this camera)`}
                  style={{ position: "absolute", top: -10, right: -12, background: count > 0 ? "var(--green)" : "#64748b", color: "#fff", borderRadius: 10, fontSize: 10, fontWeight: 800, padding: "1px 6px" }}>
                  {count}
                </div>
              )}
              <div style={{
                marginTop: 2, fontSize: 10, fontWeight: 600, color: "#1e293b", background: "rgba(255,255,255,.92)",
                border: "1px solid #cbd5e1", borderRadius: 4, padding: "1px 6px", display: "inline-block",
                maxWidth: 130, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>
                {cam.name || cam.id}
              </div>
            </div>
          );
        })}

        {placed.length === 0 && !placingCam && (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b", fontSize: 13 }}>
            Empty floor — click <b>&nbsp;Add Camera&nbsp;</b> to place your cameras here
          </div>
        )}
      </div>

      {/* Flow list + clear */}
      {flows.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8, alignItems: "center" }}>
          <span style={{ fontSize: 10.5, color: "var(--text3)" }}>Flows:</span>
          {flows.map((f, i) => (
            <span key={i} className="badge badge-blue" style={{ fontSize: 9.5 }}>
              {f.from_cam} → {f.to_cam}
              <span style={{ cursor: "pointer", marginLeft: 4 }}
                onClick={() => saveFlows(flows.filter((_, j) => j !== i))}>✕</span>
            </span>
          ))}
          <button className="btn btn-sm" style={{ fontSize: 10 }} onClick={() => saveFlows([])}>Clear all</button>
        </div>
      )}

      {/* ── Camera box: head count + in/out + faces detected here ── */}
      {selectedCam && (() => {
        const st = statsFor(selectedCam.id);
        const isHC = selectedCam.camera_type === "headcount" || selectedCam.camera_type === "both";
        return (
          <div style={{ marginTop: 10, border: "1px solid var(--border)", borderRadius: 8, padding: 12, background: "var(--surface2)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
              <span className="badge badge-blue" style={{ fontSize: 10 }}>{selectedCam.id}</span>
              <b style={{ fontSize: 12.5 }}>{selectedCam.name || selectedCam.id}</b>
              <span className="badge badge-grey" style={{ fontSize: 9.5 }}>{typeLabel(selectedCam.camera_type)}</span>
              <button className="btn btn-sm btn-icon" style={{ marginLeft: "auto", color: "var(--red)" }} onClick={() => setSelectedCam(null)}><Icon path={icons.x} size={12} /></button>
            </div>

            {isHC ? (
              <>
                {/* Head count boxes */}
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 14px" }}>
                    <span style={{ fontSize: 11, color: "var(--text2)" }}>Head count</span>
                    <b style={{ fontSize: 20, color: st.inside_count > 0 ? "var(--green)" : "var(--text)" }}>{st.inside_count}</b>
                  </span>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 14px" }}>
                    <span style={{ fontSize: 11, color: "var(--text2)" }}>⬇ In</span>
                    <b style={{ fontSize: 20, color: "var(--green)" }}>{st.in}</b>
                  </span>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 14px" }}>
                    <span style={{ fontSize: 11, color: "var(--text2)" }}>⬆ Out</span>
                    <b style={{ fontSize: 20, color: "var(--orange)" }}>{st.out}</b>
                  </span>
                </div>

                {/* Faces detected at this camera */}
                <div style={{ fontSize: 10.5, color: "var(--text2)", marginBottom: 5 }}>
                  👤 Faces detected at this camera ({facesHere.length}) — click one for details:
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {facesHere.map(t => {
                    const known = t.person_name && t.person_name !== "Unknown";
                    const img = ensureImg(t.snapshot);
                    return (
                      <div key={t.global_id} title="Click for person details"
                        onClick={e => { e.stopPropagation(); onOpenPerson && onOpenPerson(t); }}
                        style={{ display: "flex", alignItems: "center", gap: 6, background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 6, padding: "4px 8px", cursor: "pointer" }}>
                        {img
                          ? <img src={img} style={{ width: 34, height: 34, borderRadius: 5, objectFit: "cover" }} onError={e => e.target.style.display = "none"} />
                          : <Icon path={icons.humans} size={16} color="var(--text3)" />}
                        <div>
                          <div style={{ fontSize: 11, fontWeight: 600, maxWidth: 110, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {known ? t.person_name : "👤 Unknown"}
                          </div>
                          <div style={{ fontSize: 9, fontFamily: "monospace", color: known ? "var(--green)" : "var(--orange)" }}>{t.global_id}</div>
                        </div>
                      </div>
                    );
                  })}
                  {facesHere.length === 0 && <span style={{ fontSize: 10.5, color: "var(--text3)" }}>No one detected right now</span>}
                </div>
              </>
            ) : (
              <div style={{ fontSize: 11, color: "var(--text3)" }}>
                FRS camera — face detection only, no head counting. Set type to <b>Head Count</b> or <b>FRS + Head Count</b> in camera configuration to get counts.
              </div>
            )}

            <div style={{ marginTop: 10, fontSize: 10, color: "var(--text3)" }}>
              ⚙ Type / count line / room are configured in <b>Cameras → ⚙ config</b>.
            </div>
          </div>
        );
      })()}
    </div>
  );
}

// ─── GLOBAL TRACKING PAGE (floor flow + room head counts) ────
function GlobalTrackingPage({ onOpenCameras }) {
  const [rooms, setRooms] = useState([]);
  const [movements, setMovements] = useState([]);
  const [updated, setUpdated] = useState(null);
  const [expandedRoom, setExpandedRoom] = useState(null);
  const [roomHistory, setRoomHistory] = useState([]);
  const [person, setPerson] = useState(null);

  const load = useCallback(async () => {
    const [r1, r3] = await Promise.all([
      fetchAPI("/api/v1/rooms/occupancy"),
      fetchAPI("/api/v1/tracking/movements?limit=200"),
    ]);
    if (r1 && r1.success) setRooms(r1.rooms || []);
    if (r3 && r3.success) setMovements(r3.movements || []);
    setUpdated(new Date().toLocaleTimeString());
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const openHistory = async (roomId) => {
    if (expandedRoom === roomId) { setExpandedRoom(null); return; }
    setExpandedRoom(roomId);
    const r = await fetchAPI(`/api/v1/rooms/${encodeURIComponent(roomId)}/movements?limit=50`);
    if (r && r.success) setRoomHistory(r.movements || []);
  };

  const resetRoom = async (roomId) => {
    if (!window.confirm(`Reset occupancy for room "${roomId}"?`)) return;
    await fetchAPI(`/api/v1/rooms/${encodeURIComponent(roomId)}/reset`, { method: "POST" });
    load();
  };

  // person details: sightings + which rooms they are inside now
  const personInfo = person ? (() => {
    const seen = movements.filter(m => m.global_id === person.global_id);
    const insideRooms = rooms.filter(r => (r.inside || []).some(p => p.global_id === person.global_id));
    return { seen, insideRooms };
  })() : null;

  const ensureImg = (img) => img ? (img.startsWith("data:") || img.startsWith("http") || img.startsWith("/") ? img : `data:image/jpeg;base64,${img}`) : null;

  return (
    <div>
      <FloorFlowView onOpenPerson={setPerson} />
      <div className="toolbar" style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ fontSize: 11, color: "var(--text3)" }}>
          {updated ? `Live — updated ${updated}, refreshes every 5s` : "Loading..."}
        </span>
        <span style={{ fontSize: 11, color: "var(--text2)", marginLeft: "auto" }}>
          {rooms.length} room{rooms.length === 1 ? "" : "s"} · total inside:{" "}
          <b style={{ color: "var(--green)" }}>{rooms.reduce((s, r) => s + (r.inside_count || 0), 0)}</b>
        </span>
        <button className="btn btn-sm" onClick={onOpenCameras}>⚙ Configure cameras (zones / lines / rooms)</button>
        <button className="btn btn-sm" onClick={load}><Icon path={icons.refresh} size={12} /> Refresh</button>
      </div>

      {/* Room occupancy cards */}
      {rooms.length === 0 ? (
        <div className="table-wrap" style={{ padding: 30, textAlign: "center", color: "var(--text3)", fontSize: 12.5 }}>
          No rooms yet.<br />
          Assign a <b>Room ID</b> to a camera (Cameras → ⚙ config → Room ID),<br />
          set its type to <b>Head Count</b> or <b>FRS + Head Count</b> and draw the <b>count line</b>.
        </div>
      ) : (
        <div className="stats-row" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
          {rooms.map(room => (
            <div key={room.room_id} className="stat-box" style={{ border: "1px solid var(--border)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div className="stat-box-label" style={{ fontSize: 12 }}>🏠 {room.room_id}</div>
                <div style={{ display: "flex", gap: 4 }}>
                  <button className="btn btn-sm btn-icon" title="Movement history" onClick={() => openHistory(room.room_id)}>
                    <Icon path={icons.dashboard} size={12} />
                  </button>
                  <button className="btn btn-sm btn-icon" title="Reset occupancy" style={{ color: "var(--red)" }} onClick={() => resetRoom(room.room_id)}>
                    <Icon path={icons.trash} size={12} />
                  </button>
                </div>
              </div>
              <div className="stat-box-value" style={{ color: room.inside_count > 0 ? "var(--green)" : "var(--text)" }}>
                {room.inside_count}
                <span style={{ fontSize: 12, color: "var(--text3)", fontWeight: 400 }}> inside</span>
              </div>
              <div style={{ display: "flex", gap: 14, fontSize: 11, color: "var(--text2)", margin: "4px 0 8px" }}>
                <span>⬇ Entries: <b style={{ color: "var(--green)" }}>{room.entries}</b></span>
                <span>⬆ Exits: <b style={{ color: "var(--red)" }}>{room.exits}</b></span>
              </div>
              {room.inside && room.inside.length > 0 && (
                <div style={{ maxHeight: 110, overflowY: "auto", borderTop: "1px solid var(--border)", paddingTop: 6 }}>
                  {room.inside.map(p => (
                    <div key={p.global_id} style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, padding: "2px 0", cursor: "pointer" }}
                      onClick={() => setPerson(p)}>
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {p.person_name === "Unknown" ? "👤 Unknown" : p.person_name}
                      </span>
                      <span style={{ fontFamily: "monospace", color: "var(--text3)", fontSize: 9.5 }}>{p.global_id}</span>
                    </div>
                  ))}
                </div>
              )}
              <div style={{ marginTop: 8, borderTop: "1px solid var(--border)", paddingTop: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
                {room.cameras.map(c => (
                  <span key={c.id} className="badge badge-blue" style={{ fontSize: 9 }}>
                    {c.id}{c.running ? " ●" : " ○"}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Room movement history */}
      {expandedRoom && (
        <div className="table-wrap" style={{ marginBottom: 16 }}>
          <div style={{ padding: "10px 14px", fontWeight: 600, fontSize: 12.5, borderBottom: "1px solid var(--border)" }}>
            📜 Movement history — {expandedRoom}
          </div>
          <div style={{ maxHeight: 240, overflowY: "auto" }}>
            <table>
              <thead><tr><th>Time</th><th>Direction</th><th>Person</th><th>Global ID</th><th>Camera</th></tr></thead>
              <tbody>
                {roomHistory.map(m => (
                  <tr key={m.id}>
                    <td style={{ fontFamily: "monospace", fontSize: 10.5 }}>{(m.timestamp || "").slice(0, 19).replace("T", " ")}</td>
                    <td><span className={`badge ${m.direction === "entry" || m.direction === "in" ? "badge-green" : "badge-orange"}`} style={{ fontSize: 9.5 }}>{m.direction === "entry" || m.direction === "in" ? "⬇ IN" : "⬆ OUT"}</span></td>
                    <td style={{ fontWeight: 500 }}>{m.person_name}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 10.5, color: m.global_id && m.global_id.startsWith("PERSON") ? "var(--green)" : "var(--orange)" }}>{m.global_id}</td>
                    <td>{m.camera_id}</td>
                  </tr>
                ))}
                {roomHistory.length === 0 && <tr><td colSpan={5}><div className="empty">No movements recorded yet</div></td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Person popup (known or unknown): entries + room head count ── */}
      {person && personInfo && (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && setPerson(null)}>
          <div className="modal" style={{ maxWidth: 420 }}>
            <div className="modal-header">
              <span className="modal-title">Person — {person.person_name === "Unknown" ? "👤 Unknown" : person.person_name}</span>
              <button className="btn btn-sm btn-icon" onClick={() => setPerson(null)}><Icon path={icons.x} size={13} /></button>
            </div>
            <div className="modal-body">
              <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12 }}>
                <div style={{ width: 56, height: 56, borderRadius: 6, overflow: "hidden", background: "var(--surface)", border: "1px solid var(--border)", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {ensureImg(person.snapshot)
                    ? <img src={ensureImg(person.snapshot)} style={{ width: "100%", height: "100%", objectFit: "cover" }} onError={e => e.target.style.display = "none"} />
                    : <Icon path={icons.humans} size={22} color="var(--text3)" />}
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>{person.person_name === "Unknown" ? "Unknown person" : person.person_name}</div>
                  <div style={{ fontFamily: "monospace", fontSize: 11, color: person.global_id.startsWith("PERSON") ? "var(--green)" : "var(--orange)" }}>{person.global_id}</div>
                </div>
              </div>

              <div style={{ fontSize: 11.5, fontWeight: 600, marginBottom: 5 }}>🏠 Rooms inside now (with head count):</div>
              {personInfo.insideRooms.length === 0 && <div style={{ fontSize: 11, color: "var(--text3)", marginBottom: 8 }}>Not inside any room</div>}
              {personInfo.insideRooms.map(r => (
                <div key={r.room_id} style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, padding: "4px 8px", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 6, marginBottom: 4 }}>
                  <span>🏠 {r.room_id}</span>
                  <span style={{ fontWeight: 700, color: "var(--green)" }}>head count: {r.inside_count}</span>
                </div>
              ))}

              <div style={{ fontSize: 11.5, fontWeight: 600, margin: "10px 0 5px" }}>🕒 Recent entries / sightings ({personInfo.seen.length}):</div>
              <div style={{ maxHeight: 180, overflowY: "auto" }}>
                {personInfo.seen.map((m, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, padding: "3px 0", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ fontFamily: "monospace", color: "var(--text2)" }}>{(m.timestamp || "").slice(11, 19)}</span>
                    <span>{m.camera_id}</span>
                  </div>
                ))}
                {personInfo.seen.length === 0 && <div style={{ fontSize: 10.5, color: "var(--text3)" }}>No sightings recorded yet</div>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function LiveFeedModal({ onClose }) {
  const [ksEvents, setKsEvents]   = useState([]);
  const [ourEvents, setOurEvents] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [hours, setHours]         = useState(1);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [ksError, setKsError]     = useState("");
  const [countdown, setCountdown]     = useState(60);
  const [filterType, setFilterType]   = useState("known"); // "all" | "known" | "unknown"

  const ensureLocalDataUrl = (img) => {
    if (!img) return null;
    if (img.startsWith("data:") || img.startsWith("http")) return img;
    return `data:image/jpeg;base64,${img}`;
  };

  const fetchFeed = useCallback(() => {
    setLoading(true);
    // Hit KloudSpot API live via backend, get fresh data
    fetchAPI(`/api/v1/comparison/live-feed?hours=${hours}`).then(res => {
      if (res && res.success) {
        setKsEvents(res.kloudspot_events || []);
        setOurEvents(res.our_events     || []);
        setKsError(res.ks_error || "");
        setLastUpdated(new Date().toLocaleTimeString());
        setCountdown(60);
      }
      setLoading(false);
    });
  }, [hours]);

  // Poll every 60 seconds (KloudSpot API is hit server-side each time)
  useEffect(() => {
    fetchFeed();
    const poll = setInterval(fetchFeed, 60000);
    return () => clearInterval(poll);
  }, [fetchFeed]);

  // Countdown ticker
  useEffect(() => {
    const tick = setInterval(() => setCountdown(c => Math.max(0, c - 1)), 1000);
    return () => clearInterval(tick);
  }, [lastUpdated]);

  const filteredKs = ksEvents.filter(ev => {
    const name = ev.full_name || ((ev.first_name || "") + " " + (ev.last_name || "")).trim();
    const isKnown = name && name !== "Unknown" && name.trim() !== "";
    if (filterType === "known")   return isKnown;
    if (filterType === "unknown") return !isKnown;
    return true;
  });

  const filteredOur = ourEvents.filter(ev => {
    if (filterType === "known")   return !!ev.matched;
    if (filterType === "unknown") return !ev.matched;
    return true;
  });

  return (
    <div className="modal-overlay" style={{zIndex: 9999}}>
      <div style={{background:"var(--surface)", border:"1px solid var(--border)", borderRadius:8,
        maxWidth:1020, width:"95%", height:"88vh", display:"flex", flexDirection:"column", overflow:"hidden"}}>

        {/* Header */}
        <div style={{display:"flex", justifyContent:"space-between", alignItems:"center",
          padding:"12px 18px", borderBottom:"1px solid var(--border)", flexShrink:0}}>
          <div style={{display:"flex", alignItems:"center", gap:10}}>
            <span style={{color:"#ef4444", fontSize:16}}>🔴</span>
            <span style={{fontSize:14, fontWeight:600}}>Live Feed Comparison</span>
            {loading && <span style={{fontSize:11, color:"var(--orange)"}}>Fetching...</span>}
            {!loading && lastUpdated && (
              <span style={{fontSize:11, color:"var(--text2)"}}>
                Updated {lastUpdated} — next in <b style={{color: countdown<=10?"var(--red)":"var(--green)"}}>{countdown}s</b>
              </span>
            )}
            {ksError && <span style={{fontSize:11, color:"var(--red)"}}>⚠ {ksError}</span>}
          </div>
          <div style={{display:"flex", gap:8, alignItems:"center"}}>
            <span style={{fontSize:11, color:"var(--text2)"}}>Filter:</span>
            <button className={`btn btn-sm ${filterType==="all"?"btn-primary":""}`} style={{padding:"3px 9px",fontSize:11}} onClick={()=>setFilterType("all")}>All</button>
            <button className={`btn btn-sm ${filterType==="known"?"btn-primary":""}`} style={{padding:"3px 9px",fontSize:11}} onClick={()=>setFilterType("known")}>Known</button>
            <button className={`btn btn-sm ${filterType==="unknown"?"btn-primary":""}`} style={{padding:"3px 9px",fontSize:11}} onClick={()=>setFilterType("unknown")}>Unknown</button>
            <span style={{width:1, height:16, background:"var(--border)", margin:"0 4px"}}/>
            {/* Window selector */}
            <select value={hours} onChange={e=>setHours(Number(e.target.value))} style={{width:130, fontSize:11}}>
              <option value={0.5}>Last 30 min</option>
              <option value={1}>Last 1 hour</option>
              <option value={3}>Last 3 hours</option>
              <option value={6}>Last 6 hours</option>
              <option value={24}>Last 24 hours</option>
            </select>
            <button className="btn btn-sm btn-primary" onClick={fetchFeed} disabled={loading}>
              <Icon path={icons.refresh} size={12}/> {loading?"Loading...":"Refresh Now"}
            </button>
            <button className="btn btn-sm" onClick={onClose}>Close</button>
          </div>
        </div>

        {/* Counts bar */}
        <div style={{display:"flex", gap:24, padding:"8px 18px", background:"var(--surface2)",
          borderBottom:"1px solid var(--border)", fontSize:12, flexShrink:0}}>
          <span>🟠 <b style={{color:"#f97316"}}>{filteredKs.length}</b> KloudSpot events</span>
          <span>🔵 <b style={{color:"#3b82f6"}}>{filteredOur.length}</b> Our FRS events</span>
        </div>

        {/* Two-column feed */}
        <div style={{display:"flex", gap:0, flex:1, overflow:"hidden"}}>

          {/* KloudSpot column */}
          <div style={{flex:1, display:"flex", flexDirection:"column", borderRight:"1px solid var(--border)", overflow:"hidden"}}>
            <div style={{padding:"8px 14px", borderBottom:"1px solid var(--border)", fontSize:12,
              fontWeight:600, color:"#f97316", flexShrink:0}}>
              KloudSpot Data ({filteredKs.length})
            </div>
            <div style={{overflowY:"auto", flex:1, padding:"8px 10px"}}>
              {filteredKs.length === 0 && !loading && (
                <div style={{textAlign:"center", padding:30, color:"var(--text3)", fontSize:12}}>
                  No KloudSpot events yet.<br/>Click Refresh Now to fetch.
                </div>
              )}
              {filteredKs.map((ev, i) => {
                const img = ev.image_data_url;
                const isEntry = (ev.direction||"").toLowerCase().includes("entry") ||
                                (ev.direction||"").toLowerCase() === "in";
                return (
                  <div key={i} style={{padding:"8px 10px", background:"var(--bg)",
                    border:"1px solid var(--border)", borderRadius:6, marginBottom:6,
                    display:"flex", gap:10, alignItems:"center"}}>
                    <div style={{width:46, height:46, borderRadius:4, background:"var(--surface)",
                      overflow:"hidden", flexShrink:0, display:"flex", alignItems:"center",
                      justifyContent:"center", border:"1px solid var(--border)"}}>
                      {img
                        ? <img src={img} alt="" style={{width:"100%",height:"100%",objectFit:"cover"}}
                            onError={e=>e.target.style.display="none"}/>
                        : <Icon path={icons.enroll} size={18} color="var(--text3)"/>}
                    </div>
                    <div style={{flex:1, minWidth:0}}>
                      <div style={{fontSize:10, color:"var(--text3)"}}>{ev.timestamp_iso||ev.date||""}</div>
                      <div style={{fontWeight:600, fontSize:13, color:"var(--text)", overflow:"hidden",
                        textOverflow:"ellipsis", whiteSpace:"nowrap"}}>
                        {ev.full_name || ((ev.first_name||"")+" "+(ev.last_name||"")).trim() || "Unknown"}
                      </div>
                      <div style={{fontSize:11, marginTop:2, display:"flex", justifyContent:"space-between"}}>
                        <span style={{color:"var(--text2)"}}>Loc: {ev.location_type||"zone"}</span>
                        <span style={{fontWeight:700, color: isEntry ? "var(--green)" : "var(--red)"}}>
                          {isEntry ? "ENTRY" : "EXIT"}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Our FRS column */}
          <div style={{flex:1, display:"flex", flexDirection:"column", overflow:"hidden"}}>
            <div style={{padding:"8px 14px", borderBottom:"1px solid var(--border)", fontSize:12,
              fontWeight:600, color:"#3b82f6", flexShrink:0}}>
              Our FRS Data ({filteredOur.length})
            </div>
            <div style={{overflowY:"auto", flex:1, padding:"8px 10px"}}>
              {filteredOur.length === 0 && !loading && (
                <div style={{textAlign:"center", padding:30, color:"var(--text3)", fontSize:12}}>
                  No FRS events for this time window.
                </div>
              )}
              {filteredOur.map((ev, i) => {
                const img = `/api/v1/events/${ev.id}/snapshot`;
                const conf = ev.confidence || 0;
                const confColor = conf >= 0.5 ? "var(--green)" : conf >= 0.37 ? "var(--orange)" : "var(--red)";
                return (
                  <div key={i} style={{padding:"8px 10px", background:"var(--bg)",
                    border:"1px solid var(--border)", borderRadius:6, marginBottom:6,
                    display:"flex", gap:10, alignItems:"center"}}>
                    <div style={{width:46, height:46, borderRadius:4, background:"var(--surface)",
                      overflow:"hidden", flexShrink:0, display:"flex", alignItems:"center",
                      justifyContent:"center", border:"1px solid var(--border)"}}>
                      {img
                        ? <img src={img} alt="" style={{width:"100%",height:"100%",objectFit:"cover"}}
                            onError={e=>e.target.style.display="none"}/>
                        : <Icon path={icons.enroll} size={18} color="var(--text3)"/>}
                    </div>
                    <div style={{flex:1, minWidth:0}}>
                      <div style={{fontSize:10, color:"var(--text3)"}}>{(ev.timestamp||"").slice(0,19).replace("T"," ")}</div>
                      <div style={{fontWeight:600, fontSize:13, color:"var(--text)", overflow:"hidden",
                        textOverflow:"ellipsis", whiteSpace:"nowrap"}}>
                        {ev.matched ? ev.person_name : <span style={{color:"var(--text2)"}}>Unknown Person</span>}
                      </div>
                      <div style={{fontSize:11, marginTop:2, display:"flex", justifyContent:"space-between"}}>
                        <span style={{color:"var(--text2)"}}>Cam: {ev.camera_id||"—"}</span>
                        <span style={{color: confColor, fontWeight:600}}>
                          Acc: {(conf*100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

// ─── KLOUDSPOT VS OUR FRS COMPARISON DASHBOARD ──────────────────
function ComparisonPage() {
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().slice(0, 10));
  const [tolerance, setTolerance] = useState(60);
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState([]);
  const [totalEvents, setTotalEvents] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [syncHours, setSyncHours] = useState(24);
  const [syncing, setSyncing] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [operationMsg, setOperationMsg] = useState(null);
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState(null);
  const [showConfig, setShowConfig] = useState(false);
  const [showLiveFeedModal, setShowLiveFeedModal] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState("cameras"); // "cameras" | "persons" | "attendance"
  const [activeMainTab, setActiveMainTab] = useState("events"); // "events" | "persons"
  const [configForm, setConfigForm] = useState({
    auth_url: "",
    analytics_url: "",
    app_id: "",
    secret_key: "",
    organisation_id: "",
    tolerance_seconds: 60
  });

  const loadStats = useCallback(() => {
    setLoading(true);
    fetchAPI(`/api/v1/comparison/stats?date=${selectedDate}&tolerance_seconds=${tolerance}`).then(r => {
      if (r) {
        setStats(r);
      }
      setLoading(false);
    });
  }, [selectedDate, tolerance]);

  const loadEvents = useCallback(() => {
    fetchAPI(`/api/v1/comparison/events?status=${statusFilter}&date=${selectedDate}&search=${encodeURIComponent(search)}&page=${page}&page_size=20&tolerance_seconds=${tolerance}`).then(r => {
      if (r) {
        setEvents(r.events || []);
        setTotalEvents(r.total || 0);
      }
    });
  }, [selectedDate, tolerance, statusFilter, search, page]);

  const loadConfig = useCallback(() => {
    fetchAPI("/api/v1/comparison/config").then(r => {
      if (r) {
        setConfig(r);
        setConfigForm({
          auth_url: r.auth_url || "",
          analytics_url: r.analytics_url || "",
          app_id: r.app_id || "",
          secret_key: "", // Write-only
          organisation_id: r.organisation_id || "",
          tolerance_seconds: r.tolerance_seconds || 60
        });
      }
    });
  }, []);

  useEffect(() => {
    loadStats();
    loadConfig();
  }, [loadStats, loadConfig]);

  useEffect(() => {
    setPage(1); // Reset page on filter change
  }, [selectedDate, tolerance, statusFilter, search]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  const handleSync = async () => {
    setSyncing(true);
    setOperationMsg(null);
    const res = await fetchAPI("/api/v1/comparison/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ last_hours: parseFloat(syncHours), add_image: true })
    });
    setSyncing(false);
    if (res && res.success) {
      setOperationMsg(`✓ Synced successfully! Synced ${res.saved_count} new events from Kloudspot.`);
      loadStats();
      loadEvents();
      setTimeout(() => setOperationMsg(null), 5000);
    } else {
      setOperationMsg(`❌ Sync failed: ${res?.message || "Verify Kloudspot settings / connection URL."}`);
    }
  };

  const handleSeed = async () => {
    setSeeding(true);
    setOperationMsg(null);
    const res = await fetchAPI("/api/v1/comparison/seed-sample", { method: "POST" });
    setSeeding(false);
    if (res && res.success) {
      setOperationMsg(`✓ Mock comparison data generated: seeded ${res.kloudspot_seeded} Kloudspot events and ${res.our_seeded} Our FRS events for today.`);
      loadStats();
      loadEvents();
      setTimeout(() => setOperationMsg(null), 5000);
    } else {
      setOperationMsg("❌ Failed to seed comparison data.");
    }
  };

  const handleClear = async () => {
    if (!window.confirm("Clear synced Kloudspot events? Local FRS events are not affected.")) return;
    setClearing(true);
    setOperationMsg(null);
    const res = await fetchAPI("/api/v1/comparison/clear-kloudspot", { method: "DELETE" });
    setClearing(false);
    if (res && res.success) {
      setOperationMsg("✓ Kloudspot events database cleared successfully.");
      loadStats();
      loadEvents();
      setTimeout(() => setOperationMsg(null), 5000);
    } else {
      setOperationMsg("❌ Failed to clear events.");
    }
  };

  const handleSaveConfig = async () => {
    const res = await fetchAPI("/api/v1/comparison/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(configForm)
    });
    if (res && res.success) {
      alert("Kloudspot API settings updated successfully!");
      setShowConfig(false);
      loadConfig();
    } else {
      alert("Failed to update settings.");
    }
  };

  const ensureDataUrl = (img) => {
    if (!img) return null;
    if (img.startsWith("data:") || img.startsWith("http") || img.startsWith("/")) return img;
    return `data:image/jpeg;base64,${img}`;
  };

  // Safe helper to extract nested data
  const summary = stats?.summary || {};
  const ks = summary.kloudspot || {};
  const our = summary.our_frs || {};
  const checkinStats = summary.checkin_stats || {};

  // Accuracy chart values
  const metricsList = [
    { label: "Accuracy", ks: ks.accuracy || 0, our: our.accuracy || 0 },
    { label: "Precision", ks: ks.precision || 0, our: our.precision || 0 },
    { label: "Recall", ks: ks.recall || 0, our: our.recall || 0 },
    { label: "F1 Score", ks: ks.f1_score || 0, our: our.f1_score || 0 },
  ];

  return (
    <div>
      {/* Configuration modal */}
      {showConfig && (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && setShowConfig(false)}>
          <div className="modal" style={{ maxWidth: 520 }}>
            <div className="modal-header">
              <span className="modal-title">Kloudspot API Configuration Settings</span>
              <button className="btn btn-sm btn-icon" onClick={() => setShowConfig(false)}><Icon path={icons.x} size={13} /></button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Auth Token Login Endpoint</label>
                <input type="text" value={configForm.auth_url} onChange={e => setConfigForm({ ...configForm, auth_url: e.target.value })} placeholder="https://3c.zdotapps.in/advanced/api/v1/auth/login" />
              </div>
              <div className="form-group">
                <label className="form-label">Entry/Exit Analytics API URL</label>
                <input type="text" value={configForm.analytics_url} onChange={e => setConfigForm({ ...configForm, analytics_url: e.target.value })} placeholder="https://3c.zdotapps.in/advanced/api/v1/camera/analytics/entryExit" />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">API App ID</label>
                  <input type="text" value={configForm.app_id} onChange={e => setConfigForm({ ...configForm, app_id: e.target.value })} placeholder="69b25f..." />
                </div>
                <div className="form-group">
                  <label className="form-label">Secret Key (Hidden)</label>
                  <input type="password" value={configForm.secret_key} onChange={e => setConfigForm({ ...configForm, secret_key: e.target.value })} placeholder="Enter secret key to update..." />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Organization ID</label>
                  <input type="text" value={configForm.organisation_id} onChange={e => setConfigForm({ ...configForm, organisation_id: e.target.value })} placeholder="1" />
                </div>
                <div className="form-group">
                  <label className="form-label">Tolerance Window (seconds)</label>
                  <input type="number" value={configForm.tolerance_seconds} onChange={e => setConfigForm({ ...configForm, tolerance_seconds: parseInt(e.target.value) || 60 })} min="5" max="3600" />
                </div>
              </div>
              <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 8 }}>
                ⚠️ <b>Notice:</b> Credentials and locations are populated from local configuration. Make sure target cameras are available and streaming on the expected RTSP urls.
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={() => setShowConfig(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSaveConfig}>Save API Configuration</button>
            </div>
          </div>
        </div>
      )}

      {/* Operation Status Banner */}
      {operationMsg && (
        <div style={{
          padding: "10px 14px", borderRadius: 6, marginBottom: 14, fontSize: 12.5, fontWeight: 500,
          background: operationMsg.startsWith("✓") ? "rgba(61,186,110,0.15)" : "rgba(224,82,82,0.15)",
          border: operationMsg.startsWith("✓") ? "1px solid rgba(61,186,110,0.4)" : "1px solid rgba(224,82,82,0.4)",
          color: operationMsg.startsWith("✓") ? "var(--green)" : "var(--red)"
        }}>
          {operationMsg}
        </div>
      )}

      {/* Date Filter & Sync Panel Row */}
      <div className="table-wrap" style={{ padding: 14, marginBottom: 16 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center" }}>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 11, color: "var(--text2)", textTransform: "uppercase", letterSpacing: ".06em" }}>Date</span>
            <input type="date" value={selectedDate} onChange={e => setSelectedDate(e.target.value)} style={{ width: 140 }} />
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 11, color: "var(--text2)", textTransform: "uppercase", letterSpacing: ".06em" }}>Time Jitter Window</span>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <input type="number" value={tolerance} onChange={e => setTolerance(parseInt(e.target.value) || 10)} style={{ width: 70 }} min="5" max="300" />
              <span style={{ fontSize: 11, color: "var(--text3)" }}>seconds</span>
            </div>
          </div>

          <div style={{ borderLeft: "1px solid var(--border)", height: 24, margin: "0 4px" }} className="desktop-only" />

          {/* Sync Operations */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button className="btn" onClick={() => setShowLiveFeedModal(true)} style={{ background: "rgba(239, 68, 68, 0.1)", color: "#ef4444", borderColor: "rgba(239, 68, 68, 0.3)" }}>
              🔴 Live Feed
            </button>
            <select value={syncHours} onChange={e => setSyncHours(Number(e.target.value))} style={{ width: 130 }}>
              <option value={1}>Last 1 hour</option>
              <option value={6}>Last 6 hours</option>
              <option value={24}>Last 24 hours</option>
              <option value={72}>Last 3 days</option>
              <option value={168}>Last 7 days</option>
            </select>
            <button className="btn btn-primary" onClick={handleSync} disabled={syncing}>
              {syncing ? "Syncing..." : "⚡ Sync Kloudspot API"}
            </button>
          </div>

          {/* Fallback Seeding & Controls */}
          <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
            <button className="btn btn-sm" onClick={handleSeed} disabled={seeding} title="Seed mock events for direct testing">
              {seeding ? "Generating..." : "🧪 Seed Mock Data"}
            </button>
            <button className="btn btn-sm" onClick={handleClear} disabled={clearing} style={{ color: "var(--red)", borderColor: "rgba(224,82,82,0.3)" }}>
              🗑️ Clear Cache
            </button>
            <button className="btn btn-sm btn-icon" onClick={() => setShowConfig(true)} title="API Settings">⚙️ Settings</button>
            <button className="btn btn-sm" onClick={loadStats}><Icon path={icons.refresh} size={12} /></button>
          </div>

        </div>
      </div>

      {showLiveFeedModal && <LiveFeedModal onClose={() => setShowLiveFeedModal(false)} />}

      {/* Main Stats Widgets */}
      <div className="stats-row">

        {/* Expected Incidents */}
        <div className="stat-box">
          <div className="stat-box-label">Ground Truth Sights</div>
          <div className="stat-box-value" style={{ color: "var(--accent)" }}>{summary.total_ground_truth_events ?? 0}</div>
          <div className="stat-box-sub">Total actual events detected</div>
        </div>

        {/* Common Sighted */}
        <div className="stat-box">
          <div className="stat-box-label">Common People</div>
          <div className="stat-box-value" style={{ color: "var(--green)" }}>{summary.common_people_count ?? 0}</div>
          <div className="stat-box-sub">Sighted in both models</div>
        </div>

        {/* Kloudspot Performance */}
        <div className="stat-box compare-card kloudspot" style={{ paddingTop: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
            <div className="stat-box-label" style={{ fontWeight: 700, color: "#f97316" }}>KOLDSPOT FRS</div>
            <span className="badge badge-orange" style={{ fontSize: 9.5 }}>Standard Model</span>
          </div>
          <div className="stat-box-value" style={{ fontSize: 24, color: "#f97316" }}>{ks.accuracy ? `${ks.accuracy.toFixed(1)}%` : "0.0%"}</div>
          <div style={{ marginTop: 6, display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2px 8px", fontSize: 10.5, color: "var(--text2)" }}>
            <div>Precision: <b>{ks.precision ? `${ks.precision.toFixed(1)}%` : "—"}</b></div>
            <div>Recall: <b>{ks.recall ? `${ks.recall.toFixed(1)}%` : "—"}</b></div>
            <div>F1 Score: <b>{ks.f1_score ? `${ks.f1_score.toFixed(1)}%` : "—"}</b></div>
            <div>Duplicates: <b>{ks.duplicates ?? 0}</b></div>
          </div>
        </div>

        {/* Our FRS Performance */}
        <div className="stat-box compare-card our-frs" style={{ paddingTop: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
            <div className="stat-box-label" style={{ fontWeight: 700, color: "#3b82f6" }}>OUR LOCAL FRS</div>
            <span className="badge badge-blue" style={{ fontSize: 9.5 }}>Active Model</span>
          </div>
          <div className="stat-box-value" style={{ fontSize: 24, color: "#3b82f6" }}>{our.accuracy ? `${our.accuracy.toFixed(1)}%` : "0.0%"}</div>
          <div style={{ marginTop: 6, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "2px 8px", fontSize: 10.5, color: "var(--text2)" }}>
            <div>Precision: <b>{our.precision ? `${our.precision.toFixed(1)}%` : "—"}</b></div>
            <div>Recall: <b>{our.recall ? `${our.recall.toFixed(1)}%` : "—"}</b></div>
            <div>F1 Score: <b>{our.f1_score ? `${our.f1_score.toFixed(1)}%` : "—"}</b></div>
            <div style={{ gridColumn: "span 2" }}>Avg Confidence: <b style={{ color: "var(--green)" }}>{our.avg_confidence ? `${(our.avg_confidence * 100).toFixed(0)}%` : "—"}</b></div>
          </div>
        </div>

      </div>

      {/* ── MAIN CONTENT TABS ─────────────────────────────── */}
      <div style={{display:"flex", borderBottom:"1px solid var(--border)", marginBottom:16, background:"var(--surface2)", borderRadius:"6px 6px 0 0"}}>
        <button className={`tab-btn ${activeMainTab==="persons"?"active":""}`} style={{fontSize:13,padding:"10px 20px"}}
          onClick={()=>setActiveMainTab("persons")}>
          👥 Person Detection Report
        </button>
        <button className={`tab-btn ${activeMainTab==="events"?"active":""}`} style={{fontSize:13,padding:"10px 20px"}}
          onClick={()=>setActiveMainTab("events")}>
          📋 Event Stream Comparison
        </button>
      </div>

      {/* ══ TAB 1: PERSON DETECTION REPORT ══════════════════ */}
      {activeMainTab === "persons" && (() => {
        const counts = personReport?.counts || {};
        const allPersons = personReport?.persons || [];
        const filtered = allPersons.filter(p => {
          if (personFilter !== "all" && p.status !== personFilter) return false;
          if (personSearch) {
            const q = personSearch.toLowerCase();
            if (!p.person_name.toLowerCase().includes(q) &&
                !p.ks_name.toLowerCase().includes(q) &&
                !(p.company||"").toLowerCase().includes(q)) return false;
          }
          return true;
        });

        const statusLabel = { both:"✅ Both", our_only:"🔵 Our AI Only", ks_only:"🟠 KS Only", neither:"⬜ Neither" };
        const statusColor = { both:"var(--green)", our_only:"var(--accent)", ks_only:"var(--orange)", neither:"var(--text3)" };
        const statusBg   = { both:"rgba(61,186,110,.15)", our_only:"rgba(74,158,255,.15)", ks_only:"rgba(232,148,58,.15)", neither:"var(--surface2)" };

        return (
          <div>
            {/* 4 stat cards */}
            <div className="stats-row" style={{marginBottom:14}}>
              {[
                {key:"both",    label:"Both Detected",      sub:"Our AI + KloudSpot",      color:"var(--green)",   icon:"✅"},
                {key:"our_only",label:"Our AI Only",         sub:"KloudSpot missed them",   color:"var(--accent)",  icon:"🔵"},
                {key:"ks_only", label:"KloudSpot Only",      sub:"Our AI missed them",       color:"var(--orange)",  icon:"🟠"},
                {key:"neither", label:"Not Detected Today",  sub:"Absent from both",         color:"var(--text2)",   icon:"⬜"},
              ].map(c => (
                <div key={c.key} className="stat-box" style={{cursor:"pointer", borderTop:`3px solid ${c.color}`,
                  background: personFilter===c.key ? "rgba(255,255,255,0.04)" : "var(--surface)"}}
                  onClick={()=>setPersonFilter(personFilter===c.key?"all":c.key)}>
                  <div className="stat-box-label">{c.icon} {c.label}</div>
                  <div className="stat-box-value" style={{color:c.color}}>{counts[c.key]??0}</div>
                  <div className="stat-box-sub">{c.sub}</div>
                </div>
              ))}
            </div>

            {/* Filter bar */}
            <div style={{display:"flex", gap:10, alignItems:"center", marginBottom:10, flexWrap:"wrap"}}>
              <div className="search-box">
                <span className="search-icon"><Icon path={icons.search} size={13}/></span>
                <input type="text" placeholder="Search person name..." value={personSearch}
                  onChange={e=>setPersonSearch(e.target.value)} style={{width:220}}/>
              </div>
              <div style={{display:"flex", gap:6}}>
                {["all","both","our_only","ks_only","neither"].map(f=>(
                  <button key={f} className={`btn btn-sm ${personFilter===f?"btn-primary":""}`}
                    onClick={()=>setPersonFilter(f)}>
                    {f==="all"?"All":statusLabel[f]}
                  </button>
                ))}
              </div>
              <span style={{marginLeft:"auto",fontSize:11,color:"var(--text2)"}}>
                Showing <b>{filtered.length}</b> of <b>{allPersons.length}</b> persons
              </span>
              <button className="btn btn-sm" onClick={loadPersonReport}><Icon path={icons.refresh} size={12}/></button>
            </div>

            {/* Person table */}
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th style={{width:44}}>Photo</th>
                    <th>Our DB Person</th>
                    <th>Company</th>
                    <th>Status</th>
                    <th style={{textAlign:"center"}}>Our AI<br/><span style={{fontWeight:400,textTransform:"none",fontSize:10}}>detections</span></th>
                    <th style={{textAlign:"center"}}>AI Conf</th>
                    <th style={{textAlign:"center"}}>KloudSpot<br/><span style={{fontWeight:400,textTransform:"none",fontSize:10}}>events</span></th>
                    <th>KloudSpot Name</th>
                    <th style={{width:80}}>Entity ID</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 && (
                    <tr><td colSpan={9}><div className="empty">
                      {personReport ? "No persons match the filter." : "Loading..."}
                    </div></td></tr>
                  )}
                  {filtered.map((p,i) => (
                    <tr key={i}>
                      {/* Photo */}
                      <td>
                        <div className="avatar">
                          {(p.our_snapshot||p.photo)
                            ? <img src={p.our_snapshot||p.photo} alt="" style={{width:"100%",height:"100%",objectFit:"cover"}}
                                onError={e=>e.target.style.display="none"}/>
                            : <Icon path={icons.humans} size={14} color="var(--text3)"/>}
                        </div>
                      </td>
                      {/* Name */}
                      <td>
                        <div style={{fontWeight:500}}>{p.person_name}</div>
                        <div style={{fontSize:10,color:"var(--text3)",fontFamily:"monospace"}}>{fmtId(p.person_id)}</div>
                      </td>
                      {/* Company */}
                      <td><span className="badge badge-grey" style={{fontSize:10}}>{p.company||"—"}</span></td>
                      {/* Status badge */}
                      <td>
                        <span style={{
                          display:"inline-flex", alignItems:"center", gap:4,
                          padding:"3px 10px", borderRadius:12, fontSize:11, fontWeight:600,
                          background: statusBg[p.status], color: statusColor[p.status]
                        }}>
                          {p.status==="both"     && "✅ Both Detected"}
                          {p.status==="our_only" && "🔵 Our AI Only"}
                          {p.status==="ks_only"  && "🟠 KS Only"}
                          {p.status==="neither"  && "⬜ Neither"}
                        </span>
                      </td>
                      {/* Our AI count */}
                      <td style={{textAlign:"center"}}>
                        {p.our_count > 0
                          ? <span style={{color:"var(--green)",fontWeight:600}}>{p.our_count}</span>
                          : <span style={{color:"var(--text3)"}}>—</span>}
                      </td>
                      {/* AI confidence */}
                      <td style={{textAlign:"center",fontFamily:"monospace",fontSize:11}}>
                        {p.our_conf > 0
                          ? <span style={{color: p.our_conf>=0.5?"var(--green)":p.our_conf>=0.37?"var(--orange)":"var(--red)"}}>
                              {(p.our_conf*100).toFixed(0)}%
                            </span>
                          : <span style={{color:"var(--text3)"}}>—</span>}
                      </td>
                      {/* KS count */}
                      <td style={{textAlign:"center"}}>
                        {p.ks_count > 0
                          ? <span style={{color:"var(--orange)",fontWeight:600}}>{p.ks_count}</span>
                          : <span style={{color:"var(--text3)"}}>—</span>}
                      </td>
                      {/* KS name */}
                      <td style={{fontSize:11,color:"var(--text2)"}}>
                        {p.ks_name || <span style={{color:"var(--text3)",fontSize:10}}>not in KloudSpot</span>}
                      </td>
                      {/* Entity ID */}
                      <td style={{fontFamily:"monospace",fontSize:9,color:"var(--text3)"}}>
                        {p.ks_entity_id
                          ? <span title={p.ks_entity_id}>{p.ks_entity_id.slice(-8)}</span>
                          : <span style={{color:"var(--red)",fontSize:10}}>no map</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })()}

      {/* ══ TAB 2: EVENT STREAM COMPARISON ══════════════════ */}
      {activeMainTab === "events" && (
        <>
          {/* Stats summary row */}
          <div className="stats-row" style={{marginBottom:14}}>
            <div className="stat-box"><div className="stat-box-label">Ground Truth</div>
              <div className="stat-box-value" style={{color:"var(--accent)"}}>{summary.total_ground_truth_events??0}</div>
              <div className="stat-box-sub">Total events</div></div>
            <div className="stat-box"><div className="stat-box-label">Common People</div>
              <div className="stat-box-value" style={{color:"var(--green)"}}>{summary.common_people_count??0}</div>
              <div className="stat-box-sub">Sighted in both</div></div>
            <div className="stat-box compare-card kloudspot" style={{paddingTop:12}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:4}}>
                <div className="stat-box-label" style={{fontWeight:700,color:"#f97316"}}>KLOUDSPOT FRS</div>
                <span className="badge badge-orange" style={{fontSize:9.5}}>Standard Model</span>
              </div>
              <div className="stat-box-value" style={{fontSize:24,color:"#f97316"}}>{ks.accuracy?`${ks.accuracy.toFixed(1)}%`:"0.0%"}</div>
              <div style={{marginTop:6,display:"grid",gridTemplateColumns:"1fr 1fr",gap:"2px 8px",fontSize:10.5,color:"var(--text2)"}}>
                <div>Precision: <b>{ks.precision?`${ks.precision.toFixed(1)}%`:"—"}</b></div>
                <div>Recall: <b>{ks.recall?`${ks.recall.toFixed(1)}%`:"—"}</b></div>
                <div>F1: <b>{ks.f1_score?`${ks.f1_score.toFixed(1)}%`:"—"}</b></div>
                <div>Dupes: <b>{ks.duplicates??0}</b></div>
              </div>
            </div>
            <div className="stat-box compare-card our-frs" style={{paddingTop:12}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:4}}>
                <div className="stat-box-label" style={{fontWeight:700,color:"#3b82f6"}}>OUR LOCAL FRS</div>
                <span className="badge badge-blue" style={{fontSize:9.5}}>Active Model</span>
              </div>
              <div className="stat-box-value" style={{fontSize:24,color:"#3b82f6"}}>{our.accuracy?`${our.accuracy.toFixed(1)}%`:"0.0%"}</div>
              <div style={{marginTop:6,display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:"2px 8px",fontSize:10.5,color:"var(--text2)"}}>
                <div>Precision: <b>{our.precision?`${our.precision.toFixed(1)}%`:"—"}</b></div>
                <div>Recall: <b>{our.recall?`${our.recall.toFixed(1)}%`:"—"}</b></div>
                <div>F1: <b>{our.f1_score?`${our.f1_score.toFixed(1)}%`:"—"}</b></div>
                <div style={{gridColumn:"span 2"}}>Avg Conf: <b style={{color:"var(--green)"}}>{our.avg_confidence?`${(our.avg_confidence*100).toFixed(0)}%`:"—"}</b></div>
              </div>
            </div>
          </div>

      {loading ? (
        <div style={{textAlign:"center",padding:40,color:"var(--text2)"}}>Computing benchmark...</div>
      ) : (
        <>
          {/* Side-by-Side SVG Graph block & Breakdown statistics */}
          <div style={{ display: "grid", gridTemplateColumns: "3fr 4fr", gap: 16, marginBottom: 16 }} className="two-col-config">

            {/* Visual SVG Comparison Chart */}
            <div className="table-wrap" style={{ padding: 16 }}>
              <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 14, color: "var(--text)", display: "flex", alignItems: "center", gap: 6 }}>
                <Icon path={icons.dashboard} size={14} color="var(--accent)" />
                Side-by-Side Metrics Benchmarking
              </div>
              <div style={{ height: 190, position: "relative", display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "10px 0" }}>
                {metricsList.map((m, idx) => {
                  return (
                    <div key={idx} style={{ marginBottom: 10 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, color: "var(--text2)", marginBottom: 3 }}>
                        <span>{m.label}</span>
                        <span>
                          <b style={{ color: "#f97316" }}>{m.ks.toFixed(1)}%</b> vs <b style={{ color: "#3b82f6" }}>{m.our.toFixed(1)}%</b>
                        </span>
                      </div>
                      {/* Double Progress Bar */}
                      <div style={{ height: 10, display: "flex", flexDirection: "column", gap: 2, background: "rgba(255,255,255,0.04)", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{ height: 4, width: `${m.ks}%`, background: "#f97316", borderRadius: 2, transition: "width 0.3s ease" }} />
                        <div style={{ height: 4, width: `${m.our}%`, background: "#3b82f6", borderRadius: 2, transition: "width 0.3s ease" }} />
                      </div>
                    </div>
                  );
                })}
              </div>
              <div style={{ display: "flex", gap: 12, justifyContent: "center", fontSize: 10, color: "var(--text3)", borderTop: "1px solid var(--border)", paddingTop: 10 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ width: 8, height: 8, background: "#f97316", borderRadius: 2 }} /> Kloudspot
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ width: 8, height: 8, background: "#3b82f6", borderRadius: 2 }} /> Our Local FRS
                </span>
              </div>
            </div>

            {/* Breakdowns & Segmentations Tabbed Panel */}
            <div className="table-wrap">
              <div style={{ display: "flex", borderBottom: "1px solid var(--border)", background: "var(--surface2)" }}>
                <button className={`tab-btn ${activeSubTab === "cameras" ? "active" : ""}`} onClick={() => setActiveSubTab("cameras")}>
                  📹 Camera Breakdowns
                </button>
                <button className={`tab-btn ${activeSubTab === "persons" ? "active" : ""}`} onClick={() => setActiveSubTab("persons")}>
                  👥 Ground Truth People ({stats?.person_stats?.length || 0})
                </button>
                <button className={`tab-btn ${activeSubTab === "attendance" ? "active" : ""}`} onClick={() => setActiveSubTab("attendance")}>
                  📅 Check-in Metrics
                </button>
              </div>

              <div style={{ padding: 8, maxHeight: 220, overflowY: "auto" }}>

                {/* 1. Camera tab */}
                {activeSubTab === "cameras" && (
                  <table>
                    <thead>
                      <tr>
                        <th>Camera ID</th>
                        <th>Ground Truth</th>
                        <th>Kloudspot Accuracy</th>
                        <th>Our FRS Accuracy</th>
                        <th>Winner</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats?.camera_stats?.map((c, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 600 }}>{c.camera}</td>
                          <td>{c.total_events}</td>
                          <td style={{ color: "#f97316" }}>{c.kloudspot_acc.toFixed(1)}%</td>
                          <td style={{ color: "#3b82f6" }}>{c.our_acc.toFixed(1)}%</td>
                          <td>
                            <span className={`badge ${c.winner === "Our FRS" ? "badge-blue" : c.winner === "Kloudspot" ? "badge-orange" : "badge-grey"}`}>
                              {c.winner}
                            </span>
                          </td>
                        </tr>
                      ))}
                      {(!stats?.camera_stats || stats.camera_stats.length === 0) && (
                        <tr><td colSpan={5} className="empty">No camera metrics for selected date range</td></tr>
                      )}
                    </tbody>
                  </table>
                )}

                {/* 2. Persons tab */}
                {activeSubTab === "persons" && (
                  <table>
                    <thead>
                      <tr>
                        <th>Person Name</th>
                        <th>Sighted (KS / Our)</th>
                        <th>KS Count</th>
                        <th>Our Count</th>
                        <th>Match Rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats?.person_stats?.map((p, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 600 }}>{p.person_name}</td>
                          <td>
                            <span style={{ marginRight: 6 }}>{p.in_both ? "✅" : p.ks_count > 0 ? "⚠️" : "❌"}</span>
                            <span>{p.our_count > 0 ? "✅" : "❌"}</span>
                          </td>
                          <td>{p.ks_count}</td>
                          <td>{p.our_count}</td>
                          <td style={{ fontFamily: "monospace" }}>{p.match_rate.toFixed(1)}%</td>
                        </tr>
                      ))}
                      {(!stats?.person_stats || stats.person_stats.length === 0) && (
                        <tr><td colSpan={5} className="empty">No person metrics. Seed demo data to see.</td></tr>
                      )}
                    </tbody>
                  </table>
                )}

                {/* 3. Attendance comparison tab */}
                {activeSubTab === "attendance" && (
                  <table style={{ minWidth: "100%" }}>
                    <thead>
                      <tr>
                        <th>Metric Type</th>
                        <th>Kloudspot Sighting</th>
                        <th>Our Local FRS</th>
                        <th>Accuracy Delta</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td><b>Total Check-ins (Entry Gate)</b></td>
                        <td style={{ color: "#f97316", fontFamily: "monospace" }}>{checkinStats.kloudspot_in ?? 0}</td>
                        <td style={{ color: "#3b82f6", fontFamily: "monospace" }}>{checkinStats.matched_in ?? 0}</td>
                        <td style={{ fontWeight: 600 }}>
                          {checkinStats.kloudspot_in > 0
                            ? `${((checkinStats.matched_in / checkinStats.kloudspot_in) * 100).toFixed(0)}% matching`
                            : "—"}
                        </td>
                      </tr>
                      <tr>
                        <td><b>Total Check-outs (Exit Gate)</b></td>
                        <td style={{ color: "#f97316", fontFamily: "monospace" }}>{checkinStats.kloudspot_out ?? 0}</td>
                        <td style={{ color: "#3b82f6", fontFamily: "monospace" }}>{checkinStats.matched_out ?? 0}</td>
                        <td style={{ fontWeight: 600 }}>
                          {checkinStats.kloudspot_out > 0
                            ? `${((checkinStats.matched_out / checkinStats.kloudspot_out) * 100).toFixed(0)}% matching`
                            : "—"}
                        </td>
                      </tr>
                      <tr>
                        <td><b>Duplicate Detections (&lt;30s)</b></td>
                        <td style={{ color: "#f97316", fontFamily: "monospace" }}>{ks.duplicates ?? 0}</td>
                        <td style={{ color: "#3b82f6", fontFamily: "monospace" }}>{our.duplicates ?? 0}</td>
                        <td>
                          {ks.duplicates > our.duplicates
                            ? <span className="badge badge-green" style={{ fontSize: 9 }}>Our Dedup Better</span>
                            : <span className="badge badge-grey" style={{ fontSize: 9.5 }}>Equivalent</span>}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                )}

              </div>
            </div>

          </div>

          {/* Detailed Paginated Incident Comparison Feed */}
          <div className="table-wrap">
            <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>Compared Incident Stream Detections</span>

              <div style={{ display: "flex", gap: 6 }} className="toolbar-group">
                {[
                  { id: "all", label: "All" },
                  { id: "both_matched", label: "Matched" },
                  { id: "mismatch", label: "Wrong Identifications" },
                  { id: "kloudspot_only", label: "Missed in Our FRS" },
                  { id: "our_only", label: "Missed in Kloudspot" }
                ].map(t => (
                  <button key={t.id} className={`btn btn-sm ${statusFilter === t.id ? "btn-primary" : ""}`} onClick={() => setStatusFilter(t.id)}>
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ padding: "10px 16px", display: "flex", gap: 12, alignItems: "center", borderBottom: "1px solid var(--border)" }}>
              <div className="search-box">
                <span className="search-icon"><Icon path={icons.search} size={13} /></span>
                <input type="text" placeholder="Search person name..." value={search} onChange={e => setSearch(e.target.value)} style={{ width: 250 }} />
              </div>
              <span style={{ fontSize: 11, color: "var(--text2)", marginLeft: "auto" }}>
                Found <b>{totalEvents}</b> incidents
              </span>
            </div>

            <div style={{ maxHeight: 500, overflowY: "auto" }}>
              {events.map((ev, i) => {
                const isMatched = ev.status === "both_matched";
                const isMismatch = ev.status === "mismatch";
                const isKsOnly = ev.status === "kloudspot_only";
                const isOurOnly = ev.status === "our_only";

                const timeDiff = ev.time_delta_seconds != null ? `${ev.time_delta_seconds.toFixed(1)}s` : null;

                return (
                  <div key={i} style={{
                    padding: 12, borderBottom: "1px solid var(--border)",
                    background: isMismatch ? "rgba(224,82,82,0.04)" : isMatched ? "" : "rgba(255,255,255,0.01)"
                  }}>
                    {/* Sighting header */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontFamily: "monospace", fontSize: 10.5, color: "var(--text3)" }}>#{totalEvents - ((page - 1) * 20 + i)}</span>
                        <span style={{ fontSize: 11, color: "var(--text2)" }}>
                          {new Date(ev.timestamp_iso || (ev.timestamp_sec * 1000)).toLocaleString("en-IN")}
                        </span>
                        {timeDiff && (
                          <span className="badge badge-grey" style={{ fontSize: 10 }}>Time Jitter: {timeDiff}</span>
                        )}
                      </div>

                      {isMatched && <span className="pill-matched">✓ Both Matched</span>}
                      {isMismatch && <span className="pill-mismatch">❌ Wrong Identification</span>}
                      {isKsOnly && <span className="pill-ks-only">⚠️ Kloudspot Only (Our FRS Missed)</span>}
                      {isOurOnly && <span className="pill-our-only">⚠️ Our FRS Only (Kloudspot Missed)</span>}
                    </div>

                    {/* Sighting details columns */}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

                      {/* Left: Kloudspot */}
                      <div style={{
                        padding: 10, background: "rgba(0,0,0,0.15)", borderRadius: 6, border: "1px solid rgba(249,115,22,0.15)",
                        display: "flex", gap: 12, opacity: isOurOnly ? 0.35 : 1
                      }}>
                        <div style={{ width: 44, height: 44, borderRadius: 4, background: "var(--surface)", overflow: "hidden", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid var(--border)" }}>
                          {ev.kloudspot?.image
                            ? <img src={ensureDataUrl(ev.kloudspot.image)} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} onError={e => e.target.style.display = "none"} />
                            : <Icon path={icons.enroll} size={18} color="var(--text3)" />}
                        </div>
                        <div>
                          <div style={{ fontSize: 9.5, textTransform: "uppercase", letterSpacing: ".04em", color: "#f97316", fontWeight: 600 }}>Kloudspot CCTV Sighting</div>
                          <div style={{ fontWeight: 600, fontSize: 13, marginTop: 1 }}>{ev.kloudspot ? ev.kloudspot.person_name : "Sighting Missed"}</div>
                          {ev.kloudspot && (
                            <div style={{ fontSize: 10.5, color: "var(--text2)", marginTop: 2 }}>
                              Camera: <b>{ev.kloudspot.location_type || "Gate"}</b> | Dir: <b style={{ textTransform: "uppercase" }}>{ev.kloudspot.direction}</b>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Right: Our FRS */}
                      <div style={{
                        padding: 10, background: "rgba(0,0,0,0.15)", borderRadius: 6, border: "1px solid rgba(59,130,246,0.15)",
                        display: "flex", gap: 12, opacity: isKsOnly ? 0.35 : 1
                      }}>
                        <div style={{ width: 44, height: 44, borderRadius: 4, background: "var(--surface)", overflow: "hidden", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid var(--border)" }}>
                          {ev.our_frs?.snapshot
                            ? <img src={ensureDataUrl(ev.our_frs.snapshot)} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} onError={e => e.target.style.display = "none"} />
                            : <Icon path={icons.enroll} size={18} color="var(--text3)" />}
                        </div>
                        <div>
                          <div style={{ fontSize: 9.5, textTransform: "uppercase", letterSpacing: ".04em", color: "#3b82f6", fontWeight: 600 }}>Our FRS Local Detections</div>
                          <div style={{ fontWeight: 600, fontSize: 13, marginTop: 1 }}>{ev.our_frs ? ev.our_frs.person_name : "Sighting Missed"}</div>
                          {ev.our_frs && (
                            <div style={{ fontSize: 10.5, color: "var(--text2)", marginTop: 2 }}>
                              Camera ID: <b>{ev.our_frs.camera_id}</b> | Match Conf: <b style={{ color: ev.our_frs.confidence >= 0.7 ? "var(--green)" : "var(--orange)" }}>{(ev.our_frs.confidence * 100).toFixed(0)}%</b>
                            </div>
                          )}
                        </div>
                      </div>

                    </div>

                  </div>
                );
              })}

              {events.length === 0 && (
                <div className="empty">
                  No compared incidents for selected status filter.
                  <br />
                  <span style={{ fontSize: 11, color: "var(--text3)" }}>Verify that you have synced Kloudspot events for this date. Click <b>Seed Mock Data</b> to quickly preview the dashboard interface.</span>
                </div>
              )}
            </div>

            {/* Pagination */}
            {totalEvents > 20 && (
              <div style={{ display: "flex", justifyContent: "center", gap: 10, padding: 12, borderTop: "1px solid var(--border)" }}>
                <button className="btn btn-sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>← Prev</button>
                <span style={{ alignSelf: "center", fontSize: 11, color: "var(--text2)" }}>
                  Page <b>{page}</b> of {Math.ceil(totalEvents / 20)}
                </span>
                <button className="btn btn-sm" onClick={() => setPage(p => Math.min(Math.ceil(totalEvents / 20), p + 1))} disabled={page >= Math.ceil(totalEvents / 20)}>Next →</button>
              </div>
            )}

          </div>
        </>
      )}
      </>
      )}
    </div>
  );
}

// ─── VIEW IMAGES MODAL ───────────────────────────────────────
function ViewImagesModal({ person, onClose }) {
  // On Render: train_images/ doesn't exist — show DB photo + enrollment info instead
  const photo = person.photo_data_url || null;

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 460 }}>
        <div className="modal-header">
          <span className="modal-title">Enrollment — {person.name}</span>
          <button className="btn btn-sm btn-icon" onClick={onClose}><Icon path={icons.x} size={13} /></button>
        </div>
        <div className="modal-body">

          {/* Person info */}
          <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 16, padding: "12px", background: "var(--surface2)", borderRadius: 6, border: "1px solid var(--border)" }}>
            <div style={{ width: 80, height: 80, borderRadius: 8, overflow: "hidden", flexShrink: 0, background: "var(--surface)", border: "2px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              {photo
                ? <img src={photo} alt={person.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                : <Icon path={icons.enroll} size={28} color="var(--text3)" />}
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{person.name}</div>
              <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 3 }}>ID: #{person.id}</div>
              <div style={{ fontSize: 11, color: "var(--text2)" }}>
                Watchlist: <span style={{ color: "var(--accent)" }}>{person.watchlist || "employee"}</span>
              </div>
              {person.company && (
                <div style={{ fontSize: 11, color: "var(--text2)" }}>
                  Company: <span style={{ textTransform: "capitalize", color: "var(--text)" }}>{person.company}</span>
                </div>
              )}
            </div>
          </div>

          {/* Enrollment status */}
          <div style={{ background: "var(--surface2)", borderRadius: 6, padding: "10px 14px", border: "1px solid var(--border)" }}>
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8, color: "var(--text)" }}>Enrollment Status</div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: photo ? "var(--green)" : "var(--orange)" }} />
              <span style={{ fontSize: 12, color: photo ? "var(--green)" : "var(--orange)" }}>
                {photo ? "✓ Face photo stored in database" : "⚠ No photo stored yet"}
              </span>
            </div>
            <div style={{ fontSize: 11, color: "var(--text2)" }}>
              Face embeddings are stored in the local FAISS index (5 embeddings per person).
              The system enrolls 5 verified photos and checks all belong to the same person before training.
            </div>
          </div>

          <div style={{ marginTop: 12, fontSize: 11, color: "var(--text3)", padding: "6px 10px", background: "var(--surface2)", borderRadius: 4, fontFamily: "monospace" }}>
            Source: {person.train_folder || "face_images_export/"}
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

// ─── BULK IMPORT MODAL ───────────────────────────────────────
function BulkImportModal({ watchlist, onClose }) {
  const [files, setFiles] = useState([]);
  const [persons, setPersons] = useState([]);
  const [bulkWatchlist, setBulkWatchlist] = useState(watchlist || "employee");
  const [loading, setLoading] = useState(false);
  const [log, setLog] = useState([]);
  const [done, setDone] = useState(false);
  // Local server bulk enroll
  const [localMode, setLocalMode] = useState(false);
  const [localUrl, setLocalUrl] = useState("http://localhost:8000");
  const [localLoading, setLocalLoading] = useState(false);
  const [localResult, setLocalResult] = useState(null);
  const folderRef = useRef();

  const handleFolderSelect = (e) => {
    const allFiles = Array.from(e.target.files).filter(f => f.type.startsWith("image/"));
    const map = {};
    for (const f of allFiles) {
      const parts = f.webkitRelativePath.split("/");
      if (parts.length >= 2) {
        const personName = parts[parts.length - 2];
        if (!map[personName]) map[personName] = [];
        map[personName].push(f);
      }
    }
    const list = Object.entries(map).map(([name, imgs]) => ({ name, files: imgs }));
    setPersons(list);
    setFiles(allFiles);
    setLog([]);
    setDone(false);
  };

  const runLocalBulkEnroll = async () => {
    setLocalLoading(true);
    setLocalResult(null);
    try {
      const r = await fetch(`${localUrl}/api/v1/frd/bulk-enroll-folders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ watchlist: bulkWatchlist, overwrite: false })
      });
      const d = await r.json();
      if (r.ok) {
        setLocalResult({
          ok: true,
          msg: `✅ Done! ${d.total_persons} persons enrolled (${d.total_images} images)`
        });
      } else {
        setLocalResult({ ok: false, msg: `❌ ${d.detail || "Failed"}` });
      }
    } catch (e) {
      setLocalResult({ ok: false, msg: `❌ Cannot reach ${localUrl} — is local server running?` });
    }
    setLocalLoading(false);
  };

  const runImport = async () => {
    if (!persons.length) return;
    setLoading(true);
    setLog([]);
    let totalEnrolled = 0;

    for (const person of persons) {
      const addLog = (msg, ok = true) => setLog(prev => [...prev, { msg: `${person.name}: ${msg}`, ok }]);
      addLog(`Enrolling ${person.files.length} photo(s)...`);
      let enrolled = 0;

      for (const file of person.files) {
        const fd = new FormData();
        fd.append("file", file);
        try {
          const r = await fetch(
            `${API_BASE}/api/v1/frd/enroll?name=${encodeURIComponent(person.name)}&watchlist=${bulkWatchlist}`,
            { method: "POST", body: fd }
          );
          if (r.ok) enrolled++;
          else {
            const d = await r.json().catch(() => ({}));
            addLog(`⚠ ${file.name}: ${d.detail || r.status}`, false);
          }
        } catch {
          addLog(`⚠ ${file.name}: server unreachable`, false);
        }
      }

      if (enrolled > 0) { totalEnrolled++; addLog(`✓ ${enrolled}/${person.files.length} photos enrolled`); }
      else addLog(`✗ No photos enrolled`, false);
    }

    setLoading(false);
    setDone(true);
    setLog(prev => [...prev, { msg: `─── Done: ${totalEnrolled}/${persons.length} persons enrolled ───`, ok: totalEnrolled > 0 }]);
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && !loading && onClose()}>
      <div className="modal" style={{ maxWidth: 560 }}>
        <div className="modal-header">
          <span className="modal-title">📁 Bulk Import</span>
          <button className="btn btn-sm btn-icon" onClick={onClose}><Icon path={icons.x} size={13} /></button>
        </div>
        <div className="modal-body">

          {/* Mode toggle */}
          <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
            <button className={`btn btn-sm ${!localMode ? "btn-primary" : ""}`} onClick={() => setLocalMode(false)}>
              Upload Photos
            </button>
            <button className={`btn btn-sm ${localMode ? "btn-primary" : ""}`} onClick={() => setLocalMode(true)}>
              🖥 From Local train_images/
            </button>
          </div>

          <div className="form-row" style={{ marginBottom: 12 }}>
            <div className="form-group">
              <label className="form-label">Watchlist</label>
              <select value={bulkWatchlist} onChange={e => setBulkWatchlist(e.target.value)}>
                <option value="employee">Employee</option>
                <option value="visitor">Visitor</option>
                <option value="blacklist">Blacklist</option>
              </select>
            </div>
          </div>

          {localMode ? (
            /* ── Local server mode ── */
            <div>
              <div style={{ background: "var(--surface2)", borderRadius: 6, padding: "10px 12px", marginBottom: 14, fontSize: 12, color: "var(--text2)", border: "1px solid var(--border)" }}>
                <div style={{ fontWeight: 600, color: "var(--text)", marginBottom: 4 }}>How it works:</div>
                <div>1. Make sure <b>python start.py</b> is running locally with <b>AI_MODE=1</b></div>
                <div>2. Click "Enroll from train_images/" below</div>
                <div>3. Local server reads your <b>train_images/</b> folder, enrolls all persons, saves to Render DB</div>
              </div>
              <div className="form-group">
                <label className="form-label">Local Server URL</label>
                <input type="text" value={localUrl} onChange={e => setLocalUrl(e.target.value)}
                  placeholder="http://localhost:8000" />
              </div>
              {localResult && (
                <div style={{
                  marginTop: 10, padding: "8px 12px", borderRadius: 5, fontSize: 12,
                  background: localResult.ok ? "rgba(61,186,110,.1)" : "rgba(224,82,82,.1)",
                  color: localResult.ok ? "var(--green)" : "var(--red)"
                }}>
                  {localResult.msg}
                </div>
              )}
            </div>
          ) : (
            /* ── Upload mode ── */
            <div>
              <div style={{ background: "var(--surface2)", borderRadius: 6, padding: "10px 12px", marginBottom: 14, fontSize: 12, color: "var(--text2)", border: "1px solid var(--border)" }}>
                <div style={{ fontWeight: 600, color: "var(--text)", marginBottom: 4 }}>📂 Folder structure:</div>
                <div style={{ fontFamily: "monospace", fontSize: 11, lineHeight: 1.8 }}>
                  MyFolder/<br />
                  &nbsp;&nbsp;John Smith/ ← person name<br />
                  &nbsp;&nbsp;&nbsp;&nbsp;1.jpg, 2.jpg<br />
                  &nbsp;&nbsp;Jane Doe/<br />
                  &nbsp;&nbsp;&nbsp;&nbsp;photo1.jpg
                </div>
              </div>

              <div className="drop-zone" onClick={() => folderRef.current?.click()}
                style={{ marginBottom: persons.length ? 12 : 0 }}>
                <input ref={folderRef} type="file" style={{ display: "none" }}
                  webkitdirectory="true" directory="true" multiple onChange={handleFolderSelect} />
                <Icon path={icons.upload} size={22} color="var(--text3)" />
                <div className="drop-zone-text">
                  {persons.length ? `${persons.length} person(s) found — click to change` : "Click to select a folder"}
                </div>
              </div>

              {persons.length > 0 && !loading && !done && (
                <div style={{ maxHeight: 160, overflowY: "auto", border: "1px solid var(--border)", borderRadius: 5 }}>
                  {persons.map((p, i) => (
                    <div key={i} style={{
                      display: "flex", justifyContent: "space-between", padding: "6px 10px",
                      borderBottom: "1px solid var(--border)", fontSize: 12
                    }}>
                      <span style={{ fontWeight: 500 }}>{p.name}</span>
                      <span style={{ color: "var(--text2)" }}>{p.files.length} photo{p.files.length !== 1 ? "s" : ""}</span>
                    </div>
                  ))}
                </div>
              )}

              {log.length > 0 && (
                <div style={{ maxHeight: 200, overflowY: "auto", marginTop: 10, display: "flex", flexDirection: "column", gap: 3 }}>
                  {log.map((l, i) => (
                    <div key={i} style={{
                      fontSize: 11, padding: "3px 8px", borderRadius: 3,
                      background: l.ok ? "rgba(61,186,110,.08)" : "rgba(224,82,82,.08)",
                      color: l.ok ? "var(--green)" : "var(--red)"
                    }}>{l.msg}</div>
                  ))}
                </div>
              )}

              {loading && (
                <div style={{ marginTop: 10, fontSize: 12, color: "var(--text2)", textAlign: "center" }}>
                  ⏳ Enrolling... do not close
                </div>
              )}
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn" onClick={onClose}>{done || localResult?.ok ? "Close" : "Cancel"}</button>
          {localMode ? (
            <button className="btn btn-primary" disabled={localLoading} onClick={runLocalBulkEnroll}>
              {localLoading ? "Enrolling..." : "Enroll from train_images/"}
            </button>
          ) : (
            !done && (
              <button className="btn btn-primary" disabled={!persons.length || loading} onClick={runImport}>
                {loading ? "Importing..." : `Import ${persons.length} Person${persons.length !== 1 ? "s" : ""}`}
              </button>
            )
          )}
        </div>
      </div>
    </div>
  );
}

// ─── HUMANS PAGE ─────────────────────────────────────────────
function HumansPage() {
  const [persons, setPersons] = useState([]);
  const [watchlist, setWatchlist] = useState("employee");
  const [search, setSearch] = useState("");
  const [companyFilter, setCompanyFilter] = useState("");
  const [showEnroll, setShowEnroll] = useState(false);
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [viewingImages, setViewingImages] = useState(null);
  const [images, setImages] = useState([]);
  const [previews, setPreviews] = useState([]);
  const [name, setName] = useState("");
  const [enrollWatchlist, setEnrollWatchlist] = useState("employee");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [results, setResults] = useState([]);
  const [retraining, setRetraining] = useState(null);
  const fileRef = useRef();
  const addFileRef = useRef();
  const [addingTo, setAddingTo] = useState(null);
  const [addFile, setAddFile] = useState(null);
  const [addPreview, setAddPreview] = useState(null);
  const [addLoading, setAddLoading] = useState(false);
  const [addResult, setAddResult] = useState(null);
  // Edit state
  const [editingPerson, setEditingPerson] = useState(null);
  const [editName, setEditName] = useState("");
  const [editWatchlist, setEditWatchlist] = useState("employee");
  const [editSaving, setEditSaving] = useState(false);
  // Bulk select state
  const [selected, setSelected] = useState(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);

  const load = () => fetchAPI(`/api/v1/persons?watchlist=${watchlist}`).then(d => { if (d) { setPersons(d.persons || []); setSelected(new Set()); } });
  useEffect(() => { load(); }, [watchlist]);

  const filtered = persons.filter(p =>
    (!search || p.name.toLowerCase().includes(search.toLowerCase())) &&
    (!companyFilter || (p.company || "").toLowerCase() === companyFilter.toLowerCase())
  );

  // Get unique companies from loaded persons
  const companies = [...new Set(persons.map(p => p.company).filter(Boolean))].sort();

  const toggleSelect = (id) => setSelected(prev => {
    const s = new Set(prev);
    s.has(id) ? s.delete(id) : s.add(id);
    return s;
  });
  const toggleAll = () => setSelected(prev => prev.size === filtered.length ? new Set() : new Set(filtered.map(p => p.id)));

  const bulkDelete = async () => {
    if (!selected.size) return;
    const names = persons.filter(p => selected.has(p.id)).map(p => p.name).join(", ");
    if (!window.confirm(`Delete ${selected.size} person(s)?\n\n${names}\n\nThis cannot be undone.`)) return;
    setBulkDeleting(true);
    for (const id of selected) {
      await fetchAPI(`/api/v1/frd/person/${id}?watchlist=${watchlist}`, { method: "DELETE" });
    }
    setBulkDeleting(false);
    load();
  };

  const remove = async (id) => {
    const person = persons.find(p => p.id === id);
    if (!window.confirm(`Delete "${person?.name}" completely?\n\nThis will remove:\n• Face embeddings from FAISS\n• Person record\n• Training images folder\n• Enrollment photos\n\nThis cannot be undone.`)) return;
    const res = await fetchAPI(`/api/v1/frd/person/${id}?watchlist=${watchlist}`, { method: "DELETE" });
    if (res?.success) {
      setPersons(p => p.filter(x => x.id !== id));
    }
  };

  const openEdit = (person) => {
    setEditingPerson(person);
    setEditName(person.name);
    setEditWatchlist(person.watchlist || "employee");
  };

  const saveEdit = async () => {
    if (!editingPerson || !editName.trim()) return;
    setEditSaving(true);
    await fetchAPI(`/api/v1/persons/${editingPerson.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: editName.trim(), watchlist: editWatchlist })
    });
    setEditSaving(false);
    setEditingPerson(null);
    load();
  };

  const retrain = async (p) => {
    setRetraining(p.id);
    const res = await fetchAPI(`/api/v1/frd/person/${p.id}/retrain`, { method: "POST" });
    setRetraining(null);
    alert(res?.success ? `✓ ${res.name}: ${res.embeddings_added}/${res.images_found} images retrained` : "Retrain failed");
  };

  const handleFiles = (fileList) => {
    const files = Array.from(fileList).filter(f => f.type.startsWith("image/")).slice(0, 5 - images.length);
    setImages(p => [...p, ...files]);
    setPreviews(p => [...p, ...files.map(f => URL.createObjectURL(f))]);
    setResults([]);
  };

  const handleEnroll = async () => {
    if (!images.length || !name.trim()) return;
    setLoading(true); setResults([]); setProgress({ done: 0, total: images.length });
    const res = [];
    for (let i = 0; i < images.length; i++) {
      const fd = new FormData(); fd.append("file", images[i]);
      try {
        const r = await fetch(`${API_BASE}/api/v1/frd/enroll?name=${encodeURIComponent(name)}&watchlist=${enrollWatchlist}`, { method: "POST", body: fd });
        const d = await r.json();
        res.push({ success: r.ok, msg: `Photo ${i + 1}: ${r.ok ? "✓ Enrolled" : d.detail || "Failed"}` });
      } catch { res.push({ success: false, msg: `Photo ${i + 1}: Server unreachable` }); }
      setProgress({ done: i + 1, total: images.length }); setResults([...res]);
    }
    if (res.some(r => r.success)) { load(); setName(""); setImages([]); setPreviews(p => { p.forEach(u => URL.revokeObjectURL(u)); return []; }); }
    setLoading(false);
  };

  const submitAddImage = async () => {
    if (!addFile || !addingTo) return;
    setAddLoading(true);
    const fd = new FormData(); fd.append("file", addFile);
    const res = await fetchAPI(`/api/v1/frd/person/${addingTo.id}/add-image`, { method: "POST", body: fd });
    setAddLoading(false);
    if (res?.success) { setAddResult({ success: true, msg: `Photo #${res.image_number} added` }); load(); }
    else setAddResult({ success: false, msg: res?.detail || "Failed" });
  };

  return (
    <div>
      <div className="toolbar">
        <div className="toolbar-group">
          {["employee", "visitor", "blacklist"].map(w => (
            <button key={w} className={`btn btn-sm ${watchlist === w ? "btn-primary" : ""}`} onClick={() => setWatchlist(w)}>
              {w === "employee" ? "Employees" : w === "visitor" ? "Visitors" : "Blacklist"}
            </button>
          ))}
        </div>
        <div className="search-box">
          <span className="search-icon"><Icon path={icons.search} size={13} /></span>
          <input type="text" placeholder="Search name" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        {companies.length > 0 && (
          <div className="toolbar-group" style={{ flexWrap: "wrap" }}>
            <button className={`btn btn-sm ${!companyFilter ? "btn-primary" : ""}`}
              onClick={() => setCompanyFilter("")}>All</button>
            {companies.map(c => (
              <button key={c} className={`btn btn-sm ${companyFilter === c ? "btn-primary" : ""}`}
                onClick={() => setCompanyFilter(companyFilter === c ? "" : c)}
                style={{ textTransform: "capitalize" }}>
                {c}
              </button>
            ))}
          </div>
        )}
        <div style={{ display: "flex", gap: 6, marginLeft: "auto", alignItems: "center" }}>
          {selected.size > 0 && (
            <button className="btn btn-sm" style={{ background: "var(--red)", color: "#fff", border: "none" }}
              disabled={bulkDeleting} onClick={bulkDelete}>
              {bulkDeleting ? "Deleting..." : `🗑 Delete ${selected.size} selected`}
            </button>
          )}
          <button className="btn btn-sm" style={{ background: "var(--surface2)", color: "var(--text)" }}
            onClick={() => setShowBulkImport(true)}>
            📁 Bulk Import
          </button>
          <button className="btn btn-sm btn-primary" onClick={() => setShowEnroll(true)}>
            <Icon path={icons.plus} size={12} /> Add Human
          </button>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th style={{ width: 32 }}>
                <input type="checkbox"
                  checked={filtered.length > 0 && selected.size === filtered.length}
                  onChange={toggleAll} />
              </th>
              <th>Identity</th><th>First Name</th><th>Last Name</th><th>Company</th><th>Images</th><th>Status</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p, i) => {
              const parts = p.name.trim().split(" ");
              const first = parts[0] || "";
              const last = parts.slice(1).join(" ") || "";
              const identity = `${p.name.toLowerCase().replace(/ /g, ".")}@station-s.org`;
              return (
                <tr key={i} style={{ background: selected.has(p.id) ? "rgba(74,158,255,0.07)" : "" }}>
                  <td>
                    <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleSelect(p.id)} />
                  </td>
                  <td style={{ color: "var(--accent)", fontSize: 12 }}>{identity}</td>
                  <td style={{ fontWeight: 500 }}>{first}</td>
                  <td>{last}</td>
                  <td>
                    {p.company
                      ? <span className="badge badge-grey" style={{ fontSize: 10, textTransform: "uppercase" }}>{p.company}</span>
                      : <span style={{ color: "var(--text3)" }}>—</span>}
                  </td>
                  <td>
                    <div className="avatar avatar-sm">
                      {p.photo_data_url
                        ? <img src={p.photo_data_url} alt={p.name} onError={e => e.target.style.display = 'none'} />
                        : <Icon path={icons.enroll} size={12} color="var(--text3)" />}
                    </div>
                  </td>
                  <td><span className="badge badge-green">ACTIVE</span></td>
                  <td>
                    <div style={{ display: "flex", gap: 4 }}>
                      <button className="btn btn-sm btn-icon" title="View images" style={{ color: "var(--accent)" }} onClick={() => setViewingImages(p)}>
                        <Icon path={icons.eye} size={12} />
                      </button>
                      <button className="btn btn-sm btn-icon" title="Edit" onClick={() => openEdit(p)}>
                        <Icon path={icons.edit} size={12} />
                      </button>
                      <button className="btn btn-sm btn-icon" title="Add image" onClick={() => { setAddingTo(p); setAddFile(null); setAddPreview(null); setAddResult(null); }}>
                        <Icon path={icons.image} size={12} />
                      </button>
                      <button className="btn btn-sm btn-icon" title="Re-train" disabled={retraining === p.id} onClick={() => retrain(p)}>
                        {retraining === p.id ? "⏳" : <Icon path={icons.refresh} size={12} />}
                      </button>
                      <button className="btn btn-sm btn-icon" title="Remove" style={{ color: "var(--red)" }} onClick={() => remove(p.id)}>
                        <Icon path={icons.trash} size={12} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && <tr><td colSpan={8}><div className="empty">No persons found</div></td></tr>}
          </tbody>
        </table>
      </div>

      {/* Enroll Modal */}
      {showEnroll && (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && !loading && setShowEnroll(false)}>
          <div className="modal" style={{ maxWidth: 500 }}>
            <div className="modal-header">
              <span className="modal-title">Add Human</span>
              <button className="btn btn-sm btn-icon" onClick={() => setShowEnroll(false)}><Icon path={icons.x} size={13} /></button>
            </div>
            <div className="modal-body">
              <div className="form-row" style={{ marginBottom: 12 }}>
                <div className="form-group">
                  <label className="form-label">Full Name *</label>
                  <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Enter name" />
                </div>
                <div className="form-group">
                  <label className="form-label">List</label>
                  <select value={enrollWatchlist} onChange={e => setEnrollWatchlist(e.target.value)}>
                    <option value="employee">Employee</option>
                    <option value="visitor">Visitor</option>
                    <option value="blacklist">Blacklist</option>
                  </select>
                </div>
              </div>
              <div className="drop-zone" onClick={() => fileRef.current?.click()}>
                <input ref={fileRef} type="file" accept="image/*" multiple style={{ display: "none" }} onChange={e => handleFiles(e.target.files)} />
                <Icon path={icons.upload} size={22} color="var(--text3)" />
                <div className="drop-zone-text">Drop up to 5 photos or click to browse</div>
              </div>
              {previews.length > 0 && (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 6, marginTop: 10 }}>
                  {previews.map((src, i) => (
                    <div key={i} style={{ position: "relative" }}>
                      <img src={src} alt="" style={{ width: "100%", aspectRatio: "1", objectFit: "cover", borderRadius: 4, border: "1px solid var(--border)" }} />
                      {!loading && <button onClick={() => { setImages(p => p.filter((_, j) => j !== i)); setPreviews(p => { URL.revokeObjectURL(p[i]); return p.filter((_, j) => j !== i); }); }} style={{ position: "absolute", top: 2, right: 2, width: 16, height: 16, borderRadius: "50%", background: "var(--red)", border: "none", color: "#fff", fontSize: 9, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>✕</button>}
                    </div>
                  ))}
                </div>
              )}
              {loading && (
                <div style={{ marginTop: 10 }}>
                  <div className="progress-bar"><div className="progress-fill" style={{ width: `${(progress.done / progress.total) * 100}%` }} /></div>
                  <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 4 }}>Uploading {progress.done}/{progress.total}...</div>
                </div>
              )}
              {results.length > 0 && (
                <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}>
                  {results.map((r, i) => (
                    <div key={i} style={{ fontSize: 11, padding: "5px 8px", borderRadius: 3, background: r.success ? "rgba(61,186,110,.1)" : "rgba(224,82,82,.1)", color: r.success ? "var(--green)" : "var(--red)" }}>{r.msg}</div>
                  ))}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={() => setShowEnroll(false)}>Cancel</button>
              <button className="btn btn-primary" disabled={!images.length || !name.trim() || loading} onClick={handleEnroll}>
                {loading ? `Enrolling ${progress.done}/${progress.total}...` : "Add Human"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Image Modal */}
      {addingTo && (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && !addLoading && setAddingTo(null)}>
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">Add Image — {addingTo.name}</span>
              <button className="btn btn-sm btn-icon" onClick={() => setAddingTo(null)}><Icon path={icons.x} size={13} /></button>
            </div>
            <div className="modal-body">
              <div className="drop-zone" onClick={() => addFileRef.current?.click()}>
                <input ref={addFileRef} type="file" accept="image/*" style={{ display: "none" }} onChange={e => { const f = e.target.files[0]; if (f) { setAddFile(f); setAddPreview(URL.createObjectURL(f)); setAddResult(null); } }} />
                {addPreview ? <img src={addPreview} alt="" style={{ width: "100%", maxHeight: 180, objectFit: "cover", borderRadius: 4 }} /> : <><Icon path={icons.upload} size={22} color="var(--text3)" /><div className="drop-zone-text">Click to select photo</div></>}
              </div>
              {addResult && <div style={{ marginTop: 10, fontSize: 11, padding: "5px 8px", borderRadius: 3, background: addResult.success ? "rgba(61,186,110,.1)" : "rgba(224,82,82,.1)", color: addResult.success ? "var(--green)" : "var(--red)" }}>{addResult.msg}</div>}
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={() => setAddingTo(null)}>{addResult?.success ? "Close" : "Cancel"}</button>
              {!addResult?.success && <button className="btn btn-primary" disabled={!addFile || addLoading} onClick={submitAddImage}>{addLoading ? "Training..." : "Add & Train"}</button>}
            </div>
          </div>
        </div>
      )}

      {/* Edit Person Modal */}
      {editingPerson && (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && !editSaving && setEditingPerson(null)}>
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">Edit Human — {editingPerson.name}</span>
              <button className="btn btn-sm btn-icon" onClick={() => setEditingPerson(null)}>
                <Icon path={icons.x} size={13} />
              </button>
            </div>
            <div className="modal-body">
              {editingPerson.photo_url && (
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, padding: "10px 12px", background: "var(--surface2)", borderRadius: 6, border: "1px solid var(--border)" }}>
                  <div className="avatar" style={{ width: 48, height: 48, borderRadius: 8 }}>
                    {editingPerson.photo_data_url
                      ? <img src={editingPerson.photo_data_url} alt="" onError={e => e.target.style.display = 'none'} />
                      : <Icon path={icons.enroll} size={16} color="var(--text3)" />}
                  </div>
                  <div>
                    <div style={{ fontWeight: 500, fontSize: 13 }}>{editingPerson.name}</div>
                    <div style={{ fontSize: 11, color: "var(--text2)" }}>ID: #{editingPerson.id}</div>
                  </div>
                </div>
              )}
              <div className="form-group">
                <label className="form-label">Full Name *</label>
                <input type="text" value={editName} onChange={e => setEditName(e.target.value)}
                  placeholder="Enter full name"
                  onKeyDown={e => e.key === "Enter" && saveEdit()} />
              </div>
              <div className="form-group">
                <label className="form-label">List / Watchlist</label>
                <select value={editWatchlist} onChange={e => setEditWatchlist(e.target.value)}>
                  <option value="employee">Employee</option>
                  <option value="visitor">Visitor</option>
                  <option value="blacklist">Blacklist</option>
                </select>
              </div>
              <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 4 }}>
                Note: Changing the name updates recognition labels. Re-train after renaming for best results.
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={() => setEditingPerson(null)} disabled={editSaving}>Cancel</button>
              <button className="btn btn-primary" disabled={!editName.trim() || editSaving} onClick={saveEdit}>
                {editSaving ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* View Images Modal */}
      {viewingImages && (
        <ViewImagesModal person={viewingImages} onClose={() => setViewingImages(null)} />
      )}

      {/* Bulk Import Modal */}
      {showBulkImport && (
        <BulkImportModal
          watchlist={watchlist}
          onClose={() => { setShowBulkImport(false); load(); }}
        />
      )}
    </div>
  );
}

// ─── CAMERA CONFIG PAGE ──────────────────────────────────────
function CameraConfigPage({ camera, onBack, onSave }) {
  const [form, setForm] = useState({
    name: camera.name || "",
    rtsp_url: camera.rtsp_url || "",
    camera_type: camera.camera_type || "checkin",
    fps: camera.fps || 30,
    enabled: camera.enabled !== false,
    face_confidence: camera.face_confidence || 0.6,
    detection_range: camera.detection_range || 6.5,
    min_yaw: camera.min_yaw ?? -35,
    max_yaw: camera.max_yaw ?? 35,
    min_pitch: camera.min_pitch ?? -15,
    max_pitch: camera.max_pitch ?? 15,
    detection_zone: camera.detection_zone || [],
    count_line: camera.count_line || null,
    count_inside_pt: camera.count_inside_pt || null,
    room_id: camera.room_id || "",
    send_image: camera.send_image !== false,
    data_frequency: camera.data_frequency || 2,
    notes: camera.notes || "",
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const [drawing, setDrawing] = useState(false);
  const [zone, setZone] = useState(camera.detection_zone || []);
  const [countLine, setCountLine] = useState(camera.count_line || null);
  const [countInsidePt, setCountInsidePt] = useState(camera.count_inside_pt || null);
  const [lineDrawing, setLineDrawing] = useState(false);
  const [insidePtDrawing, setInsidePtDrawing] = useState(false);
  const [linePreview, setLinePreview] = useState(null);
  const lineDragRef = useRef(null);
  const camType = form.camera_type;
  const showZone = camType === "frs" || camType === "both" || camType === "checkin" || camType === "checkout";
  const showLine = camType === "headcount" || camType === "both";
  const [imgSize, setImgSize] = useState({ w: 640, h: 360 });

  // Draw zone on canvas overlay
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || zone.length < 1) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    // Map zone % directly to canvas internal pixels (1:1 with CSS %)
    const pts = zone.map(p => [p[0] / 100 * W, p[1] / 100 * H]);

    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    pts.slice(1).forEach(p => ctx.lineTo(p[0], p[1]));
    if (zone.length >= 3) ctx.closePath();
    ctx.strokeStyle = "#4a9eff";
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 3]);
    ctx.stroke();
    if (zone.length >= 3) {
      ctx.fillStyle = "rgba(74,158,255,0.10)";
      ctx.fill();
    }
    pts.forEach((p, i) => {
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.arc(p[0], p[1], 6, 0, Math.PI * 2);
      ctx.fillStyle = i === 0 ? "#3dba6e" : "#4a9eff";
      ctx.fill();
    });
    if (zone.length >= 3) {
      ctx.setLineDash([]);
      ctx.fillStyle = "#4a9eff";
      ctx.font = "bold 14px monospace";
      ctx.fillText(drawing ? `Drawing... (${zone.length} pts)` : "ZONE ACTIVE", 8, 22);
    }
  }, [zone, drawing]);

  const handleCanvasClick = (e) => {
    if (!drawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Get click position as % of the canvas CSS display area
    const rect = canvas.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 1000) / 10;
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 1000) / 10;

    // Clamp 0-100
    setZone(prev => [...prev, [
      Math.max(0, Math.min(100, x)),
      Math.max(0, Math.min(100, y))
    ]]);
  };

  const clearZone = () => setZone([]);
  const closeZone = () => {
    if (zone.length >= 3) {
      setForm(f => ({ ...f, detection_zone: zone }));
      setDrawing(false);
    }
  };

  // ── Count-line drawing (drag on the feed) — headcount / both ──
  const lineStart = (e) => {
    if (!lineDrawing) return;
    e.preventDefault();
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch (err) {}
    const rect = e.currentTarget.getBoundingClientRect();
    lineDragRef.current = {
      x1: Math.round(((e.clientX - rect.left) / rect.width) * 1000) / 10,
      y1: Math.round(((e.clientY - rect.top) / rect.height) * 1000) / 10,
    };
    setLinePreview(null);
  };
  const lineMove = (e) => {
    const d = lineDragRef.current;
    if (!d || !lineDrawing) return;
    const rect = e.currentTarget.getBoundingClientRect();
    setLinePreview({
      x1: d.x1, y1: d.y1,
      x2: Math.round(((e.clientX - rect.left) / rect.width) * 1000) / 10,
      y2: Math.round(((e.clientY - rect.top) / rect.height) * 1000) / 10,
    });
  };
  const lineEnd = (e) => {
    const d = lineDragRef.current;
    const p = linePreview;
    lineDragRef.current = null;
    if (!d || !lineDrawing) return;
    try { e && e.currentTarget.releasePointerCapture && e.currentTarget.releasePointerCapture(e.pointerId); } catch (err) {}
    setLinePreview(null);
    setLineDrawing(false);
    if (!p) return;
    if (Math.abs(p.x2 - p.x1) < 3 && Math.abs(p.y2 - p.y1) < 3) return; // accidental click
    const line = [
      Math.max(0, Math.min(100, Math.round(p.x1 * 10) / 10)),
      Math.max(0, Math.min(100, Math.round(p.y1 * 10) / 10)),
      Math.max(0, Math.min(100, Math.round(p.x2 * 10) / 10)),
      Math.max(0, Math.min(100, Math.round(p.y2 * 10) / 10)),
    ];
    setCountLine(line);
    setForm(f => ({ ...f, count_line: line }));
  };

  const handleSave = async () => {
    setSaving(true);
    const payload = { ...form, detection_zone: showZone ? zone : [], count_line: showLine ? countLine : null, count_inside_pt: showLine ? countInsidePt : null, room_id: (form.room_id || "").trim() || null };
    await fetchAPI(`/api/v1/cameras/${encodeURIComponent(camera.id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    onSave?.();
  };

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <button className="btn btn-sm" onClick={onBack}>← Back</button>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>Camera Configuration — {camera.id}</div>
          <div style={{ fontSize: 11, color: "var(--text2)" }}>Update the camera configuration</div>
        </div>
        <button className="btn btn-primary btn-sm" style={{ marginLeft: "auto" }}
          disabled={saving} onClick={handleSave}>
          {saving ? "Saving..." : saved ? "✓ Saved" : "Save Changes"}
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }} className="two-col-config">
        {/* Left — Live feed + zone / line drawing */}
        <div>
          <div className="table-wrap" style={{ padding: 0, overflow: "hidden" }}>
            <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border)", fontSize: 12, fontWeight: 500 }}>
              {showLine && !showZone ? "Count Line" : showZone && showLine ? "Detection Zone + Count Line" : "Detection Zone"}
              <span style={{ fontSize: 11, color: "var(--text2)", marginLeft: 8 }}>
                {drawing && "Click on feed to add zone points"}
                {lineDrawing && "Drag a LINE across the doorway on the feed"}
                {!drawing && !lineDrawing && (camType === "headcount" ? "Head-count camera — draw the count line" : camType === "both" ? "Both — draw zone AND count line" : "FRS camera — draw the detection zone")}
              </span>
            </div>
            <div style={{ position: "relative", background: "#000" }}>
              <ConfigLiveFeed cameraId={camera.id} />
              {showZone && (
                <canvas
                  ref={canvasRef}
                  width={640} height={360}
                  style={{
                    position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
                    cursor: drawing ? "crosshair" : "default",
                    pointerEvents: lineDrawing ? "none" : "auto",
                  }}
                  onClick={handleCanvasClick}
                />
              )}
              {showLine && (
                <div
                  style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
                    cursor: lineDrawing ? "crosshair" : (insidePtDrawing ? "crosshair" : "default"), touchAction: "none",
                    pointerEvents: (drawing && !insidePtDrawing) ? "none" : "auto" }}
                  onPointerDown={lineStart} onPointerMove={lineMove} onPointerUp={lineEnd}
                  onClick={(e) => {
                    if (insidePtDrawing) {
                      const rect = e.currentTarget.getBoundingClientRect();
                      const x = Math.round(((e.clientX - rect.left) / rect.width) * 1000) / 10;
                      const y = Math.round(((e.clientY - rect.top) / rect.height) * 1000) / 10;
                      setCountInsidePt([Math.max(0, Math.min(100, x)), Math.max(0, Math.min(100, y))]);
                      setInsidePtDrawing(false);
                      setForm(f => ({ ...f, count_inside_pt: [x, y] }));
                    }
                  }}
                >
                  <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
                    {countLine && countLine.length >= 4 && (
                      <>
                        <line x1={`${countLine[0]}%`} y1={`${countLine[1]}%`} x2={`${countLine[2]}%`} y2={`${countLine[3]}%`}
                          stroke="#22c55e" strokeWidth={3} />
                        <circle cx={`${countLine[0]}%`} cy={`${countLine[1]}%`} r={5} fill="#22c55e" />
                        <circle cx={`${countLine[2]}%`} cy={`${countLine[3]}%`} r={5} fill="#22c55e" />
                      </>
                    )}
                    {linePreview && (
                      <line x1={`${linePreview.x1}%`} y1={`${linePreview.y1}%`} x2={`${linePreview.x2}%`} y2={`${linePreview.y2}%`}
                        stroke="#facc15" strokeWidth={3} strokeDasharray="6 4" />
                    )}
                    {countInsidePt && (
                      <g>
                        <circle cx={`${countInsidePt[0]}%`} cy={`${countInsidePt[1]}%`} r={6} fill="#3b82f6" stroke="#fff" strokeWidth={2} />
                        <text x={`${countInsidePt[0]}%`} y={`${countInsidePt[1] - 3}%`} fill="#3b82f6" fontSize="12" fontWeight="bold" textAnchor="middle">IN</text>
                      </g>
                    )}
                  </svg>
                </div>
              )}
            </div>
            <div style={{ padding: "8px 12px", display: "flex", gap: 8, borderTop: "1px solid var(--border)", flexWrap: "wrap", alignItems: "center" }}>
              {showZone && (!drawing
                ? <button className="btn btn-sm btn-primary" disabled={lineDrawing} onClick={() => { setLineDrawing(false); setDrawing(true); }}>✏ Draw Zone</button>
                : <>
                  <button className="btn btn-sm btn-primary" onClick={closeZone} disabled={zone.length < 3}>
                    ✓ Close Zone ({zone.length} pts)
                  </button>
                  <button className="btn btn-sm" onClick={() => setZone(p => p.slice(0, -1))}>↩ Undo</button>
                </>
              )}
              {showZone && zone.length > 0 && (
                <button className="btn btn-sm" style={{ color: "var(--red)" }} onClick={() => { setZone([]); setForm(f => ({ ...f, detection_zone: [] })); }}>✕ Clear Zone</button>
              )}
              {showLine && (!lineDrawing
                ? <button className="btn btn-sm btn-primary" disabled={drawing} onClick={() => { setDrawing(false); setLineDrawing(true); }}>📏 Draw Count Line</button>
                : <button className="btn btn-sm" onClick={() => { setLineDrawing(false); setLinePreview(null); }}>✕ Cancel Line</button>
              )}
              {showLine && countLine && !lineDrawing && !insidePtDrawing && (
                <button className="btn btn-sm btn-primary" onClick={() => setInsidePtDrawing(true)}>📍 Set Inside Point</button>
              )}
              {insidePtDrawing && (
                <button className="btn btn-sm" onClick={() => setInsidePtDrawing(false)}>✕ Cancel Set Point</button>
              )}
              {showLine && countLine && !lineDrawing && (
                <button className="btn btn-sm" style={{ color: "var(--red)" }} onClick={() => { setCountLine(null); setCountInsidePt(null); setForm(f => ({ ...f, count_line: null, count_inside_pt: null })); }}>✕ Clear Line</button>
              )}
              {showLine && countInsidePt && !insidePtDrawing && (
                <button className="btn btn-sm" style={{ color: "var(--red)" }} onClick={() => { setCountInsidePt(null); setForm(f => ({ ...f, count_inside_pt: null })); }}>✕ Clear Point</button>
              )}
              {showZone && zone.length >= 3 && !drawing && (
                <span style={{ fontSize: 11, color: "var(--green)", marginLeft: "auto" }}>
                  ✓ Zone active ({zone.length} points)
                </span>
              )}
              {showLine && countLine && !lineDrawing && (
                <span style={{ fontSize: 11, color: "var(--green)", marginLeft: "auto" }}>
                  ✓ Count line active
                </span>
              )}
            </div>
            {showLine && (
              <div style={{ padding: "0 12px 10px", fontSize: 10.5, color: "var(--text3)" }}>
                Counting rule: person crosses the line → one direction <b style={{ color: "var(--green)" }}>IN (+1)</b>, other direction <b style={{ color: "var(--orange)" }}>OUT (−1)</b>. If IN/OUT feel swapped, redraw the line the opposite way.
              </div>
            )}
          </div>
        </div>

        {/* Right — Settings */}
        <div>
          <div className="table-wrap" style={{ padding: 16 }}>
            <div className="form-row" style={{ marginBottom: 12 }}>
              <div className="form-group">
                <label className="form-label">Camera Name</label>
                <input type="text" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">Camera Type</label>
                <select value={form.camera_type} onChange={e => setForm({ ...form, camera_type: e.target.value })}>
                  <option value="frs">FRS Only (Detection Zone)</option>
                  <option value="headcount">Head Count Only (Count Line)</option>
                  <option value="both">FRS + Head Count (Zone + Line)</option>
                  <option value="checkin">Entry Check-in (legacy)</option>
                  <option value="checkout">Exit Check-out (legacy)</option>
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Room ID (head-count room for this camera)</label>
              <input type="text" value={form.room_id || ""} placeholder="e.g. Room A"
                onChange={e => setForm({ ...form, room_id: e.target.value })} />
            </div>

            <div className="form-group">
              <label className="form-label">RTSP URL</label>
              <input type="text" value={form.rtsp_url} onChange={e => setForm({ ...form, rtsp_url: e.target.value })} />
            </div>

            <div className="form-row" style={{ marginBottom: 12 }}>
              <div className="form-group">
                <label className="form-label">Frames per second</label>
                <select value={form.fps} onChange={e => setForm({ ...form, fps: parseInt(e.target.value) })}>
                  {[1, 2, 5, 10, 15, 20, 25, 30].map(v => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Detection Range (metres)</label>
                <input type="number" value={form.detection_range} step="0.5" min="1" max="20"
                  onChange={e => setForm({ ...form, detection_range: parseFloat(e.target.value) })} />
              </div>
            </div>

            <div className="form-row" style={{ marginBottom: 12 }}>
              <div className="form-group">
                <label className="form-label">Face Confidence</label>
                <input type="number" value={form.face_confidence} step="0.05" min="0.1" max="1.0"
                  onChange={e => setForm({ ...form, face_confidence: parseFloat(e.target.value) })} />
              </div>
              <div className="form-group">
                <label className="form-label">Data Frequency (sec)</label>
                <input type="number" value={form.data_frequency} min="1" max="60"
                  onChange={e => setForm({ ...form, data_frequency: parseInt(e.target.value) })} />
              </div>
            </div>

            {/* Yaw / Pitch */}
            <div style={{ fontSize: 11, color: "var(--text2)", marginBottom: 6, textTransform: "uppercase", letterSpacing: ".06em" }}>Face Angle Range</div>
            <div className="form-row" style={{ marginBottom: 12 }}>
              <div className="form-group">
                <label className="form-label">Min Yaw</label>
                <input type="number" value={form.min_yaw} min="-90" max="0"
                  onChange={e => setForm({ ...form, min_yaw: parseInt(e.target.value) })} />
              </div>
              <div className="form-group">
                <label className="form-label">Max Yaw</label>
                <input type="number" value={form.max_yaw} min="0" max="90"
                  onChange={e => setForm({ ...form, max_yaw: parseInt(e.target.value) })} />
              </div>
            </div>
            <div className="form-row" style={{ marginBottom: 16 }}>
              <div className="form-group">
                <label className="form-label">Min Pitch</label>
                <input type="number" value={form.min_pitch} min="-90" max="0"
                  onChange={e => setForm({ ...form, min_pitch: parseInt(e.target.value) })} />
              </div>
              <div className="form-group">
                <label className="form-label">Max Pitch</label>
                <input type="number" value={form.max_pitch} min="0" max="90"
                  onChange={e => setForm({ ...form, max_pitch: parseInt(e.target.value) })} />
              </div>
            </div>

            {/* Checkboxes */}
            <div style={{ fontSize: 11, color: "var(--text2)", marginBottom: 8, textTransform: "uppercase", letterSpacing: ".06em" }}>Options</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[
                { key: "enabled", label: "Camera Enabled" },
                { key: "send_image", label: "Send Image with detection" },
              ].map(({ key, label }) => (
                <label key={key} style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 12 }}>
                  <input type="checkbox" checked={form[key]} onChange={e => setForm({ ...form, [key]: e.target.checked })}
                    style={{ width: 14, height: 14, accentColor: "var(--accent)" }} />
                  {label}
                </label>
              ))}
            </div>

            <div className="form-group" style={{ marginTop: 14 }}>
              <label className="form-label">Notes</label>
              <input type="text" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} placeholder="Optional notes..." />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
// ─── CAMERA CONFIG LIVE FEED (snapshot polling) ──────────────
// ─── LIVE PER-CAMERA HEAD-COUNT STATS (polls every 3s) ──────
function CameraLiveStats({ cameraId, compact }) {
  const [st, setSt] = useState(null);
  useEffect(() => {
    let active = true;
    const tick = async () => {
      const r = await fetchAPI(`/api/v1/cameras/${encodeURIComponent(cameraId)}/stats`);
      if (active && r && r.success) setSt(r);
    };
    tick();
    const t = setInterval(tick, 3000);
    return () => { active = false; clearInterval(t); };
  }, [cameraId]);
  if (!st) return null;
  const box = (label, val, color) => (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 6, padding: compact ? "2px 8px" : "4px 12px" }}>
      <span style={{ fontSize: compact ? 10 : 11, color: "var(--text2)" }}>{label}</span>
      <b style={{ fontSize: compact ? 11.5 : 14, color }}>{val}</b>
    </span>
  );
  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
      {box("Head count now", st.inside_count, st.inside_count > 0 ? "var(--green)" : "var(--text)")}
      {box("⬇ In events", st.in, "var(--green)")}
      {box("⬆ Out events", st.out, "var(--orange)")}
    </div>
  );
}

function ConfigLiveFeed({ cameraId }) {
  const timerRef = useRef(null);
  const [frameSrc, setFrameSrc] = useState("");
  const [offline, setOffline] = useState(false);
  const failRef = useRef(0);

  useEffect(() => {
    let active = true;
    failRef.current = 0;
    const fetchFrame = async () => {
      if (!active) return;
      try {
        // Try Render first (works when camera_processor pushes frames)
        const res = await fetch(`${API_BASE}/api/v1/cameras/${encodeURIComponent(cameraId)}/snapshot?_=${Date.now()}`);
        if (res.ok && res.status !== 204) {
          const blob = await res.blob();
          if (blob.size > 200) {
            failRef.current = 0;
            const objUrl = URL.createObjectURL(blob);
            setFrameSrc(prev => { if (prev) URL.revokeObjectURL(prev); return objUrl; });
            setOffline(false);
          } else { failRef.current += 1; }
        } else { failRef.current += 1; }
      } catch (_) { failRef.current += 1; }
      if (failRef.current >= 15) { setOffline(true); return; }
      if (active) timerRef.current = setTimeout(fetchFrame, 200);
    };
    fetchFrame();
    return () => { active = false; clearTimeout(timerRef.current); };
  }, [cameraId]);

  if (offline) return (
    <div style={{
      background: "#111", minHeight: 160, display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 8, color: "var(--text2)", fontSize: 12, padding: 16, textAlign: "center"
    }}>
      <span style={{ fontSize: 22 }}>📷</span>
      <span style={{ fontWeight: 600 }}>Live feed not available on cloud</span>
      <span style={{ fontSize: 11, color: "var(--text3)", maxWidth: 260 }}>
        Camera streams run on your local machine. Open the local dashboard for live feed.
      </span>
      <a href="http://localhost:5173" target="_blank" rel="noreferrer"
        style={{ marginTop: 6, padding: "5px 14px", background: "var(--accent)", color: "#fff", borderRadius: 4, fontSize: 11, textDecoration: "none" }}>
        Open Local Dashboard →
      </a>
    </div>
  );
  return frameSrc
    ? <img src={frameSrc} alt="Live Feed" style={{ width: "100%", display: "block", objectFit: "fill" }} />
    : <div style={{ background: "#111", minHeight: 160, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text2)", fontSize: 12 }}>Connecting...</div>;
}
// ─── LIVE FEED WITH ZONE OVERLAY ─────────────────────────────
function LiveFeedWithZone({ camera, onConfigure }) {
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const timerRef = useRef(null);
  const [frameSrc, setFrameSrc] = useState("");
  const [fps, setFps] = useState(0);
  const [offline, setOffline] = useState(false);
  const fpsCountRef = useRef(0);
  const fpsTimeRef = useRef(Date.now());
  const failRef = useRef(0);

  useEffect(() => {
    let active = true;
    failRef.current = 0;
    const fetchFrame = async () => {
      if (!active) return;
      try {
        const url = `${API_BASE}/api/v1/cameras/${encodeURIComponent(camera.id)}/snapshot?_=${Date.now()}`;
        const res = await fetch(url);
        if (res.ok && res.status !== 204) {
          const blob = await res.blob();
          if (blob.size > 200) {
            failRef.current = 0;
            const objUrl = URL.createObjectURL(blob);
            setFrameSrc(prev => { if (prev) URL.revokeObjectURL(prev); return objUrl; });
            setOffline(false);
            fpsCountRef.current += 1;
            const now = Date.now();
            const elapsed = (now - fpsTimeRef.current) / 1000;
            if (elapsed >= 2) {
              setFps(Math.round(fpsCountRef.current / elapsed));
              fpsCountRef.current = 0;
              fpsTimeRef.current = now;
            }
          } else { failRef.current += 1; }
        } else { failRef.current += 1; }
      } catch (_) { failRef.current += 1; }
      // Slow down polling when offline rather than stopping completely
      if (failRef.current >= 20) {
        setOffline(true);
        if (active) timerRef.current = setTimeout(fetchFrame, 3000);
      } else {
        if (active) timerRef.current = setTimeout(fetchFrame, 300);
      }
    };
    fetchFrame();
    return () => { active = false; clearTimeout(timerRef.current); };
  }, [camera.id]);

  // ── Zone / count-line overlay drawing (depends on camera type) ──
  const isHeadcount = camera.camera_type === "headcount";
  const showZoneOverlay = !isHeadcount;                       // frs/both/checkin/checkout
  const showLineOverlay = isHeadcount || camera.camera_type === "both";
  const drawZone = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;
    const W = canvas.width = img.offsetWidth || 640;
    const H = canvas.height = img.offsetHeight || 360;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, W, H);
    // count line (headcount / both cameras) — green
    if (showLineOverlay && camera.count_line && camera.count_line.length >= 4) {
      const [x1, y1, x2, y2] = camera.count_line;
      ctx.setLineDash([]);
      ctx.strokeStyle = "#22c55e"; ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(x1 / 100 * W, y1 / 100 * H);
      ctx.lineTo(x2 / 100 * W, y2 / 100 * H);
      ctx.stroke();
      [[x1, y1], [x2, y2]].forEach(([px, py]) => {
        ctx.beginPath(); ctx.arc(px / 100 * W, py / 100 * H, 5, 0, Math.PI * 2);
        ctx.fillStyle = "#22c55e"; ctx.fill();
      });
      ctx.fillStyle = "#22c55e"; ctx.font = "bold 12px monospace";
      ctx.fillText("COUNT LINE", 8, 20);
    }
    // detection zone (frs / both / legacy cameras) — blue
    const zone = camera.detection_zone;
    if (!showZoneOverlay || !zone || zone.length < 3) return;
    const pts = zone.map(p => [p[0] / 100 * W, p[1] / 100 * H]);
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    pts.slice(1).forEach(p => ctx.lineTo(p[0], p[1]));
    ctx.closePath();
    ctx.strokeStyle = "#4a9eff"; ctx.lineWidth = 2; ctx.setLineDash([8, 4]); ctx.stroke();
    ctx.fillStyle = "rgba(74,158,255,0.10)"; ctx.fill();
    pts.forEach((p, i) => {
      ctx.setLineDash([]);
      ctx.beginPath(); ctx.arc(p[0], p[1], 5, 0, Math.PI * 2);
      ctx.fillStyle = i === 0 ? "#3dba6e" : "#4a9eff"; ctx.fill();
    });
    ctx.setLineDash([]);
    ctx.fillStyle = "#4a9eff"; ctx.font = "bold 12px monospace";
    ctx.fillText("ZONE ACTIVE", 8, showLineOverlay ? 38 : 20);
  }, [camera.detection_zone, camera.count_line, showZoneOverlay, showLineOverlay]);

  useEffect(() => {
    drawZone();
    window.addEventListener("resize", drawZone);
    return () => window.removeEventListener("resize", drawZone);
  }, [drawZone, frameSrc]);

  return (
    <div style={{ position: "relative", background: "#000", lineHeight: 0 }}>
      <img ref={imgRef}
        src={frameSrc || ""}
        alt="Live Feed"
        style={{ width: "100%", display: "block", objectFit: "fill", minHeight: 200 }}
        onLoad={() => setTimeout(drawZone, 10)}
      />
      <canvas ref={canvasRef}
        style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none" }} />
      {/* FPS badge */}
      <div style={{
        position: "absolute", top: 8, right: 8, background: "rgba(0,0,0,.75)",
        padding: "2px 8px", borderRadius: 4, fontSize: 11, color: "#3dba6e", fontFamily: "monospace"
      }}>
        {fps > 0 ? `${fps} fps` : "connecting..."}
      </div>
      {(!camera.detection_zone || camera.detection_zone.length < 3) && (
        <div style={{
          position: "absolute", top: 8, left: 8, background: "rgba(0,0,0,.7)",
          padding: "3px 10px", borderRadius: 4, fontSize: 11, color: "var(--orange)"
        }}>
          ⚠ No zone — detecting full frame
        </div>
      )}
      {!frameSrc && (
        <div style={{
          position: "absolute", inset: 0, display: "flex", alignItems: "center",
          justifyContent: "center", color: "var(--text2)", fontSize: 12
        }}>
          Connecting to camera...
        </div>
      )}
    </div>
  );
}

// ─── CAMERA PULSE METER ──────────────────────────────────────
function CameraPulseMeter({ cameraId, visible }) {
  const [pulse, setPulse] = useState(null);

  useEffect(() => {
    if (!visible) { setPulse(null); return; }
    let active = true;
    const load = () => {
      if (!active) return;
      fetchAPI(`/api/v1/cameras/${encodeURIComponent(cameraId)}/pulse`).then(d => { if (active && d) setPulse(d); });
    };
    const t = setInterval(load, 5000);
    return () => { active = false; clearInterval(t); };
  }, [cameraId, visible]);

  if (!visible || !pulse) return null;

  const fpsColor = pulse.fps >= pulse.target_fps * 0.8 ? "var(--green)"
    : pulse.fps >= pulse.target_fps * 0.4 ? "var(--orange)" : "var(--red)";

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))",
      gap: 6,
      padding: "8px 0",
      borderTop: "1px solid var(--border)",
    }}>
      {/* FPS */}
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 9, color: "var(--text3)", textTransform: "uppercase", letterSpacing: ".06em" }}>FPS</div>
        <div style={{ fontSize: 20, fontWeight: 700, color: fpsColor, lineHeight: 1.2 }}>
          {pulse.fps.toFixed(1)}
        </div>
        <div style={{ fontSize: 9, color: "var(--text3)" }}>of {pulse.target_fps}</div>
        {/* Mini bar */}
        <div style={{ height: 3, background: "var(--surface2)", borderRadius: 2, marginTop: 3 }}>
          <div style={{ height: 3, borderRadius: 2, background: fpsColor, width: `${Math.min(100, (pulse.fps / pulse.target_fps) * 100)}%`, transition: "width .3s" }} />
        </div>
      </div>
      {/* Total Detections */}
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 9, color: "var(--text3)", textTransform: "uppercase", letterSpacing: ".06em" }}>Detections</div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text)", lineHeight: 1.2 }}>
          {pulse.total_detections}
        </div>
        <div style={{ fontSize: 9, color: "var(--text3)" }}>today</div>
      </div>
      {/* Known / Registered */}
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 9, color: "var(--text3)", textTransform: "uppercase", letterSpacing: ".06em" }}>Registered</div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "var(--green)", lineHeight: 1.2 }}>
          {pulse.known_count}
        </div>
        <div style={{ fontSize: 9, color: "var(--text3)" }}>{pulse.unique_known} unique</div>
      </div>
      {/* Unknown / Unregistered */}
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 9, color: "var(--text3)", textTransform: "uppercase", letterSpacing: ".06em" }}>Unregistered</div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "var(--orange)", lineHeight: 1.2 }}>
          {pulse.unknown_count}
        </div>
        <div style={{ fontSize: 9, color: "var(--text3)" }}>faces</div>
      </div>
      {/* Inside Now */}
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 9, color: "var(--text3)", textTransform: "uppercase", letterSpacing: ".06em" }}>Inside Now</div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "var(--accent)", lineHeight: 1.2 }}>
          {pulse.inside_now}
        </div>
        <div style={{ fontSize: 9, color: "var(--text3)" }}>persons</div>
      </div>
      {/* Zone Status */}
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 9, color: "var(--text3)", textTransform: "uppercase", letterSpacing: ".06em" }}>Zone</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: pulse.has_zone ? "var(--green)" : "var(--text3)", lineHeight: 1.4 }}>
          {pulse.has_zone ? "Active" : "None"}
        </div>
        <div style={{ fontSize: 9, color: "var(--text3)" }}>{pulse.running ? "Running" : "Stopped"}</div>
      </div>
    </div>
  );
}

// Time range options: label → how many history points to keep (poll every 3s)
const PULSE_RANGES = [
  { label: "30s",  points: 10  },
  { label: "1min", points: 20  },
  { label: "5min", points: 100 },
  { label: "15min",points: 300 },
];

function CameraPulseCard({ camera, rangePoints }) {
  const [pulse, setPulse] = useState(null);
  const [fpsHistory, setFpsHistory] = useState(new Array(rangePoints).fill(0));
  const [loading, setLoading] = useState(true);
  const [showDetails, setShowDetails] = useState(false);

  // When rangePoints changes, resize history buffer
  useEffect(() => {
    setFpsHistory(prev => {
      if (prev.length === rangePoints) return prev;
      if (rangePoints > prev.length) return [...new Array(rangePoints - prev.length).fill(0), ...prev];
      return prev.slice(prev.length - rangePoints);
    });
  }, [rangePoints]);

  useEffect(() => {
    let active = true;
    const fetchPulse = () => {
      fetchAPI(`/api/v1/cameras/${encodeURIComponent(camera.id)}/pulse?_=${Date.now()}`).then(d => {
        if (!active) return;
        if (d) {
          setPulse(d);
          setLoading(false);
          setFpsHistory(prev => {
            const buf = prev.length === rangePoints ? prev : prev.slice(prev.length - rangePoints);
            return [...buf.slice(1), d.fps];
          });
        }
      });
    };
    fetchPulse();
    const t = setInterval(fetchPulse, 3000);
    return () => { active = false; clearInterval(t); };
  }, [camera.id]);

  if (loading || !pulse) {
    return (
      <div className="pulse-card" style={{ opacity: 0.6, minHeight: 160, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: 12, color: "var(--text2)" }}>Loading pulse for {camera.name}…</div>
      </div>
    );
  }

  const isOnline = pulse.running && pulse.fps > 0;
  const fpsColor = !isOnline ? "var(--red)"
    : pulse.fps >= pulse.target_fps * 0.8 ? "var(--green)"
    : pulse.fps >= pulse.target_fps * 0.4 ? "var(--orange)" : "var(--red)";

  // Build SVG EKG path
  const svgW = 340, svgH = 60;
  const maxVal = Math.max(pulse.target_fps, 10);
  const pts = fpsHistory.map((val, idx) => {
    const x = (idx / (fpsHistory.length - 1)) * svgW;
    const y = svgH - 5 - (val / maxVal) * (svgH - 10);
    return [x, y];
  });
  let pathD = pts.length > 0 ? `M ${pts[0][0]} ${pts[0][1]}` : "";
  for (let i = 1; i < pts.length; i++) {
    const cpx = (pts[i - 1][0] + pts[i][0]) / 2;
    pathD += ` C ${cpx} ${pts[i-1][1]}, ${cpx} ${pts[i][1]}, ${pts[i][0]} ${pts[i][1]}`;
  }

  return (
    <div className="pulse-card">
      {/* Header */}
      <div className="pulse-card-header">
        <div>
          <div className="pulse-title">{camera.name}</div>
          <div className="pulse-subtitle">{camera.id}</div>
        </div>
        <div className="pulse-status-indicator">
          <div className={`status-dot ${isOnline ? "pulsing" : "flatline"}`} />
          <span style={{ color: isOnline ? "var(--green)" : "var(--red)", fontWeight: 500 }}>
            {isOnline ? "ONLINE" : "OFFLINE"}
          </span>
        </div>
      </div>

      {/* FPS readout + stats row */}
      <div className="pulse-readout-wrap">
        <div>
          <div className="pulse-fps-label">FPS Pulse</div>
          <div className="pulse-fps-val" style={{ color: fpsColor }}>{pulse.fps.toFixed(1)}</div>
          <div className="pulse-fps-target">of {pulse.target_fps}</div>
        </div>
        <div style={{ display: "flex", gap: 16, fontSize: 11, color: "var(--text2)", alignItems: "flex-end", paddingBottom: 4 }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: "var(--text)", lineHeight: 1 }}>{pulse.total_detections}</div>
            <div style={{ fontSize: 9, color: "var(--text3)", textTransform: "uppercase", letterSpacing: ".05em" }}>Detections</div>
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: "var(--green)", lineHeight: 1 }}>{pulse.known_count ?? 0}</div>
            <div style={{ fontSize: 9, color: "var(--text3)", textTransform: "uppercase", letterSpacing: ".05em" }}>Known</div>
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: "var(--orange)", lineHeight: 1 }}>{pulse.unknown_count ?? 0}</div>
            <div style={{ fontSize: 9, color: "var(--text3)", textTransform: "uppercase", letterSpacing: ".05em" }}>Unknown</div>
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: "var(--accent)", lineHeight: 1 }}>{pulse.inside_now ?? 0}</div>
            <div style={{ fontSize: 9, color: "var(--text3)", textTransform: "uppercase", letterSpacing: ".05em" }}>Inside</div>
          </div>
        </div>
      </div>

      {/* EKG Graph — NO video */}
      <div className="pulse-graph-box" style={{ height: 70 }}>
        <div className="pulse-graph-grid" />
        <svg width="100%" height="100%" viewBox={`0 0 ${svgW} ${svgH}`} style={{ display: "block", overflow: "visible" }}>
          <defs>
            <filter id={`glow-${camera.id}`} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="1.5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          {isOnline ? (
            <path d={pathD} fill="none" stroke={fpsColor} strokeWidth="2"
              filter={`url(#glow-${camera.id})`} style={{ transition: "d 0.3s ease" }} />
          ) : (
            <line x1="0" y1={svgH - 5} x2={svgW} y2={svgH - 5}
              stroke="var(--red)" strokeWidth="2" filter={`url(#glow-${camera.id})`} />
          )}
        </svg>
      </div>

      {/* AI FPS sub-stat */}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--text3)", padding: "4px 2px 6px" }}>
        <span>AI proc: <b style={{ color: "var(--text2)" }}>{((pulse.rec_fps ?? 0) || 0).toFixed(1)} fps</b></span>
        <span>Zone: <b style={{ color: pulse.has_zone ? "var(--green)" : "var(--text3)" }}>{pulse.has_zone ? "Active" : "None"}</b></span>
        <span>Type: <b style={{ color: "var(--text2)" }}>{camera.camera_type}</b></span>
      </div>

      {/* Expandable details */}
      <button className="pulse-details-btn" onClick={() => setShowDetails(!showDetails)}>
        {showDetails ? "▲ Hide Details" : "▼ Show Camera Details"}
      </button>
      {showDetails && (
        <div className="pulse-details-grid">
          <div className="pulse-detail-item" style={{ gridColumn: "span 2" }}>
            <span className="pulse-detail-lbl">RTSP URL</span>
            <span className="pulse-detail-val" style={{ fontFamily: "monospace", wordBreak: "break-all" }}>{camera.rtsp_url}</span>
          </div>
          <div className="pulse-detail-item">
            <span className="pulse-detail-lbl">Camera Type</span>
            <span className="pulse-detail-val" style={{ textTransform: "capitalize" }}>{camera.camera_type}</span>
          </div>
          <div className="pulse-detail-item">
            <span className="pulse-detail-lbl">Target FPS</span>
            <span className="pulse-detail-val">{camera.fps} FPS</span>
          </div>
          <div className="pulse-detail-item">
            <span className="pulse-detail-lbl">Face Confidence</span>
            <span className="pulse-detail-val">{camera.face_confidence}</span>
          </div>
          <div className="pulse-detail-item">
            <span className="pulse-detail-lbl">Detection Range</span>
            <span className="pulse-detail-val">{camera.detection_range}m</span>
          </div>
          <div className="pulse-detail-item">
            <span className="pulse-detail-lbl">Yaw Range</span>
            <span className="pulse-detail-val">[{camera.min_yaw}°, {camera.max_yaw}°]</span>
          </div>
          <div className="pulse-detail-item">
            <span className="pulse-detail-lbl">Pitch Range</span>
            <span className="pulse-detail-val">[{camera.min_pitch}°, {camera.max_pitch}°]</span>
          </div>
          <div className="pulse-detail-item">
            <span className="pulse-detail-lbl">Zone</span>
            <span className="pulse-detail-val">
              {camera.detection_zone?.length >= 3 ? `✓ ${camera.detection_zone.length} points` : "No zone"}
            </span>
          </div>
          <div className="pulse-detail-item">
            <span className="pulse-detail-lbl">Status</span>
            <span className="pulse-detail-val">{camera.enabled ? "Enabled" : "Disabled"}</span>
          </div>
          {camera.notes && (
            <div className="pulse-detail-item" style={{ gridColumn: "span 2" }}>
              <span className="pulse-detail-lbl">Notes</span>
              <span className="pulse-detail-val">{camera.notes}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CameraPulsePage() {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [rangeIdx, setRangeIdx] = useState(0); // default: 30s

  const load = () => {
    fetchAPI("/api/v1/cameras").then(d => {
      if (d && d.cameras) setCameras(d.cameras);
      setLoading(false);
    });
  };

  useEffect(() => { load(); }, []);

  const selectedRange = PULSE_RANGES[rangeIdx];

  return (
    <div>
      <div className="toolbar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        {/* Time range selector */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 11, color: "var(--text3)", textTransform: "uppercase", letterSpacing: ".06em" }}>Window:</span>
          {PULSE_RANGES.map((r, i) => (
            <button
              key={r.label}
              onClick={() => setRangeIdx(i)}
              style={{
                fontSize: 11, padding: "3px 10px", borderRadius: 4, border: "none", cursor: "pointer",
                background: i === rangeIdx ? "var(--accent)" : "var(--surface2)",
                color: i === rangeIdx ? "#fff" : "var(--text2)",
                fontWeight: i === rangeIdx ? 700 : 400,
                transition: "all .15s"
              }}
            >
              {r.label}
            </button>
          ))}
          <span style={{ fontSize: 10, color: "var(--text3)", marginLeft: 4 }}>
            (polling every 3s)
          </span>
        </div>
        <button className="btn btn-sm" onClick={load}><Icon path={icons.refresh} size={12} /> Refresh</button>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 40, color: "var(--text2)" }}>Loading cameras…</div>
      ) : cameras.length === 0 ? (
        <div className="empty">No cameras found. Add cameras under the Cameras tab.</div>
      ) : (
        <div className="pulse-grid">
          {cameras.map(cam => (
            <CameraPulseCard key={cam.id} camera={cam} rangePoints={selectedRange.points} />
          ))}
        </div>
      )}
    </div>
  );
}

function CamerasPage() {
  const [cameras, setCameras] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ id: "", name: "", rtsp_url: "", camera_type: "frs", fps: 30, enabled: true, notes: "", room_id: "" });
  const [saving, setSaving] = useState(false);
  const [liveCamera, setLiveCamera] = useState(null);
  const [configCamera, setConfigCamera] = useState(null);
  const [pulseCam, setPulseCam] = useState(null);
  // FIX: moved these two hooks BEFORE the early return — React rules of hooks
  const [cameraMode, setCameraMode] = useState("3mp");
  const [modeLoading, setModeLoading] = useState(false);

  const load = () => fetchAPI("/api/v1/cameras").then(d => d && setCameras(d.cameras || []));
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, []);

  // Load camera mode on mount
  useEffect(() => {
    fetchAPI("/api/v1/camera-mode").then(d => {
      if (d && d.camera_mode) setCameraMode(d.camera_mode);
    });
  }, []);

  if (configCamera) {
    return <CameraConfigPage
      camera={configCamera}
      onBack={() => setConfigCamera(null)}
      onSave={() => { load(); setConfigCamera(null); }}
    />;
  }

  const switchMode = async (mode) => {
    if (!window.confirm(`Switch to ${mode.toUpperCase()} mode? Cameras will restart.`)) return;
    setModeLoading(true);
    const res = await fetchAPI("/api/v1/camera-mode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ camera_mode: mode })
    });
    if (res && res.success) {
      setCameraMode(mode);
      setTimeout(load, 2000);  // reload after cameras restart
    }
    setModeLoading(false);
  };

  const openAdd = () => { setEditing(null); setForm({ id: "", name: "", rtsp_url: "", camera_type: "frs", fps: 30, enabled: true, notes: "", room_id: "" }); setShowModal(true); };
  const openEdit = (cam) => { setEditing(cam.id); setForm({ ...cam }); setShowModal(true); };

  const save = async () => {
    if (!form.id || !form.name || !form.rtsp_url) return;
    setSaving(true);
    let res;
    if (editing) res = await fetchAPI(`/api/v1/cameras/${encodeURIComponent(editing)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    else res = await fetchAPI("/api/v1/cameras", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    if (!res || !res.success) { alert(`Failed to ${editing ? "update" : "add"} camera — check the server console.`); setSaving(false); return; }
    await load(); setSaving(false); setShowModal(false);
  };

  const remove = async (id) => { if (!window.confirm("Delete camera?")) return; const res = await fetchAPI(`/api/v1/cameras/${encodeURIComponent(id)}`, { method: "DELETE" }); if (!res || !res.success) alert("Failed to delete camera — check the server console."); load(); };
  const toggle = async (cam) => { await fetchAPI(`/api/v1/cameras/${encodeURIComponent(cam.id)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: !cam.enabled }) }); load(); };
  const toggleRun = async (cam) => { await fetchAPI(`/api/v1/cameras/${encodeURIComponent(cam.id)}/${cam.running ? "stop" : "start"}`, { method: "POST" }); setTimeout(load, 500); };

  return (
    <div>
      <div className="toolbar" style={{ flexWrap: "wrap", gap: 8 }}>
        {/* Camera Mode Switcher */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginRight: 12 }}>
          <span style={{ fontSize: 11, color: "var(--text2)", fontWeight: 600 }}>MODE:</span>
          {["8mp", "3mp", "both"].map(mode => (
            <button
              key={mode}
              className={`btn btn-sm ${cameraMode === mode ? "btn-primary" : ""}`}
              style={{
                fontSize: 11,
                padding: "4px 10px",
                background: cameraMode === mode ? "var(--accent)" : "var(--surface)",
                color: cameraMode === mode ? "#fff" : "var(--text)",
                border: `1px solid ${cameraMode === mode ? "var(--accent)" : "var(--border)"}`,
                opacity: modeLoading ? 0.5 : 1
              }}
              onClick={() => switchMode(mode)}
              disabled={modeLoading}
            >
              {mode === "8mp" ? "🎬 8MP" : mode === "3mp" ? "📹 3MP" : "🔄 Both"}
            </button>
          ))}
          {modeLoading && <span style={{ fontSize: 10, color: "var(--text3)" }}>Restarting...</span>}
        </div>

        <button className="btn btn-sm btn-primary" style={{ marginLeft: "auto" }} onClick={openAdd}>
          <Icon path={icons.plus} size={12} /> Add Camera
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Type</th><th>RTSP URL</th><th>FPS</th><th>Enabled</th><th>Running</th><th>Actions</th></tr></thead>
          <tbody>
            {cameras.map((cam, i) => (
              <Fragment key={i}>
                <tr>
                  <td style={{ fontFamily: "monospace", fontSize: 11 }}>{cam.id}</td>
                  <td style={{ fontWeight: 500 }}>{cam.name}</td>
                  <td><span className={`badge ${cam.camera_type === "checkin" ? "badge-green" : cam.camera_type === "checkout" ? "badge-orange" : "badge-blue"}`}>{cam.camera_type}</span></td>
                  <td style={{ fontFamily: "monospace", fontSize: 11, color: "var(--text2)", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{cam.rtsp_url}</td>
                  <td style={{ fontFamily: "monospace" }}>{cam.fps}</td>
                  <td><button className={`badge ${cam.enabled ? "badge-green" : "badge-grey"}`} style={{ cursor: "pointer", border: "none" }} onClick={() => toggle(cam)}>{cam.enabled ? "On" : "Off"}</button></td>
                  <td><button className={`badge ${cam.running ? "badge-green" : "badge-red"}`} style={{ cursor: "pointer", border: "none" }} onClick={() => toggleRun(cam)}>{cam.running ? "▶ Live" : "■ Stop"}</button></td>
                  <td>
                    <div style={{ display: "flex", gap: 4 }}>
                      <button className="btn btn-sm btn-icon" title="Settings" style={{ color: "var(--text2)" }}
                        onClick={() => setConfigCamera(cam)}>⚙</button>
                      <button className="btn btn-sm btn-icon" title="Pulse Stats" style={{ color: pulseCam === cam.id ? "var(--green)" : "var(--text2)" }} onClick={() => setPulseCam(pulseCam === cam.id ? null : cam.id)}>
                        <Icon path={icons.dashboard} size={12} />
                      </button>
                      <button className="btn btn-sm btn-icon" title="Live Feed" style={{ color: "var(--accent)" }} onClick={() => setLiveCamera(cam)}><Icon path={icons.eye} size={12} /></button>
                      <button className="btn btn-sm btn-icon" onClick={() => openEdit(cam)}><Icon path={icons.edit} size={12} /></button>
                      <button className="btn btn-sm btn-icon" style={{ color: "var(--red)" }} onClick={() => remove(cam.id)}><Icon path={icons.trash} size={12} /></button>
                    </div>
                  </td>
                </tr>
                {pulseCam === cam.id && (
                  <tr key={`pulse-${cam.id}`}>
                    <td colSpan={8} style={{ padding: "4px 12px 8px", background: "var(--surface2)" }}>
                      <CameraPulseMeter cameraId={cam.id} visible={true} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {cameras.length === 0 && <tr><td colSpan={8}><div className="empty">No cameras added</div></td></tr>}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && setShowModal(false)}>
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">{editing ? "Edit Camera" : "Add Camera"}</span>
              <button className="btn btn-sm btn-icon" onClick={() => setShowModal(false)}><Icon path={icons.x} size={13} /></button>
            </div>
            <div className="modal-body">
              <div className="form-row">
                <div className="form-group"><label className="form-label">Camera ID *</label><input type="text" value={form.id} onChange={e => setForm({ ...form, id: e.target.value })} placeholder="cam-001" disabled={!!editing} /></div>
                <div className="form-group"><label className="form-label">Name *</label><input type="text" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Main Entrance" /></div>
              </div>
              <div className="form-group"><label className="form-label">RTSP URL *</label><input type="text" value={form.rtsp_url} onChange={e => setForm({ ...form, rtsp_url: e.target.value })} placeholder="rtsp://user:pass@ip:554/live" /></div>
              <div className="form-row">
                <div className="form-group"><label className="form-label">Type</label>
                  <select value={form.camera_type} onChange={e => setForm({ ...form, camera_type: e.target.value })}>
                    <option value="frs">FRS Only (Zone)</option>
                    <option value="headcount">Head Count Only (Line)</option>
                    <option value="both">FRS + Head Count (Zone + Line)</option>
                    <option value="checkin">Entry Check-in (legacy)</option>
                    <option value="checkout">Exit Check-out (legacy)</option>
                  </select>
                </div>
                <div className="form-group"><label className="form-label">Room ID (for head count)</label>
                  <input type="text" value={form.room_id || ""} onChange={e => setForm({ ...form, room_id: e.target.value })} placeholder="e.g. Room A" />
                </div>
                <div className="form-group"><label className="form-label">FPS</label>
                  <select value={form.fps} onChange={e => setForm({ ...form, fps: parseInt(e.target.value) })}>
                    <option value={1}>1 fps</option><option value={2}>2 fps</option><option value={5}>5 fps</option>
                    <option value={10}>10 fps</option><option value={15}>15 fps</option><option value={30}>30 fps</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary" disabled={saving || !form.id || !form.name || !form.rtsp_url} onClick={save}>{saving ? "Saving..." : editing ? "Update" : "Add Camera"}</button>
            </div>
          </div>
        </div>
      )}

      {liveCamera && (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && setLiveCamera(null)}>
          <div className="modal" style={{ maxWidth: 720 }}>
            <div className="modal-header">
              <span className="modal-title">Live Feed — {liveCamera.name}</span>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span className={`badge ${liveCamera.running ? "badge-green" : "badge-red"}`}>{liveCamera.running ? "● LIVE" : "■ OFFLINE"}</span>
                <button className="btn btn-sm btn-icon" onClick={() => setLiveCamera(null)}><Icon path={icons.x} size={13} /></button>
              </div>
            </div>
            {/* Live feed with zone overlay */}
            <LiveFeedWithZone camera={liveCamera} onConfigure={() => { const c = liveCamera; setLiveCamera(null); setEditing(c); setForm(c); setShowModal(true); }} />
            <div style={{ padding: "10px 16px", borderTop: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ fontSize: 11, color: "var(--text2)", display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
                <span>ID: <b style={{ color: "var(--text)" }}>{liveCamera.id}</b></span>
                <span>Type: <b style={{ color: liveCamera.camera_type === "headcount" ? "var(--orange)" : liveCamera.camera_type === "both" ? "var(--accent)" : "var(--green)" }}>
                  {liveCamera.camera_type === "frs" ? "FRS (detection zone)" : liveCamera.camera_type === "headcount" ? "Head Count (count line)" : liveCamera.camera_type === "both" ? "FRS + Head Count (zone + line)" : liveCamera.camera_type}
                </b></span>
                <span>FPS: <b style={{ color: "var(--text)" }}>{liveCamera.fps}</b></span>
                <span>Face Conf: <b style={{ color: "var(--text)" }}>{liveCamera.face_confidence || 0.6}</b></span>
                {liveCamera.camera_type !== "headcount" && liveCamera.detection_zone?.length >= 3 && (
                  <span style={{ color: "var(--accent)" }}>✓ Zone: {liveCamera.detection_zone.length} points</span>
                )}
                {(liveCamera.camera_type === "headcount" || liveCamera.camera_type === "both") && liveCamera.count_line?.length >= 4 && (
                  <span style={{ color: "var(--green)" }}>✓ Count line</span>
                )}
                {(liveCamera.camera_type === "headcount" || liveCamera.camera_type === "both") && !liveCamera.count_line?.length && (
                  <span style={{ color: "var(--orange)" }}>⚠ No count line drawn</span>
                )}
                <button className="btn btn-sm" style={{ marginLeft: "auto" }} onClick={() => { const c = liveCamera; setLiveCamera(null); setEditing(c); setForm(c); setShowModal(true); }}>
                  ⚙ Configure
                </button>
              </div>
              {(liveCamera.camera_type === "headcount" || liveCamera.camera_type === "both") && (
                <CameraLiveStats cameraId={liveCamera.id} compact />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── MAIN APP ────────────────────────────────────────────────
export default function App() {
  const [page, setPage] = useState("dashboard");
  const [stats, setStats] = useState(null);
  const [serverOk, setServerOk] = useState(null);
  const [health, setHealth] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const loadData = useCallback(async () => {
    const [s, h] = await Promise.all([
      fetchAPI("/api/v1/dashboard"),
      fetchAPI("/api/v1/health")
    ]);
    if (s) setStats(s);
    if (h) { setHealth(h); setServerOk(true); } else setServerOk(false);
  }, []);

  useEffect(() => {
    loadData();
    const t = setInterval(loadData, 30000);
    // ── Keep Render awake — ping health every 8 minutes ──────
    // Render free tier sleeps after 15 min inactivity → 30s cold start
    const keepAlive = setInterval(() => {
      fetch(`${API_BASE}/api/v1/health`).catch(() => { });
    }, 8 * 60 * 1000);
    return () => { clearInterval(t); clearInterval(keepAlive); };
  }, [loadData]);

  const nav = [
    { id: "dashboard", label: "My Dashboards", icon: icons.dashboard, top: true },
    { id: "entry", label: "Entry exit", icon: icons.entry, sub: true },
    { id: "unregistered", label: "unregistered", icon: icons.unknown, sub: true },
    { id: "tracking", label: "Global Tracking", icon: icons.humans, sub: true },
    { id: "compare", label: "Kloudspot vs FRS", icon: icons.compare, sub: true },
    { id: "pulse", label: "Camera Pulse", icon: icons.dashboard, sub: true },
    { id: "humans", label: "Humans", icon: icons.humans, top: true },
    { id: "cameras", label: "Cameras", icon: icons.camera, top: true },
    { id: "settings", label: "Settings", icon: icons.settings, top: true },
  ];

  const titles = {
    dashboard: "My Dashboards",
    entry: "Entry exit",
    unregistered: "unregistered",
    compare: "Kloudspot vs FRS Model Comparison",
    pulse: "Camera Pulse Monitor",
    humans: "Humans",
    cameras: "Cameras",
    settings: "System Settings",
  };

  return (
    <>
      <style>{styles}</style>
      <div className="app">
        {/* Mobile overlay */}
        <div className={`sidebar-overlay ${sidebarOpen ? "open" : ""}`} onClick={() => setSidebarOpen(false)} />

        {/* Sidebar */}
        <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
          <div className="sidebar-brand">
            <div className="brand-logo">FRS</div>
            <div className="brand-name">FRD System</div>
          </div>
          <nav className="nav">
            {nav.map(n => (
              <div key={n.id}
                className={`nav-item ${n.sub ? "sub" : ""} ${page === n.id ? "active" : ""}`}
                onClick={() => { setPage(n.id); setSidebarOpen(false); }}>
                <Icon path={n.icon} size={14} />
                {n.label}
              </div>
            ))}
          </nav>
          <div className="sidebar-footer">
            <div className="status-row">
              <div className={`status-dot ${serverOk === false ? "off" : ""}`} />
              <span>{serverOk === null ? "Connecting..." : serverOk ? "Server Online" : "Server Offline"}</span>
            </div>
            {health?.camera_fps && Object.entries(health.camera_fps).map(([cid, fps]) => (
              <div key={cid} style={{ fontSize: 10, color: "var(--green)", marginTop: 2 }}>
                {cid}: {fps > 0 ? `${fps} fps` : "connected"}
              </div>
            ))}
          </div>
        </aside>

        {/* Main */}
        <div className="main">
          {/* Mobile topbar */}
          <div className="mobile-topbar">
            <button className="btn btn-sm btn-icon" onClick={() => setSidebarOpen(o => !o)}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
            <span style={{ fontSize: 13, fontWeight: 500 }}>{titles[page]}</span>
            <button className="btn btn-sm btn-icon" style={{ marginLeft: "auto" }} onClick={loadData}>
              <Icon path={icons.refresh} size={13} />
            </button>
          </div>

          {/* Topbar */}
          <div className="topbar">
            <div className="topbar-breadcrumb">
              <Icon path={icons.home} size={12} />
              <span>Home</span>
              <Icon path={icons.chevron} size={11} />
              <span style={{ color: "var(--text)" }}>{titles[page]}</span>
            </div>
            <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
              <div className="status-row" style={{ fontSize: 11 }}>
                <div className={`status-dot ${serverOk === false ? "off" : ""}`} />
                <span style={{ color: "var(--text2)" }}>{serverOk ? "Online" : "Offline"}</span>
              </div>
              <button className="btn btn-sm" onClick={loadData}><Icon path={icons.refresh} size={12} /></button>
            </div>
          </div>

          {/* Page header */}
          <div className="content">
            <div className="page-header">
              <div className="page-title">
                <span className="page-title-icon"><Icon path={nav.find(n => n.id === page)?.icon || icons.dashboard} size={16} /></span>
                {titles[page]}
              </div>
            </div>

            {page === "dashboard" && <DashboardPage onNavigate={setPage} />}
            {page === "entry" && <EntryExitPage />}
            {page === "unregistered" && <UnregisteredPage />}
            {page === "tracking" && <GlobalTrackingPage onOpenCameras={() => setPage("cameras")} />}
            {page === "compare" && <ComparisonPage />}
            {page === "pulse" && <CameraPulsePage />}
            {page === "humans" && <HumansPage />}
            {page === "cameras" && <CamerasPage />}
            {page === "settings" && <SettingsPage />}
          </div>
        </div>
      </div>
    </>
  );
}
