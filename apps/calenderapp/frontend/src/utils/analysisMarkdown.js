function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function sanitizeUrl(url) {
  const value = String(url || '').trim()
  if (!value) return '#'
  if (/^(https?:|mailto:)/i.test(value)) return value
  return '#'
}

function renderInline(text) {
  const codeTokens = []
  const pushCodeToken = (match, code) => {
    const token = `__CODE_TOKEN_${codeTokens.length}__`
    codeTokens.push(`<code>${escapeHtml(code)}</code>`)
    return token
  }

  let html = escapeHtml(text)
    .replace(/`([^`]+)`/g, pushCodeToken)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, url) => {
      const safeUrl = sanitizeUrl(url)
      return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`
    })
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
    .replace(/_([^_\n]+)_/g, '<em>$1</em>')

  codeTokens.forEach((tokenHtml, index) => {
    html = html.replace(`__CODE_TOKEN_${index}__`, tokenHtml)
  })

  return html.replace(/\n/g, '<br />')
}

function parseTableRow(line) {
  const source = String(line || '').trim().replace(/^\|/, '').replace(/\|$/, '')
  return source.split('|').map(cell => renderInline(cell.trim()))
}

function isTableSeparator(line) {
  if (!line) return false
  const source = String(line).trim()
  if (!source.includes('|')) return false
  return source
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .every(cell => /^:?-{3,}:?$/.test(cell.trim()))
}

export function renderAnalysisMarkdown(source) {
  const text = String(source || '').replace(/\r\n/g, '\n')
  const lines = text.split('\n')
  const blocks = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]
    const trimmed = line.trim()

    if (!trimmed) {
      index += 1
      continue
    }

    const codeMatch = trimmed.match(/^```([\w-]+)?$/)
    if (codeMatch) {
      const lang = codeMatch[1] ? ` language-${escapeHtml(codeMatch[1])}` : ''
      const buffer = []
      index += 1
      while (index < lines.length && !lines[index].trim().match(/^```$/)) {
        buffer.push(lines[index])
        index += 1
      }
      if (index < lines.length) index += 1
      blocks.push(`<pre class="analysis-md-code"><code class="${lang.trim()}">${escapeHtml(buffer.join('\n'))}</code></pre>`)
      continue
    }

    if (trimmed.includes('|') && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
      const header = parseTableRow(line)
      const rows = []
      index += 2
      while (index < lines.length && lines[index].trim().includes('|') && !isTableSeparator(lines[index])) {
        rows.push(parseTableRow(lines[index]))
        index += 1
      }

      blocks.push(
        `<div class="analysis-md-table-wrap"><table class="analysis-md-table"><thead><tr>${header.map(cell => `<th>${cell}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`
      )
      continue
    }

    const headingMatch = trimmed.match(/^(#{1,4})\s+(.+)$/)
    if (headingMatch) {
      const level = Math.min(4, headingMatch[1].length)
      blocks.push(`<h${level}>${renderInline(headingMatch[2])}</h${level}>`)
      index += 1
      continue
    }

    if (/^(-{3,}|\*{3,})$/.test(trimmed)) {
      blocks.push('<hr />')
      index += 1
      continue
    }

    if (/^>\s?/.test(trimmed)) {
      const quoteLines = []
      while (index < lines.length && /^>\s?/.test(lines[index].trim())) {
        quoteLines.push(lines[index].trim().replace(/^>\s?/, ''))
        index += 1
      }
      blocks.push(`<blockquote><p>${renderInline(quoteLines.join(' '))}</p></blockquote>`)
      continue
    }

    if (/^[-*+]\s+/.test(trimmed)) {
      const items = []
      while (index < lines.length && /^[-*+]\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^[-*+]\s+/, ''))
        index += 1
      }
      blocks.push(`<ul>${items.map(item => `<li>${renderInline(item)}</li>`).join('')}</ul>`)
      continue
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items = []
      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s+/, ''))
        index += 1
      }
      blocks.push(`<ol>${items.map(item => `<li>${renderInline(item)}</li>`).join('')}</ol>`)
      continue
    }

    const paragraphLines = []
    while (index < lines.length) {
      const current = lines[index]
      const currentTrimmed = current.trim()
      if (!currentTrimmed) break
      if (
        currentTrimmed.match(/^```/) ||
        currentTrimmed.match(/^(#{1,4})\s+/) ||
        currentTrimmed.match(/^>\s?/) ||
        currentTrimmed.match(/^[-*+]\s+/) ||
        currentTrimmed.match(/^\d+\.\s+/) ||
        currentTrimmed.match(/^(-{3,}|\*{3,})$/) ||
        (currentTrimmed.includes('|') && index + 1 < lines.length && isTableSeparator(lines[index + 1]))
      ) {
        break
      }
      paragraphLines.push(currentTrimmed)
      index += 1
    }
    blocks.push(`<p>${renderInline(paragraphLines.join('\n'))}</p>`)
  }

  return blocks.join('')
}
