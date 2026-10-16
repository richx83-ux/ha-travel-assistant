import { useState, useRef } from 'react'
import Button from './Button'

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

/**
 * Reusable image upload with browse, preview, and progress bar.
 * onUploaded(url) is called with the returned path when complete.
 */
export default function ImageUpload({ value, onUploaded, uploadUrl, label = 'Image' }) {
  const inputRef = useRef(null)
  const [progress, setProgress] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [preview, setPreview] = useState(value || '')

  const upload = (file) => {
    if (!file) return
    setError(null)
    setUploading(true)
    setProgress(0)

    const form = new FormData()
    form.append('file', file)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', uploadUrl)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) setProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      setUploading(false)
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText)
          const url = data.url || ''
          setPreview(url)
          onUploaded && onUploaded(url)
        } catch {
          setError('Upload failed (bad response)')
        }
      } else {
        let msg = 'Upload failed (' + xhr.status + ')'
        try {
          const data = JSON.parse(xhr.responseText)
          if (data.detail) msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
        } catch {}
        setError(msg)
      }
    }
    xhr.onerror = () => {
      setUploading(false)
      setError('Upload failed')
    }
    xhr.send(form)
  }

  const onFile = (e) => {
    const file = e.target.files?.[0]
    if (file) upload(file)
    e.target.value = ''
  }

  return (
    <div>
      <div className="text-xs font-medium text-slate-500 mb-1">{label}</div>
      <div className="flex items-center gap-3">
        <div className="w-16 h-16 rounded-lg bg-slate-100 dark:bg-slate-800 overflow-hidden flex items-center justify-center flex-shrink-0">
          {preview ? (
            <img src={assetUrl(preview)} alt="" className="w-full h-full object-cover" />
          ) : (
            <span className="text-slate-400 text-xs">None</span>
          )}
        </div>
        <div className="flex-1">
          <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={onFile} />
          <Button variant="secondary" type="button" onClick={() => inputRef.current?.click()} disabled={uploading}>
            {uploading ? 'Uploading…' : 'Browse'}
          </Button>
          {uploading && (
            <div className="mt-2 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
              <div className="h-full bg-brand-600 transition-all" style={{ width: progress + '%' }} />
            </div>
          )}
          {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
        </div>
      </div>
    </div>
  )
}
