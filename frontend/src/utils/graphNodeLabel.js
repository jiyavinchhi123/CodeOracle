export const MIN_NODE_RADIUS = 18
export const MAX_NODE_RADIUS = 40

export function splitCamelCase(text) {
  return text
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
    .split(/\s+/)
    .filter(Boolean)
}

export function wrapNodeLabel(label) {
  const extMatch = label.match(/^(.+?)(\.[a-zA-Z0-9]+)$/)
  const base = extMatch ? extMatch[1] : label
  const ext = extMatch ? extMatch[2] : null
  const camelParts = splitCamelCase(base)
  let lines = []

  if (camelParts.length >= 2) {
    if (ext) {
      if (camelParts.length === 2) {
        lines = [camelParts[0], camelParts[1], ext]
      } else if (camelParts.length === 3) {
        lines = [camelParts[0], camelParts[1], `${camelParts[2]}${ext}`]
      } else {
        lines = [camelParts[0], camelParts[1], `${camelParts.slice(2).join('')}${ext}`]
      }
    } else if (camelParts.length <= 3) {
      lines = camelParts
    } else {
      lines = [camelParts[0], camelParts[1], camelParts.slice(2).join('')]
    }
  } else if (ext) {
    if (base.length > 9) {
      const chunk = Math.ceil(base.length / 2)
      lines = [base.slice(0, chunk), base.slice(chunk), ext]
    } else {
      lines = [base, ext]
    }
  } else if (base.length > 12) {
    const chunk = Math.ceil(base.length / 2)
    lines = [base.slice(0, chunk), base.slice(chunk)]
  } else {
    lines = [base]
  }

  return lines.slice(0, 3)
}

export function truncateLine(line, maxChars) {
  if (maxChars < 4) return `${line.slice(0, 1)}…`
  if (line.length <= maxChars) return line
  return `${line.slice(0, maxChars - 1)}…`
}

export function computeNodeVisual(label, active = false) {
  const wrapped = wrapNodeLabel(label)
  const initialLongest = Math.max(...wrapped.map((line) => line.length), 1)

  let fontSize = 10
  if (wrapped.length >= 3 || initialLongest > 9) fontSize = 9
  if (initialLongest > 12) fontSize = 8
  if (initialLongest > 16) fontSize = 7

  let lines = wrapped
  let lineHeight = fontSize * 1.18
  let charWidth = fontSize * 0.56

  const measure = (currentLines, currentFontSize) => {
    const lh = currentFontSize * 1.18
    const cw = currentFontSize * 0.56
    const longest = Math.max(...currentLines.map((line) => line.length), 1)
    const textHeight = (currentLines.length - 1) * lh + currentFontSize
    const textWidth = longest * cw
    const radius = Math.min(
      MAX_NODE_RADIUS,
      Math.max(MIN_NODE_RADIUS, textWidth / 1.5 + 8, textHeight / 2 + 10) + (active ? 2 : 0),
    )
    return { longest, textHeight, textWidth, radius, lh, cw }
  }

  let metrics = measure(lines, fontSize)
  let maxChars = Math.max(4, Math.floor((metrics.radius * 1.5) / metrics.cw))
  lines = wrapped.map((line) => truncateLine(line, maxChars))
  metrics = measure(lines, fontSize)

  while (
    (metrics.textWidth > metrics.radius * 1.48 || metrics.textHeight > metrics.radius * 1.62) &&
    fontSize > 6
  ) {
    fontSize -= 1
    lineHeight = fontSize * 1.18
    charWidth = fontSize * 0.56
    maxChars = Math.max(4, Math.floor((metrics.radius * 1.5) / charWidth))
    lines = wrapped.map((line) => truncateLine(line, maxChars))
    metrics = measure(lines, fontSize)
  }

  while (metrics.textWidth > metrics.radius * 1.45 && metrics.radius < MAX_NODE_RADIUS) {
    const nextRadius = Math.min(MAX_NODE_RADIUS, metrics.radius + 2)
    maxChars = Math.max(4, Math.floor((nextRadius * 1.5) / charWidth))
    lines = wrapped.map((line) => truncateLine(line, maxChars))
    metrics = { ...measure(lines, fontSize), radius: nextRadius }
  }

  const startY = -((lines.length - 1) * lineHeight) / 2 + fontSize * 0.34

  return {
    radius: metrics.radius,
    fontSize,
    lineHeight,
    lines,
    startY,
  }
}

export function safeSvgId(id) {
  return id.replace(/[^a-zA-Z0-9_-]/g, '_')
}
