import { FormEvent, useEffect, useRef, useState } from 'react'
import { sendMessage } from './api'

interface Message {
  role: 'user' | 'agent'
  text: string
}

interface Props {
  greeting: string
  accentColour: string
}

export default function ChatWindow({ greeting, accentColour }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'agent', text: greeting },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setError(null)
    setMessages((prev) => [...prev, { role: 'user', text }])
    setLoading(true)
    try {
      const { reply } = await sendMessage(text)
      setMessages((prev) => [...prev, { role: 'agent', text: reply }])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', fontFamily: 'system-ui, sans-serif' }}>
      {/* Header */}
      <div style={{ background: accentColour, color: '#fff', padding: '12px 16px', fontWeight: 600, fontSize: '0.95rem' }}>
        Chat with us
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {messages.map((m, i) => (
          <div
            key={i}
            style={{
              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
              background: m.role === 'user' ? accentColour : '#F3F4F6',
              color: m.role === 'user' ? '#fff' : '#111',
              borderRadius: '12px',
              padding: '8px 12px',
              maxWidth: '80%',
              fontSize: '0.875rem',
            }}
          >
            {m.text}
          </div>
        ))}
        {loading && (
          <div style={{ alignSelf: 'flex-start', color: '#9CA3AF', fontSize: '0.8rem' }}>Typing…</div>
        )}
        {error && (
          <div style={{ alignSelf: 'center', color: '#EF4444', fontSize: '0.8rem' }}>{error}</div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} style={{ display: 'flex', borderTop: '1px solid #E5E7EB', padding: '8px' }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          disabled={loading}
          style={{ flex: 1, border: '1px solid #D1D5DB', borderRadius: '8px', padding: '8px 12px', fontSize: '0.875rem', outline: 'none' }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{ marginLeft: '8px', background: accentColour, color: '#fff', border: 'none', borderRadius: '8px', padding: '8px 16px', cursor: 'pointer', fontSize: '0.875rem' }}
        >
          Send
        </button>
      </form>
    </div>
  )
}
