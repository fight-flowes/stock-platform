function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function sanitizeUrl(url) {
  const trimmed = String(url ?? '').trim()
  if (!trimmed) return ''
  if (/^(https?:|mailto:)/i.test(trimmed)) {
    return escapeHtml(trimmed)
  }
  return ''
}

function parseInline(text) {
  let html = escapeHtml(text)

  html = html.replace(/`([^`]+)`/g, (_, code) => `<code>${code}</code>`)
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, href) => {
    const safeHref = sanitizeUrl(href)
    if (!safeHref) return label
    return `<a href="${safeHref}" target="_blank" rel="noreferrer noopener">${label}</a>`
  })
  html = html.replace(/(^|[\s(])((https?:\/\/|mailto:)[^\s<]+)/gi, (_, prefix, url) => {
    const safeHref = sanitizeUrl(url)
    if (!safeHref) return `${prefix}${url}`
    return `${prefix}<a href="${safeHref}" target="_blank" rel="noreferrer noopener">${url}</a>`
  })

  return html
}

function isTableSeparator(line) {
  const trimmed = line.trim()
  return /^\|?[\s:-]+(\|[\s:-]+)+\|?$/.test(trimmed)
}

function splitTableRow(line) {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(cell => cell.trim())
}

function renderTable(lines, startIndex) {
  const headerLine = lines[startIndex]
  const separatorLine = lines[startIndex + 1]
  const rows = []
  let index = startIndex + 2

  while (index < lines.length && lines[index].trim().startsWith('|')) {
    rows.push(splitTableRow(lines[index]))
    index += 1
  }

  const headers = splitTableRow(headerLine)
  const aligns = splitTableRow(separatorLine).map(cell => {
    const left = cell.startsWith(':')
    const right = cell.endsWith(':')
    if (left && right) return 'center'
    if (right) return 'right'
    return 'left'
  })

  const thead = headers
    .map((cell, columnIndex) => `<th style="text-align:${aligns[columnIndex] || 'left'}">${parseInline(cell)}</th>`)
    .join('')

  const tbody = rows
    .map(row => {
      const cells = headers.map((_, columnIndex) => {
        const align = aligns[columnIndex] || 'left'
        return `<td style="text-align:${align}">${parseInline(row[columnIndex] || '')}</td>`
      }).join('')
      return `<tr>${cells}</tr>`
    })
    .join('')

  return {
    html: `<div class="md-table-wrap"><table><thead><tr>${thead}</tr></thead><tbody>${tbody}</tbody></table></div>`,
    nextIndex: index
  }
}

function renderList(lines, startIndex, ordered) {
  const pattern = ordered ? /^\d+\.\s+/ : /^[-*+]\s+/
  const tag = ordered ? 'ol' : 'ul'
  const items = []
  let index = startIndex

  while (index < lines.length && pattern.test(lines[index].trim())) {
    items.push(lines[index].trim().replace(pattern, ''))
    index += 1
  }

  return {
    html: `<${tag}>${items.map(item => `<li>${parseInline(item)}</li>`).join('')}</${tag}>`,
    nextIndex: index
  }
}

function renderBlockquote(lines, startIndex) {
  const parts = []
  let index = startIndex

  while (index < lines.length && lines[index].trim().startsWith('>')) {
    parts.push(lines[index].trim().replace(/^>\s?/, ''))
    index += 1
  }

  return {
    html: `<blockquote>${parts.map(line => `<p>${parseInline(line)}</p>`).join('')}</blockquote>`,
    nextIndex: index
  }
}

function renderCodeBlock(lines, startIndex) {
  const fence = lines[startIndex].trim()
  const language = fence.slice(3).trim()
  const codeLines = []
  let index = startIndex + 1

  while (index < lines.length && !lines[index].trim().startsWith('```')) {
    codeLines.push(lines[index])
    index += 1
  }

  if (index < lines.length) {
    index += 1
  }

  const className = language ? ` class="language-${escapeHtml(language)}"` : ''
  return {
    html: `<pre><code${className}>${escapeHtml(codeLines.join('\n'))}</code></pre>`,
    nextIndex: index
  }
}

function renderParagraph(lines, startIndex) {
  const parts = []
  let index = startIndex

  while (index < lines.length) {
    const trimmed = lines[index].trim()
    if (!trimmed) break
    if (
      trimmed.startsWith('#') ||
      trimmed.startsWith('>') ||
      trimmed.startsWith('```') ||
      trimmed.startsWith('|') ||
      /^[-*+]\s+/.test(trimmed) ||
      /^\d+\.\s+/.test(trimmed) ||
      /^---+$/.test(trimmed)
    ) {
      break
    }
    parts.push(trimmed)
    index += 1
  }

  return {
    html: `<p>${parts.map(part => parseInline(part)).join('<br />')}</p>`,
    nextIndex: index
  }
}

export function renderMarkdown(markdownText) {
  const source = String(markdownText ?? '').replace(/\r\n/g, '\n').trim()
  if (!source) return ''

  const lines = source.split('\n')
  const blocks = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]
    const trimmed = line.trim()

    if (!trimmed) {
      index += 1
      continue
    }

    if (trimmed.startsWith('```')) {
      const block = renderCodeBlock(lines, index)
      blocks.push(block.html)
      index = block.nextIndex
      continue
    }

    if (/^#{1,6}\s+/.test(trimmed)) {
      const level = trimmed.match(/^#+/)[0].length
      const content = trimmed.replace(/^#{1,6}\s+/, '')
      blocks.push(`<h${level}>${parseInline(content)}</h${level}>`)
      index += 1
      continue
    }

    if (trimmed.startsWith('|') && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
      const block = renderTable(lines, index)
      blocks.push(block.html)
      index = block.nextIndex
      continue
    }

    if (/^[-*+]\s+/.test(trimmed)) {
      const block = renderList(lines, index, false)
      blocks.push(block.html)
      index = block.nextIndex
      continue
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const block = renderList(lines, index, true)
      blocks.push(block.html)
      index = block.nextIndex
      continue
    }

    if (trimmed.startsWith('>')) {
      const block = renderBlockquote(lines, index)
      blocks.push(block.html)
      index = block.nextIndex
      continue
    }

    if (/^---+$/.test(trimmed)) {
      blocks.push('<hr />')
      index += 1
      continue
    }

    const block = renderParagraph(lines, index)
    blocks.push(block.html)
    index = block.nextIndex
  }

  return blocks.join('\n')
}
