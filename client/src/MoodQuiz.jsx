import React, { useState } from 'react'

const QUESTIONS = [
  { id: 'energy', text: 'How energetic do you feel right now?' },
  { id: 'stress', text: 'How stressed or anxious are you right now?' },
  { id: 'hunger', text: 'How hungry are you?' },
]

export default function MoodQuiz({ onFinish }) {
  const [answers, setAnswers] = useState({})

  function setAnswer(id, value) {
    setAnswers(a => ({ ...a, [id]: value }))
  }
  function submit() {
    const vals = Object.values(answers).map(Number)
    const score = vals.length ? Math.round((vals.reduce((x,y)=>x+y,0)/ (vals.length*5) )*100) : 50
    onFinish({ score, answers })
  }

  return (
    <div>
      <h3>Quick mood check (30s)</h3>
      {QUESTIONS.map(q => (
        <div key={q.id} style={{ marginBottom: 8 }}>
          <p>{q.text}</p>
          <div>
            {[1,2,3,4,5].map(v =>
              <label key={v} style={{marginRight:8}}>
                <input type="radio" name={q.id} value={v} onChange={() => setAnswer(q.id, v)} /> {v}
              </label>
            )}
          </div>
        </div>
      ))}
      <button onClick={submit}>Save mood</button>
    </div>
  )
}
