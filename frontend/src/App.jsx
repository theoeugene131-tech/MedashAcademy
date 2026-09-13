import { useEffect, useState } from 'react'
import { demoCourse, gradeLocal, loadDemo, saveDemo, speak } from './demo.js'

const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

async function api(path, opts) {
  const r = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

function Builder({ onCreated, busy, setBusy }) {
  const [form, setForm] = useState({
    topic: 'Python for Data Analysis',
    level: 'beginner',
    audience: 'self-paced learners',
    modules_count: 3,
    lectures_per_module: 3,
    questions_per_quiz: 4,
    include_audio: true,
    include_video: true,
    include_quiz: true,
  })
  const [err, setErr] = useState('')
  const [demo, setDemo] = useState(false)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  async function submit(e) {
    e.preventDefault()
    setErr('')
    setDemo(false)
    setBusy(true)
    try {
      const course = await api('/api/generate', { method: 'POST', body: JSON.stringify(form) })
      onCreated(course, false)
    } catch {
      // Backend unreachable (e.g. static Vercel hosting) -> full-featured local demo.
      const course = demoCourse(form)
      setDemo(true)
      onCreated(course, true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      <h2>1. Generate a course</h2>
      <form onSubmit={submit}>
        <label>Topic<input value={form.topic} onChange={(e) => set('topic', e.target.value)} required minLength={3} /></label>
        <div className="row">
          <label>Level
            <select value={form.level} onChange={(e) => set('level', e.target.value)}>
              <option>beginner</option><option>intermediate</option><option>advanced</option>
            </select>
          </label>
          <label>Audience<input value={form.audience} onChange={(e) => set('audience', e.target.value)} /></label>
        </div>
        <div className="row">
          <label>Modules (1-6)<input type="number" min={1} max={6} value={form.modules_count} onChange={(e) => set('modules_count', +e.target.value)} /></label>
          <label>Lectures / module (1-5)<input type="number" min={1} max={5} value={form.lectures_per_module} onChange={(e) => set('lectures_per_module', +e.target.value)} /></label>
        </div>
        <div className="row">
          <label>Questions / quiz (2-8)<input type="number" min={2} max={8} value={form.questions_per_quiz} onChange={(e) => set('questions_per_quiz', +e.target.value)} /></label>
          <label>Media
            <div>
              <label><input type="checkbox" checked={form.include_audio} onChange={(e) => set('include_audio', e.target.checked)} style={{width:'auto'}} /> Audio narration</label>
              <label><input type="checkbox" checked={form.include_video} onChange={(e) => set('include_video', e.target.checked)} style={{width:'auto'}} /> Slide video</label>
              <label><input type="checkbox" checked={form.include_quiz} onChange={(e) => set('include_quiz', e.target.checked)} style={{width:'auto'}} /> Quizzes</label>
            </div>
          </label>
        </div>
        <button disabled={busy}>{busy ? 'Generating lectures + audio + video…' : 'Generate full course'}</button>
      </form>
      {err && <p className="error">{err}</p>}
      {demo && <p className="badge">Demo mode — generated in your browser. Connect the backend (VITE_API_URL) for Gemini text, narrated audio files and slide videos.</p>}
      {busy && <p>Large courses take 1–3 min (TTS + video rendering). Gemini produces text first, then local media.</p>}
    </div>
  )
}

function Quiz({ courseId, lecture }) {
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  if (!lecture.quiz?.questions?.length) return <p>No quiz for this lecture.</p>
  async function submit() {
    const ordered = lecture.quiz.questions.map((_, i) => answers[i] ?? -1)
    try {
      const r = await api(`/api/courses/${courseId}/lectures/${lecture.id}/grade`, {
        method: 'POST', body: JSON.stringify({ answers: ordered }),
      })
      setResult(r)
    } catch {
      setResult(gradeLocal(lecture, ordered))  // backend offline -> grade in browser
    }
  }
  return (
    <div>
      {lecture.quiz.questions.map((q, i) => (
        <div key={i} className="quiz-q">
          <b>Q{i + 1}. {q.q}</b>
          {q.options.map((opt, oi) => (
            <label key={oi}>
              <input type="radio" name={`q${i}`} checked={answers[i] === oi}
                onChange={() => setAnswers((a) => ({ ...a, [i]: oi }))} style={{ width: 'auto', marginRight: 8 }} />
              {opt}
            </label>
          ))}
        </div>
      ))}
      <button onClick={submit}>Submit quiz</button>
      {result && (
        <div>
          <h3>Score: {result.score}/{result.total} ({result.percent}%)</h3>
          {result.details.map((d, i) => (
            <div key={i} className={`result ${d.is_correct ? 'ok' : 'bad'}`}>
              <b>Q{i + 1} {d.is_correct ? '✓' : '✗'}</b> — {d.question}<br />
              Correct: {d.options[d.correct]}<br />
              <i>{d.explanation}</i>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function CourseView({ course }) {
  const [modIdx, setModIdx] = useState(0)
  const [lecIdx, setLecIdx] = useState(0)
  const [tab, setTab] = useState('lecture')
  const mod = course.modules[modIdx]
  const lec = mod?.lectures[lecIdx]
  useEffect(() => { setLecIdx(0); setTab('lecture') }, [modIdx, course.id])

  if (!mod || !lec) return <p>Empty course.</p>
  return (
    <div className="card">
      <h2>{course.topic}</h2>
      <p>{course.description}</p>
      <div className="layout">
        <div className="nav">
          {course.modules.map((m, mi) => (
            <div key={m.id}>
              <button className={mi === modIdx ? 'active' : ''} onClick={() => setModIdx(mi)}>
                M{mi + 1}. {m.title}
              </button>
              {mi === modIdx && m.lectures.map((l, li) => (
                <button key={l.id} className={li === lecIdx ? 'active' : 'ghost'}
                  style={{ marginLeft: 12 }} onClick={() => setLecIdx(li)}>
                  {mi + 1}.{li + 1} {l.title}
                </button>
              ))}
            </div>
          ))}
        </div>
        <div>
          <h3>{lec.title}</h3>
          <div className="tabs">
            {['lecture', 'video', 'audio', 'quiz'].map((t) => (
              <button key={t} className={tab === t ? 'active' : 'ghost'} onClick={() => setTab(t)}>{t}</button>
            ))}
          </div>
          {tab === 'lecture' && (
            <>
              <pre className="lecture">{lec.body_markdown}</pre>
              {!!lec.key_points?.length && (
                <ul>{lec.key_points.map((k, i) => <li key={i}>{k}</li>)}</ul>
              )}
            </>
          )}
          {tab === 'video' && (lec.video_url
            ? <video controls src={lec.video_url} /> : <p>No video rendered (ffmpeg/moviepy unavailable) — slides + audio below still work.</p>)}
          {tab === 'audio' && (lec.audio_url
            ? <audio controls src={lec.audio_url} />
            : <div>
                <p>No audio file for this lecture{lec._demo ? ' (demo course).' : '.'}</p>
                <button onClick={() => speak(`${lec.title}. ${lec.body_markdown}`)}>🔊 Read aloud in browser</button>
              </div>)}
          {tab === 'quiz' && <Quiz courseId={course.id} lecture={lec} />}
          {!!lec.slides?.length && tab !== 'quiz' && (
            <div><h4>Slides</h4><div className="slides">
              {lec.slides.map((s) => <img key={s} src={s} loading="lazy" />)}
            </div></div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [courses, setCourses] = useState([])
  const [active, setActive] = useState(null)
  const [busy, setBusy] = useState(false)
  const [health, setHealth] = useState(null)

  async function refresh() {
    try {
      const [h, list] = await Promise.all([api('/api/health'), api('/api/courses')])
      setHealth(h); setCourses(list)
      if (list.length && !active) setActive(list[0])
    } catch {
      const demo = loadDemo()  // backend offline -> courses from this browser
      setCourses(demo)
      if (demo.length && !active) setActive(demo[0])
    }
  }
  useEffect(() => { refresh() }, [])

  function handleCreated(course, isDemo) {
    setCourses((l) => {
      const next = [course, ...l]
      if (isDemo) saveDemo(next)
      return next
    })
    setActive(course)
  }

  return (
    <div className="app">
      <header className="top">
        <h1>Medash Academy</h1>
        <span className="badge">{health ? (health.gemini_configured ? 'Gemini live' : 'Mock mode (no key)') : 'Demo mode (no backend)'}</span>
      </header>
      <Builder onCreated={handleCreated} busy={busy} setBusy={setBusy} />
      <div className="card">
        <h2>2. Your courses ({courses.length})</h2>
        {courses.map((c) => (
          <button key={c.id} className={active?.id === c.id ? '' : 'ghost'}
            style={{ marginRight: 8, marginBottom: 8 }} onClick={() => setActive(c)}>
            {c.topic} ({c.modules.length} mods)
          </button>
        ))}
        {!courses.length && <p>No courses yet — generate one above. It works offline in demo mode; connect the backend for Gemini AI + audio/video files.</p>}
      </div>
      {active && <CourseView course={active} />}
    </div>
  )
}
