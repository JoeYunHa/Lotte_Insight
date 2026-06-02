const BUBBLE_PALETTE: Array<{ border: string; bg: string; text: string }> = [
  { border: '#e74c3c', bg: 'rgba(231,76,60,0.13)',  text: '#e74c3c' },
  { border: '#e67e22', bg: 'rgba(230,126,34,0.13)', text: '#e67e22' },
  { border: '#f1c40f', bg: 'rgba(241,196,15,0.13)', text: '#b8960a' },
  { border: '#27ae60', bg: 'rgba(39,174,96,0.13)',  text: '#27ae60' },
  { border: '#16a085', bg: 'rgba(22,160,133,0.13)', text: '#16a085' },
  { border: '#2980b9', bg: 'rgba(41,128,185,0.13)', text: '#2980b9' },
  { border: '#8e44ad', bg: 'rgba(142,68,173,0.13)', text: '#8e44ad' },
  { border: '#c0392b', bg: 'rgba(192,57,43,0.13)',  text: '#c0392b' },
  { border: '#d35400', bg: 'rgba(211,84,0,0.13)',   text: '#d35400' },
  { border: '#1a6ba8', bg: 'rgba(26,107,168,0.13)', text: '#1a6ba8' },
  { border: '#7d3c98', bg: 'rgba(125,60,152,0.13)', text: '#7d3c98' },
  { border: '#117a65', bg: 'rgba(17,122,101,0.13)', text: '#117a65' },
]

function hashAlias(alias: string): number {
  let h = 5381
  for (let i = 0; i < alias.length; i++) {
    h = ((h << 5) + h + alias.charCodeAt(i)) & 0x7fffffff
  }
  return h
}

export function getBubbleColor(alias: string): { border: string; bg: string; text: string } {
  return BUBBLE_PALETTE[hashAlias(alias) % BUBBLE_PALETTE.length]
}
