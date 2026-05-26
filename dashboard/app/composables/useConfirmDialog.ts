// PR75 v2.93.0 — confirm-dialog composable.
//
// Async wrapper around the canonical Nuxt UI v4 useOverlay pattern.
// Replaces every window.confirm() call across the dashboard.
//
// Usage:
//   const confirm = useConfirmDialog()
//   const ok = await confirm({
//     title: 'Delete persona',
//     description: 'This removes the persona from the JSON store.',
//     confirmLabel: 'Delete',
//     variant: 'danger',
//   })
//   if (ok) { ... }

import { ConfirmDialog } from '#components'

export interface ConfirmDialogOptions {
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'default' | 'danger'
}

export const useConfirmDialog = () => {
  const overlay = useOverlay()

  return async (options: ConfirmDialogOptions): Promise<boolean> => {
    const modal = overlay.create(ConfirmDialog, {
      destroyOnClose: true,
      props: options,
    })

    const result = await modal.open()
    return result === true
  }
}
