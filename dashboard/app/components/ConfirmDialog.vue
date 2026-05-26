<script setup lang="ts">
// PR75 v2.93.0 — canonical confirm dialog (Nuxt UI v4 pattern).
//
// Replaces native window.confirm() calls. Driven by useConfirmDialog()
// composable, which itself uses useOverlay() to mount this component
// imperatively. Emits a boolean on close: true = confirm,
// false = cancel.
//
// Per the Nuxt UI v4 docs (https://ui.nuxt.com/docs/composables/use-overlay).

interface ConfirmDialogProps {
  title?: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  /**
   * Display variant for the confirm button. Use 'error' for destructive
   * actions (delete, etc.) so the dialog visually warns the operator.
   */
  variant?: 'default' | 'danger'
}

const props = withDefaults(defineProps<ConfirmDialogProps>(), {
  title: 'Confirm action',
  description: '',
  confirmLabel: 'Confirm',
  cancelLabel: 'Cancel',
  variant: 'default',
})

const emits = defineEmits<{
  close: [value: boolean]
}>()

const confirmColor = computed(() =>
  props.variant === 'danger' ? 'error' : 'primary',
)
</script>

<template>
  <UModal
    :title="title"
    :description="description"
    :dismissible="false"
    :ui="{ footer: 'justify-end' }"
  >
    <template #footer>
      <UButton
        :label="cancelLabel"
        color="neutral"
        variant="outline"
        @click="emits('close', false)"
      />
      <UButton
        :label="confirmLabel"
        :color="confirmColor"
        @click="emits('close', true)"
      />
    </template>
  </UModal>
</template>
