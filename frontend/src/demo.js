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
        objective: `Explain and apply the core ${t} idea introduced in lecture ${l}.`,
        prerequisites: [`Basics of ${t} from the earlier part of module ${m}`],
        body_markdown:
          `## Why this matters\n${t} is a practical skill, and this lecture builds the first ` +
          `building block you need for ${form.level}-level work.\n\n` +
          `### Core concept\n${t} works best when you understand the fundamentals before ` +
          `jumping to tools. This lecture introduces the core vocabulary and a mental model.\n\n` +
          `### Step-by-step walkthrough\n1. Define the goal behind your ${t} task.\n` +
          `2. Break it into three small steps.\n3. Try the simplest version first.\n` +
          `4. Measure the result and refine once.\n\n` +
          `### Common misconceptions\n- Skipping foundations and copying solutions blindly\n` +
          `- Optimising too early instead of getting a baseline working\n` +
          `- Not writing down what you tried and what happened\n\n` +
          `### Hands-on practice\nTake a tiny ${t} task you already have and apply the four ` +
          `steps above to it. Record the result.\n`,
        key_points: [
          `Core vocabulary of ${t} (module ${m})`,
          'Mental model: goal → attempt → feedback → refine',
          'Worked example you can replicate in 15 minutes',
          'Top 3 beginner mistakes and how to avoid them',
        ],
        practice: [
          `Summarise this ${t} lecture in three sentences.`,
          `Apply one idea from it to a small ${t} project of your own.`,
        ],
        takeaways: [
          `You understand the key ${t} building block of module ${m}.`,
          'You have a repeatable four-step practice loop.',
          'You can recognise the top beginner mistakes.',
        ],
        further_reading: [
          `Official documentation and beginner guides for ${t}`,
          `Community tutorials and forums discussing ${t}`,
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
    description: `A ${form.level}-level, ${form.modules_count}-module hands-on course on ${t} for ${form.audience}. (Demo version — connect the backend for Gemini-generated, course-specific content, narrated audio and slide videos.)`,
    prerequisites: [`No prior ${t} experience required — a general interest is enough.`],
    objectives: [
      `Explain the core ideas behind ${t}`,
      `Apply ${t} basics to a small real project`,
      `Recognise and avoid the most common ${t} mistakes`,
    ],
    generated_by: 'template',
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
