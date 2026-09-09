import { useState, useRef, useCallback, useEffect } from 'react'
import './index.css'

const API_BASE = 'http://localhost:8000'
const WS_BASE = 'ws://localhost:8000'

const CATEGORY_COLORS = {
  'Two Wheelers (White Plate)': '#00f5d4',
  'Two Wheelers (Taxi)': '#00e5ff',
  'Car/Jeep/Van': '#4361ee',
  'Autorickshaw - 3wh': '#ff6b35',
  'Bus - City Bus (BMTC)': '#f72585',
  'Bus - (KSRTC) BUS': '#e040fb',
  'Bus - Other Buses': '#d500f9',
  'Bus - Mini/Midi Bus': '#aa00ff',
  'Goods Auto/LCV': '#ffab40',
  'Other Trucks': '#ff6e40',
  'Agricultural Tractor/Trailer': '#8d6e63',
  'Cycle': '#69f0ae',
  'PBS': '#84ffff',
  'Others': '#90a4ae',
}

function formatDuration(sec) {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

function formatSize(bytes) {
  if (bytes > 1e9) return (bytes / 1e9).toFixed(2) + ' GB'
  return (bytes / 1e6).toFixed(1) + ' MB'
}

export default function App() {
  const [phase, setPhase] = useState('upload') // upload | config | processing | completed
  const [dragOver, setDragOver] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [fileInfo, setFileInfo] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [frame, setFrame] = useState(null)
  const [stats, setStats] = useState({
    progress: 0,
    frameIdx: 0,
    totalFrames: 0,
    time: '00:00:00',
    activeTracks: 0,
    totalCounted: 0,
    categoryCounts: {},
  })
  const [completed, setCompleted] = useState(false)
  const [config, setConfig] = useState({
    start_time: '08:00:00',
    frame_stride: 3,
    config: 'site_15_veerasandra.yaml',
    template: 'Site 15 - Veerasandra_Main_Road.xlsx',
  })

  const fileInputRef = useRef(null)
  const wsRef = useRef(null)

  // ===== UPLOAD =====
  const handleFile = useCallback(async (file) => {
    if (!file) return
    setPhase('uploading')
    setUploadProgress(0)

    const formData = new FormData()
    formData.append('file', file)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/api/upload`)

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        setUploadProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      if (xhr.status === 200) {
        const data = JSON.parse(xhr.responseText)
        setJobId(data.job_id)
        setFileInfo({
          name: data.filename,
          size: data.size_mb + ' MB',
          resolution: data.resolution,
          fps: data.fps,
          duration: data.duration_min + ' min',
          totalFrames: data.total_frames,
        })
        setPhase('config')
      }
    }
    xhr.onerror = () => alert('Upload failed. Is the server running?')
    xhr.send(formData)
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const onDragOver = useCallback((e) => { e.preventDefault(); setDragOver(true) }, [])
  const onDragLeave = useCallback(() => setDragOver(false), [])

  // ===== PROCESSING VIA WEBSOCKET =====
  const startProcessing = useCallback(() => {
    if (!jobId) return
    setPhase('processing')
    setFrame(null)
    setCompleted(false)

    const ws = new WebSocket(`${WS_BASE}/ws/process/${jobId}`)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify(config))
    }

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)

      if (msg.type === 'init') {
        setStats(prev => ({
          ...prev,
          totalFrames: msg.total_frames,
        }))
      }

      if (msg.type === 'frame') {
        setFrame(`data:image/jpeg;base64,${msg.frame}`)
        setStats({
          progress: msg.progress,
          frameIdx: msg.frame_idx,
          totalFrames: msg.total_frames,
          time: msg.time,
          activeTracks: msg.active_tracks,
          totalCounted: msg.total_counted,
          categoryCounts: msg.category_counts || {},
        })
      }

      if (msg.type === 'complete') {
        setCompleted(true)
        setPhase('completed')
        setStats(prev => ({
          ...prev,
          progress: 100,
          totalCounted: msg.total_counted,
          categoryCounts: msg.category_counts || {},
        }))
      }

      if (msg.type === 'error') {
        alert('Processing error: ' + msg.message)
      }
    }

    ws.onclose = () => {
      if (!completed) {
        // Connection closed prematurely
      }
    }

    ws.onerror = () => {
      alert('WebSocket connection failed. Is the server running?')
    }
  }, [jobId, config, completed])

  const resetAll = useCallback(() => {
    if (wsRef.current) wsRef.current.close()
    setPhase('upload')
    setFileInfo(null)
    setJobId(null)
    setFrame(null)
    setStats({ progress: 0, frameIdx: 0, totalFrames: 0, time: '00:00:00', activeTracks: 0, totalCounted: 0, categoryCounts: {} })
    setCompleted(false)
    setUploadProgress(0)
  }, [])

  // Category list sorted by count
  const sortedCategories = Object.entries(stats.categoryCounts)
    .sort((a, b) => b[1] - a[1])

  const totalVehicles = Object.values(stats.categoryCounts).reduce((a, b) => a + b, 0)

  return (
    <div className="app-container">
      <div className="bg-glow" />

      {/* Navbar */}
      <nav className="navbar">
        <div className="nav-brand">
          <div className="nav-brand-icon">🚦</div>
          Traffic AI Pipeline
        </div>
        <div className="nav-status">
          <div className={`status-dot ${phase === 'processing' ? 'processing' : phase === 'completed' ? '' : 'idle'}`} />
          {phase === 'upload' || phase === 'uploading' ? 'Ready' :
           phase === 'config' ? 'Video Loaded' :
           phase === 'processing' ? `Processing ${stats.progress.toFixed(1)}%` :
           'Completed'}
        </div>
        {phase !== 'upload' && phase !== 'uploading' && (
          <button className="new-upload-btn" onClick={resetAll}>
            ⟳ New Upload
          </button>
        )}
      </nav>

      <div className="main-content">

        {/* ===== UPLOAD PHASE ===== */}
        {(phase === 'upload' || phase === 'uploading') && (
          <div className="upload-section fade-in">
            <div className="upload-hero-text">
              <h1>Traffic Video Analysis</h1>
              <p>Upload your traffic survey video and watch the AI count, classify, and track every vehicle in real-time. Supports up to 5-hour recordings.</p>
            </div>

            <div
              className={`upload-zone ${dragOver ? 'dragover' : ''}`}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="upload-icon">📹</div>
              <h3>Drop your video here</h3>
              <p>or click to browse — supports .avi, .mp4, .mkv, .mov</p>
              <button className="browse-btn" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click() }}>
                Browse Files
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="video/*,.avi,.mp4,.mkv,.mov"
                style={{ display: 'none' }}
                onChange={(e) => handleFile(e.target.files[0])}
              />
            </div>

            {phase === 'uploading' && (
              <div className="upload-progress fade-in">
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                  Uploading... {uploadProgress}%
                </span>
                <div className="upload-progress-bar">
                  <div className="upload-progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
                </div>
              </div>
            )}
          </div>
        )}

        {/* ===== CONFIG PHASE ===== */}
        {phase === 'config' && fileInfo && (
          <div className="fade-in">
            <div className="file-info">
              <div className="icon">🎬</div>
              <div className="file-info-details">
                <h3>{fileInfo.name}</h3>
                <p>{fileInfo.resolution} • {fileInfo.fps} fps • {fileInfo.duration} • {fileInfo.totalFrames.toLocaleString()} frames • {fileInfo.size}</p>
              </div>
            </div>

            <div className="config-bar">
              <div>
                <label>Start Time</label><br/>
                <input
                  type="time"
                  step="1"
                  value={config.start_time}
                  onChange={e => setConfig(c => ({ ...c, start_time: e.target.value }))}
                />
              </div>
              <div>
                <label>Frame Stride</label><br/>
                <select value={config.frame_stride} onChange={e => setConfig(c => ({ ...c, frame_stride: parseInt(e.target.value) }))}>
                  <option value="1">Every frame (slow)</option>
                  <option value="2">Every 2nd frame</option>
                  <option value="3">Every 3rd frame (recommended)</option>
                  <option value="5">Every 5th frame (fast)</option>
                </select>
              </div>
              <div>
                <label>Site Config</label><br/>
                <select value={config.config} onChange={e => setConfig(c => ({ ...c, config: e.target.value }))}>
                  <option value="site_15_veerasandra.yaml">Site 15 - Veerasandra</option>
                  <option value="auto">Auto-detect</option>
                </select>
              </div>
              <button className="start-btn" onClick={startProcessing}>
                ▶ Start Processing
              </button>
            </div>

            <div className="video-container" style={{ maxWidth: 800, margin: '0 auto' }}>
              <div className="video-placeholder">
                <div className="icon">🖥️</div>
                <span>Live preview will appear here once processing starts</span>
              </div>
            </div>
          </div>
        )}

        {/* ===== PROCESSING + COMPLETED PHASES ===== */}
        {(phase === 'processing' || phase === 'completed') && (
          <div className="fade-in">

            {phase === 'completed' && (
              <div className="completed-banner">
                <div className="icon">✅</div>
                <div>
                  <h3>Processing Complete</h3>
                  <p>Counted {stats.totalCounted.toLocaleString()} vehicles across {sortedCategories.length} categories</p>
                </div>
              </div>
            )}

            <div className="dashboard">
              {/* Left: Video + Progress */}
              <div className="video-panel">
                <div className="video-container">
                  {frame ? (
                    <img src={frame} alt="Live processed frame" />
                  ) : (
                    <div className="video-placeholder">
                      <div className="icon">⏳</div>
                      <span>Initializing pipeline...</span>
                    </div>
                  )}
                </div>

                <div>
                  <div className="pipeline-progress">
                    <div className="pipeline-progress-fill" style={{ width: `${stats.progress}%` }} />
                  </div>
                  <div className="progress-info">
                    <span>Frame {stats.frameIdx.toLocaleString()} / {stats.totalFrames.toLocaleString()}</span>
                    <span>{stats.time}</span>
                    <span>{stats.progress.toFixed(1)}%</span>
                  </div>
                </div>

                {phase === 'completed' && (
                  <div className="download-actions">
                    <a className="dl-btn primary" href={`${API_BASE}/api/download/${jobId}`} download>
                      📊 Download Excel Report
                    </a>
                    <a className="dl-btn secondary" href={`${API_BASE}/api/download-video/${jobId}`} download>
                      🎥 Download Debug Video
                    </a>
                  </div>
                )}
              </div>

              {/* Right: Stats sidebar */}
              <div className="stats-panel">
                <div className="stats-card">
                  <h4>Live Statistics</h4>
                  <div className="stat-grid">
                    <div className="stat-item">
                      <div className="stat-value">{stats.totalCounted.toLocaleString()}</div>
                      <div className="stat-label">Total Vehicles</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-value">{stats.activeTracks}</div>
                      <div className="stat-label">Active Tracks</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-value">{stats.time}</div>
                      <div className="stat-label">Video Time</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-value">{stats.progress.toFixed(1)}%</div>
                      <div className="stat-label">Progress</div>
                    </div>
                  </div>
                </div>

                <div className="stats-card">
                  <h4>Vehicle Categories ({sortedCategories.length})</h4>
                  <div className="category-list">
                    {sortedCategories.length === 0 ? (
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: 20 }}>
                        Waiting for first detections...
                      </div>
                    ) : (
                      sortedCategories.map(([name, count]) => (
                        <div className="category-row" key={name}>
                          <span className="cat-name">
                            <span className="cat-dot" style={{ background: CATEGORY_COLORS[name] || '#888' }} />
                            {name}
                          </span>
                          <span className="cat-count">{count.toLocaleString()}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {fileInfo && (
                  <div className="stats-card" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    <h4>Source</h4>
                    <p><strong>File:</strong> {fileInfo.name}</p>
                    <p><strong>Resolution:</strong> {fileInfo.resolution}</p>
                    <p><strong>Duration:</strong> {fileInfo.duration}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
