export default function Input({ className = '', ...props }) {
  return (
    <input
      className={`w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500 ${className}`}
      {...props}
    />
  )
}
