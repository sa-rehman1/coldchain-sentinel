import * as Dialog from '@radix-ui/react-dialog';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { CheckCircle2, ChevronDown, CircleAlert, CircleX, Info, X } from 'lucide-react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

export function Button({ variant = 'secondary', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' | 'ghost' }) {
  return <button className={`button button-${variant} ${className}`} {...props} />;
}

export function Badge({ tone = 'neutral', children }: { tone?: 'critical' | 'warning' | 'success' | 'info' | 'neutral'; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function StatusDot({ state }: { state: 'healthy' | 'degraded' | 'offline' }) {
  return <span className={`status-dot status-${state}`} role="img" aria-label={state} />;
}

export function CheckState({ state }: { state: 'pass' | 'warning' | 'failure' }) {
  const Icon = state === 'pass' ? CheckCircle2 : state === 'warning' ? CircleAlert : CircleX;
  return <Icon className={`check-icon check-${state}`} aria-label={state} />;
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><Info size={24} /><h3>{title}</h3><p>{detail}</p></div>;
}

export function Modal({ open, onOpenChange, title, description, children }: { open: boolean; onOpenChange: (open: boolean) => void; title: string; description: string; children: ReactNode }) {
  return <Dialog.Root open={open} onOpenChange={onOpenChange}>
    <Dialog.Portal>
      <Dialog.Overlay className="dialog-overlay" />
      <Dialog.Content className="dialog-content">
        <div className="dialog-header"><div><Dialog.Title>{title}</Dialog.Title><Dialog.Description>{description}</Dialog.Description></div><Dialog.Close className="icon-button" aria-label="Close"><X size={18} /></Dialog.Close></div>
        {children}
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}

export function Menu({ label, children }: { label: ReactNode; children: ReactNode }) {
  return <DropdownMenu.Root><DropdownMenu.Trigger asChild><Button variant="ghost" className="menu-trigger">{label}<ChevronDown size={14} /></Button></DropdownMenu.Trigger><DropdownMenu.Portal><DropdownMenu.Content className="dropdown-content" align="end" sideOffset={8}>{children}</DropdownMenu.Content></DropdownMenu.Portal></DropdownMenu.Root>;
}

export const MenuItem = DropdownMenu.Item;
