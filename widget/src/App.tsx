/**
 * App.tsx — widget iframe root.
 * Reads token + widget_id from URL params set by loader.js, fetches theme, renders chat.
 */
import { useEffect, useState } from 'react'
import ChatWindow from './ChatWindow'
import { WidgetConfig, fetchConfig, initSession } from './api'

const DEFAULT_CONFIG: WidgetConfig = {
  greeting: 'Hi! How can I help you?',
  accent_colour: '#3B82F6',
}

export default function App() {
  const [config, setConfig] = useState<WidgetConfig>(DEFAULT_CONFIG)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    const conversationId = params.get('conversation_id')
    const widgetId = params.get('widget_id')

    if (!token || !conversationId) {
      // Missing token — show error state, don't crash host page
      setReady(true)
      return
    }

    initSession(token, conversationId)

    if (widgetId) {
      fetchConfig(widgetId)
        .then(setConfig)
        .catch(() => { /* keep defaults */ })
        .finally(() => setReady(true))
    } else {
      setReady(true)
    }
  }, [])

  if (!ready) {
    return <div style={{ padding: 16, color: '#6B7280', fontSize: '0.875rem' }}>Loading…</div>
  }

  return <ChatWindow greeting={config.greeting} accentColour={config.accent_colour} />
}
