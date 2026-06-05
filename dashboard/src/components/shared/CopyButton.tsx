import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import clsx from 'clsx'

interface CopyButtonProps {
  text: string
  className?: string
}

export function CopyButton({ text, className }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback for older browsers
      const el = document.createElement('textarea')
      el.value = text
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <button
      onClick={handleCopy}
      title={copied ? 'Copied!' : 'Copy to clipboard'}
      className={clsx(
        'inline-flex items-center justify-center rounded p-1 transition-colors',
        copied
          ? 'text-green-400 bg-green-400/10'
          : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700',
        className,
      )}
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  )
}
