/**
 * Widget API client — all requests carry the session token in Authorization header.
 * token is set once at init; tenant_id is never sent from the client.
 */

const API_BASE = (window as Window & { CONCIERGE_API?: string }).CONCIERGE_API ?? ''

let _token: string | null = null
let _conversationId: string | null = null

export function initSession(token: string, conversationId: string): void {
  _token = token
  _conversationId = conversationId
}

export function getConversationId(): string | null {
  return _conversationId
}

function authHeaders(): HeadersInit {
  if (!_token) throw new Error('Widget session not initialized')
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${_token}`,
  }
}

export interface ChatResponse {
  reply: string
  conversation_id: string
}

export async function sendMessage(message: string): Promise<ChatResponse> {
  if (!_conversationId) throw new Error('No conversation ID')
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ conversation_id: _conversationId, message }),
  })
  if (res.status === 401) throw new Error('Session expired — please refresh')
  if (!res.ok) throw new Error(`Chat error ${res.status}`)
  return res.json() as Promise<ChatResponse>
}

export interface WidgetConfig {
  greeting: string
  accent_colour: string
}

export async function fetchConfig(widgetId: string): Promise<WidgetConfig> {
  const res = await fetch(`${API_BASE}/api/widget/${encodeURIComponent(widgetId)}/config`)
  if (!res.ok) throw new Error('Failed to load widget config')
  return res.json() as Promise<WidgetConfig>
}
