import { useEffect, useRef, useState, type ReactNode } from 'react'

interface DropdownProps {
  trigger: (ctx: { open: boolean; toggle: () => void }) => ReactNode
  children: (close: () => void) => ReactNode
  align?: 'left' | 'right'
  className?: string
}

/** Generic menu button: click the trigger to open a floating panel, click outside or Escape to close. */
export function Dropdown({ trigger, children, align = 'left', className = '' }: DropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={ref} className={`relative inline-block ${className}`}>
      {trigger({ open, toggle: () => setOpen((o) => !o) })}
      {open && (
        <div className={`knp-dropdown-panel absolute z-30 mt-2 ${align === 'right' ? 'right-0' : 'left-0'}`}>
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  )
}

export function DropdownItem({
  onClick,
  active,
  children,
}: {
  onClick: () => void
  active?: boolean
  children: ReactNode
}) {
  return (
    <button type="button" onClick={onClick} className={`knp-dropdown-item ${active ? 'knp-dropdown-item-active' : ''}`}>
      {children}
    </button>
  )
}
