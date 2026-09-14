import { useEffect, useState } from 'react'
import { demoCourse, gradeLocal, loadDemo, saveDemo, speak, uid } from './demo.js'

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

function CertificateView({ cert }) {
  return (
    <div id="print-area">
      <div className="certificate">
        <div className="seal">🎓</div>
        <h2>Medash Academy</h2>
        <p className="kicker">CERTIFICATE OF COMPLETION</p>
        <p className="line">This certifies that</p>
        <h1>{cert.student_name}</h1>
        <p className="line">has successfully completed all quizzes of the course</p>
        <h3>{cert.course_topic}</h3>
        <p className="line">Grade <b>{cert.grade}</b> · Overall score {cert.completion_percent}%</p>
        <p className="line">Issued {new Date(cert.issued_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}</p>
        <p className="line small">Certificate ID: {cert.id}</p>
        <button onClick={() => window.print()}>🖨 Print certificate</button>
      </div>
    </div>
  )
}

function Quiz({ courseId, lecture, enrollment, quizIds, online, onResult }) {
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [notice, setNotice] = useState(null)
  if (!lecture.quiz?.questions?.length) return <p>No quiz for this lecture.</p>
  async function submit() {
    setNotice(null)
    setResult(null)
    const ordered = lecture.quiz.questions.map((_, i) => answers[i] ?? -1)
    if (enrollment && !enrollment._demo) {
      const r = await api(`/api/enrollments/${enrollment.id}/lectures/${lecture.id}/grade`, {
        method: 'POST', body: JSON.stringify({ answers: ordered }),
      })
      setResult(r.result)
      setNotice(r.passed ? `Passed (≥${r.pass_percent}%) — recorded for certificate.` : `Not passed yet (need ≥${r.pass_percent}%). Review and retake.`)
      onResult(r)
    } else if (enrollment && enrollment._demo) {
      const local = gradeLocal(lecture, ordered)
      setResult(local)
      setNotice(local.percent >= 70 ? 'Passed (≥70%) — recorded for certificate (demo).' : 'Not passed yet (need ≥70%). Review and retake.')
      onResult({ passed: local.percent >= 70, percent: local.percent })
    } else {
      try {
        setResult(await api(`/api/courses/${courseId}/lectures/${lecture.id}/grade`, {
          method: 'POST', body: JSON.stringify({ answers: ordered }),
        }))
        if (quizIds.length) setNotice('Practice mode — enroll above to earn a certificate.')
      } catch {
        setResult(gradeLocal(lecture, ordered))  // backend offline -> grade in browser
      }
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
      {notice && <p className={notice.startsWith('Not') ? 'bad' : 'ok'}>{notice}</p>}
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

const PASS = 70
const enrollKey = (cid) => `medash-enroll-${cid}`
const demoKey = (cid) => `medash-demo-progress-${cid}`

function CourseView({ course, online }) {
  const [modIdx, setModIdx] = useState(0)
  const [lecIdx, setLecIdx] = useState(0)
  const [tab, setTab] = useState('lecture')
  const mod = course.modules[modIdx]
  const lec = mod?.lectures[lecIdx]
  const [enrollment, setEnrollment] = useState(null)
  const [name, setName] = useState('')
  const [enrolling, setEnrolling] = useState(false)
  const [enrollErr, setEnrollErr] = useState('')

  const quizIds = course.modules.flatMap((m) => m.lectures.filter((l) => l.quiz?.questions?.length).map((l) => l.id))
  const cert = enrollment?.certificate || null
  const passedCount = quizIds.filter((lid) => enrollment?.passed_lectures?.includes(lid)).length
  const pct = quizIds.length ? Math.round((100 * passedCount) / quizIds.length) : 0

  useEffect(() => { setLecIdx(0); setTab('lecture') }, [modIdx, course.id])

  useEffect(() => {
    try {
      const e = JSON.parse(localStorage.getItem(enrollKey(course.id)) || 'null')
      setEnrollment(e)
    } catch { setEnrollment(null) }
  }, [course.id])

  useEffect(() => {
    if (online && enrollment && !enrollment._demo) {
      api(`/api/enrollments/${enrollment.id}`).then(setEnrollment).catch(() => {})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online, course.id, enrollment?.id])

  function persistEnrollment(e) {
    setEnrollment(e)
    if (e) localStorage.setItem(enrollKey(course.id), JSON.stringify(e))
    else localStorage.removeItem(enrollKey(course.id))
  }

  async function enrollNow(e) {
    e.preventDefault()
    setEnrollErr('')
    if (!name.trim()) return
    setEnrolling(true)
    try {
      let enr
      if (online) {
        enr = await api('/api/enroll', { method: 'POST', body: JSON.stringify({ course_id: course.id, student_name: name.trim() }) })
      } else {
        const map = JSON.parse(localStorage.getItem(demoKey(course.id)) || '{}')
        enr = {
          id: 'demo-' + uid(), course_id: course.id, student_name: name.trim(),
          enrolled_at: new Date().toISOString(), passed_lectures: quizIds.filter((lid) => (map[lid] || 0) >= PASS),
          scores: {}, certificate: null, _demo: true,
        }
      }
      persistEnrollment(enr)
    } catch (err) { setEnrollErr(String(err).replace(/^Error: ?/, '')) }
    finally { setEnrolling(false) }
  }

  function leaveCourse() {
    persistEnrollment(null)
    if (!online) localStorage.removeItem(demoKey(course.id))
  }

  function onResult(r) {
    if (enrollment?._demo && r) {
      const map = JSON.parse(localStorage.getItem(demoKey(course.id)) || '{}')
      map[lec.id] = Math.max(map[lec.id] || 0, r.percent || 0)
      localStorage.setItem(demoKey(course.id), JSON.stringify(map))
      const passed = quizIds.filter((lid) => (map[lid] || 0) >= PASS)
      let certificate = enrollment.certificate
      if (!certificate && quizIds.length && passed.length === quizIds.length) {
        const avg = Math.round(quizIds.reduce((s, lid) => s + (map[lid] || 0), 0) / quizIds.length)
        certificate = {
          id: 'demo-' + uid(), student_name: enrollment.student_name, course_id: course.id, course_topic: course.topic,
          issued_at: new Date().toISOString(), completion_percent: avg,
          grade: avg >= 90 ? 'Distinction' : avg >= 80 ? 'Merit' : 'Pass',
        }
      }
      const updated = { ...enrollment, passed_lectures: passed, certificate }
      persistEnrollment(updated)
      if (certificate) setTab('certificate')
    } else if (online && r && r.issued) {
      api(`/api/enrollments/${enrollment.id}`).then((enr) => { persistEnrollment(enr); if (enr.certificate) setTab('certificate') }).catch(() => {})
    }
  }

  if (!mod || !lec) return <p>Empty course.</p>
  const tabs = ['lecture', 'video', 'audio', 'quiz', ...(cert ? ['certificate'] : [])]
  return (
    <div className="card">
      <h2>{course.topic}
        <span className={`badge ${course.generated_by === 'gemini' ? 'live' : 'tpl'}`}>
          {course.generated_by === 'gemini' ? 'AI-generated by Gemini' : 'Template (offline stub)'}
        </span>
        {cert && <span className="badge live">🎓 Certified</span>}
      </h2>
      <p>{course.description}</p>
      {!!course.prerequisites?.length && (
        <p><b>Prerequisites:</b> {course.prerequisites.join(' · ')}</p>
      )}
      {!!course.objectives?.length && (
        <ul>{course.objectives.map((o, i) => <li key={i}>{o}</li>)}</ul>
      )}

      {!enrollment ? (
        <form className="box enroll" onSubmit={enrollNow}>
          <b>Enroll to earn your certificate</b>
          <label>Student name
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Doe" minLength={1} maxLength={120} required />
          </label>
          <button disabled={enrolling}>{enrolling ? 'Enrolling…' : 'Enroll now'}</button>
          <span className="hint">A certificate is issued automatically when you pass every quiz (≥{PASS}% each).</span>
          {enrollErr && <p className="error">{enrollErr}</p>}
        </form>
      ) : (
        <div className="box prog">
          <b>Enrolled as {enrollment.student_name}</b>
          <div className="bar"><div style={{ width: pct + '%' }} /></div>
          <span>{passedCount}/{quizIds.length} quizzes passed{pct === 100 ? ' — all complete!' : ` (pass ≥${PASS}% each)`}</span>
          {cert
            ? <button onClick={() => setTab('certificate')}>View certificate 🎓</button>
            : <button className="ghost" onClick={leaveCourse}>Leave course / enroll as different student</button>}
        </div>
      )}

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
          {lec.objective && <p className="objective"><b>Objective:</b> {lec.objective}</p>}
          {!!lec.prerequisites?.length && (
            <p className="objective"><b>Before this lecture:</b> {lec.prerequisites.join(' · ')}</p>
          )}
          <div className="tabs">
            {tabs.map((t) => (
              <button key={t} className={tab === t ? 'active' : 'ghost'} onClick={() => setTab(t)}>{t}</button>
            ))}
          </div>
          {tab === 'lecture' && (
            <>
              <pre className="lecture">{lec.body_markdown}</pre>
              {!!lec.key_points?.length && (
                <div><h4>Key points</h4><ul>{lec.key_points.map((k, i) => <li key={i}>{k}</li>)}</ul></div>
              )}
              {!!lec.practice?.length && (
                <div className="box"><h4>Practice</h4><ol>{lec.practice.map((p, i) => <li key={i}>{p}</li>)}</ol></div>
              )}
              {!!lec.takeaways?.length && (
                <div className="box"><h4>Takeaways</h4><ul className="tick">{lec.takeaways.map((t, i) => <li key={i}>{t}</li>)}</ul></div>
              )}
              {!!lec.further_reading?.length && (
                <div className="box"><h4>Further reading</h4><ul>{lec.further_reading.map((f, i) => <li key={i}>{f}</li>)}</ul></div>
              )}
            </>
          )}
          {tab === 'video' && (lec.video_url
            ? <video controls src={lec.video_url} /> : <p>No video rendered (ffmpeg unavailable) — slides + audio below still work.</p>)}
          {tab === 'audio' && (lec.audio_url
            ? <audio controls src={lec.audio_url} />
            : <div>
                <p>No audio file for this lecture{lec._demo ? ' (demo course).' : '.'}</p>
                <button onClick={() => speak(`${lec.title}. ${lec.body_markdown}`)}>🔊 Read aloud in browser</button>
              </div>)}
          {tab === 'quiz' && <Quiz courseId={course.id} lecture={lec} enrollment={enrollment} quizIds={quizIds} online={online} onResult={onResult} />}
          {tab === 'certificate' && cert && <CertificateView cert={cert} />}
          {!!lec.slides?.length && tab !== 'quiz' && tab !== 'certificate' && (
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
      {active && <CourseView course={active} online={!!health} />}
    </div>
  )
}
