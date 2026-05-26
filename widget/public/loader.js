/**
 * Concierge Widget Loader — /widget.js
 *
 * Usage: <script src="/widget.js" data-widget-id="your-widget-id"></script>
 *
 * Behaviour:
 * 1. Reads data-widget-id from the script element
 * 2. POSTs to /api/widget/token with the current page origin
 * 3. On success: creates an iframe pointing to /widget/embed.html
 * 4. On failure: logs silently, does NOT break the host page
 *
 * Security: CORS is defense-in-depth. The real auth is the signed token
 * returned by /api/widget/token, which validates origin server-side.
 */
;(function () {
  'use strict'

  var script = document.currentScript || (function () {
    var scripts = document.getElementsByTagName('script')
    return scripts[scripts.length - 1]
  })()

  var widgetId = script && script.getAttribute('data-widget-id')
  if (!widgetId) {
    console.warn('[Concierge] data-widget-id not set on script tag')
    return
  }

  var apiBase = script.getAttribute('data-api-base') || window.location.origin

  fetch(apiBase + '/api/widget/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ widget_id: widgetId }),
  })
    .then(function (res) {
      if (!res.ok) {
        console.warn('[Concierge] Token exchange failed:', res.status)
        return null
      }
      return res.json()
    })
    .then(function (data) {
      if (!data || !data.token) return

      var src = apiBase
        + '/widget/embed.html'
        + '?token=' + encodeURIComponent(data.token)
        + '&conversation_id=' + encodeURIComponent(data.conversation_id)
        + '&widget_id=' + encodeURIComponent(widgetId)

      var iframe = document.createElement('iframe')
      iframe.src = src
      iframe.title = 'Concierge Chat'
      iframe.setAttribute('allow', 'microphone')
      iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms')
      Object.assign(iframe.style, {
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        width: '380px',
        height: '540px',
        border: 'none',
        borderRadius: '16px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
        zIndex: '2147483647',
      })
      document.body.appendChild(iframe)
    })
    .catch(function (err) {
      console.warn('[Concierge] Widget load error:', err)
    })
})()
