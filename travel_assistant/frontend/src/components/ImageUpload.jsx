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
  const [pickerOpen, setPickerOpen] = useState(false)
  const [uploads, setUploads] = useState([])

  const openPicker = () => {
    const base = uploadUrl.replace(/\/api\/upload.*$/, '')
    fetch(base + '/api/uploads').then((r) => r.json()).then((d) => setUploads(d.uploads || [])).catch(() => setUploads([]))
    setPickerOpen(true)
  }
  const choose = (url) => {
    setPreview(url)
    onUploaded && onUploaded(url)
    setPickerOpen(false)
  }

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
          <div className="flex gap-2">
            <Button variant="secondary" type="button" onClick={openPicker} disabled={uploading}>
              {uploading ? 'Uploading…' : 'Browse'}
            </Button>
            {preview && (
              <Button variant="secondary" type="button" onClick={() => { setPreview(''); onUploaded && onUploaded('') }}>
                Remove
              </Button>
            )}
          </div>
          {uploading && (
            <div className="mt-2 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
              <div className="h-full bg-brand-600 transition-all" style={{ width: progress + '%' }} />
            </div>
          )}
          {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
        </div>
      </div>
      {pickerOpen && (
        <div className="fixed inset-0 z-[3000] flex items-end sm:items-center justify-center bg-black/50" onClick={() => setPickerOpen(false)}>
          <div className="bg-white dark:bg-slate-900 rounded-t-2xl sm:rounded-2xl w-full sm:max-w-lg max-h-[80vh] overflow-y-auto p-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold">Choose image</h3>
              <button onClick={() => setPickerOpen(false)} className="text-slate-500">✕</button>
            </div>
            <div className="grid grid-cols-4 gap-2 mb-4">
              {uploads.map((u) => (
                <button key={u.url} onClick={() => choose(u.url)} className="aspect-square rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700">
                  <img src={assetUrl(u.url)} alt="" className="w-full h-full object-cover" />
                </button>
              ))}
              {uploads.length === 0 && <p className="col-span-4 text-sm text-slate-500">No uploaded images yet.</p>}
            </div>
            <Button onClick={() => inputRef.current?.click()} className="w-full">Upload a new image</Button>
          </div>
        </div>
      )}
    </div>
  )
}
