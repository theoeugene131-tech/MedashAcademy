// Client-side demo fallback: mirrors backend/app/ai_generator.py::_mock_course
// so the Vercel-hosted frontend is fully usable before the backend is deployed.
export function uid() {
  return Math.random().toString(36).slice(2, 10)
}

export function demoCourse(form) {
  const t = (form.topic || 'Untitled').trim()
  const cid = uid() + Date.now().toString(36)
  const modules = []
  for (let m = 1; m <= form.modules_count; m++) {
    const lectures = []
    for (let l = 1; l <= form.lectures_per_module; l++) {
      const questions = []
      if (form.include_quiz) {
        for (let q = 1; q <= form.questions_per_quiz; q++) {
          questions.push({
            q: `In the context of ${t} (module ${m}, lecture ${l}), which statement is most accurate? (Q${q})`,
            options: [
              `Core principle of ${t} applied correctly`,
              `A common misconception about ${t}`,
              'An unrelated fact',
              'The opposite of best practice',
            ],
            answer_index: 0,
            explanation: `The first option reflects the key idea taught in lecture ${l} of module ${m}.`,
          })
        }
      }
      lectures.push({
        id: `${cid}-m${m}l${l}-${uid()}`,
        title: `${t}: Module ${m} Lecture ${l}`,
        body_markdown:
          `## Lecture ${m}.${l} — ${t}\n\n` +
          `This lecture covers a key building block of **${t}** for ${form.level} learners.\n\n` +
          `### 1. The big idea\n${t} works best when you understand the fundamentals before ` +
          `jumping to tools. We introduce the core vocabulary, a mental model, and where ` +
          `this lecture fits in the module.\n\n` +
          `### 2. Worked example\nImagine applying ${t} to a small real project: define the goal, ` +
          `break it into 3 steps, try the simplest version first, then measure and iterate. ` +
          `That loop — goal, attempt, feedback, refine — is the pattern behind every module in this course.\n\n` +
          `### 3. Common mistakes\n- Skipping foundations and copying solutions blindly\n` +
          `- Optimising too early instead of getting a baseline working\n` +
          `- Not writing down what you tried and what happened\n\n` +
          `### 4. Try it yourself\n1. Summarise this lecture in 3 sentences.\n` +
          `2. Apply one idea from it to your own ${t} project.\n3. Take the quiz below to check understanding.\n`,
        key_points: [
          `Core vocabulary of ${t} (module ${m})`,
          'Mental model: goal → attempt → feedback → refine',
          'Worked example you can replicate in 15 minutes',
          'Top 3 beginner mistakes and how to avoid them',
        ],
        duration_min: 5,
        audio_url: null,
        video_url: null,
        slides: [],
        quiz: { questions },
        _demo: true,
      })
    }
    modules.push({
      id: `${cid}-m${m}-${uid()}`,
      title: `Module ${m}: ${t} foundations (${m}/${form.modules_count})`,
      objective: `By the end of module ${m}, you can explain and apply core ${t} concepts.`,
      lectures,
    })
  }
  return {
    id: cid,
    topic: t,
    level: form.level,
    audience: form.audience,
    description: `A ${form.level}-level, ${form.modules_count}-module hands-on course on ${t} for ${form.audience}. (Demo version — connect the backend for Gemini text, narrated audio and slide videos.)`,
    created_at: new Date().toISOString(),
    modules,
    _demo: true,
  }
}

export function gradeLocal(lecture, answers) {
  const questions = lecture.quiz?.questions || []
  const details = []
  let score = 0
  questions.forEach((q, i) => {
    const picked = i < answers.length ? answers[i] : -1
    const is_correct = picked === q.answer_index
    if (is_correct) score++
    details.push({
      question: q.q, picked, correct: q.answer_index, is_correct,
      explanation: q.explanation, options: q.options,
    })
  })
  const total = questions.length
  return { score, total, percent: total ? Math.round((100 * score) / total * 10) / 10 : 0, details }
}

// In-browser narration via Web Speech API (demo-mode audio).
export function speak(text) {
  try {
    speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text.slice(0, 4000))
    u.lang = 'en-US'
    speechSynthesis.speak(u)
  } catch { /* unsupported */ }
}

const KEY = 'medash-academy-demo-courses'
export function loadDemo() {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]') } catch { return [] }
}
export function saveDemo(courses) {
  try { localStorage.setItem(KEY, JSON.stringify(courses.slice(0, 20))) } catch { /* full/blocked */ }
}
