/**
 * Exportação de documentos no client — sem dependências externas.
 *
 * `.doc` (Word) é gerado como HTML com MIME `application/msword`: o Word abre
 * HTML nativamente, então o arquivo abre formatado sem precisar de lib de docx.
 * Para PDF "de verdade" seria necessária uma lib (jsPDF/docx) — fora de escopo aqui.
 */

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/** Normaliza um nome de arquivo (sem acentos/espaços problemáticos). */
export function slugifyFilename(s: string): string {
  return (
    s
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-zA-Z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .toLowerCase() || 'documento'
  )
}

export interface DocSection {
  titulo: string
  conteudo: string
}

export interface DocOptions {
  /** Nome do arquivo, sem extensão. */
  filename: string
  title: string
  subtitle?: string
  sections: DocSection[]
  /** Rodapé (ex.: aviso de origem / disclaimer). */
  footer?: string
}

/** Gera e baixa um `.doc` (Word) a partir de seções de texto. */
export function downloadDoc({ filename, title, subtitle, sections, footer }: DocOptions): void {
  const body = sections
    .map(
      (s) =>
        `<h2 style="font-size:13pt;margin:18pt 0 6pt">${escapeHtml(s.titulo)}</h2>` +
        `<p style="font-size:11pt;line-height:1.5;text-align:justify;white-space:pre-wrap">${escapeHtml(
          s.conteudo,
        )}</p>`,
    )
    .join('\n')

  const html =
    `<!DOCTYPE html><html xmlns:o="urn:schemas-microsoft-com:office:office" ` +
    `xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">` +
    `<head><meta charset="utf-8"><title>${escapeHtml(title)}</title></head>` +
    `<body style="font-family:'Times New Roman',serif;color:#111">` +
    `<h1 style="font-size:16pt;text-align:center;margin:0 0 4pt">${escapeHtml(title)}</h1>` +
    (subtitle
      ? `<p style="font-size:11pt;text-align:center;color:#555;margin:0 0 12pt">${escapeHtml(subtitle)}</p>`
      : '') +
    body +
    (footer
      ? `<hr style="margin-top:24pt"><p style="font-size:9pt;color:#777">${escapeHtml(footer)}</p>`
      : '') +
    `</body></html>`

  triggerDownload(new Blob([html], { type: 'application/msword' }), `${filename}.doc`)
}

/** Gera e baixa um JSON estruturado (portabilidade / trilha ANPD). */
export function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  triggerDownload(blob, `${filename}.json`)
}
