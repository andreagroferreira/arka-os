<script setup lang="ts">
// PR80 v2.98.0 — /personas/new wraps the 4-step AI PersonaWizard.
//
// Fills the dead link that PR78 introduced when it moved the New Persona
// button into the table header but never built the destination route.
//
// Wizard contract (defined in components/PersonaWizard.vue):
//   @completed(persona)   → wizard finished + saved; navigate to detail
//   @cancelled            → operator backed out; return to the table
//
// The wizard never auto-saves; every step is operator-confirmed inside
// the component, so this page is purely a hosting shell.

import type { Persona } from '~/types'

const toast = useToast()

function onCompleted(persona: Persona) {
  toast.add({
    title: 'Persona created',
    description: `${persona.name} is ready in the library.`,
    color: 'success',
    icon: 'i-lucide-check-circle',
  })
  navigateTo(`/personas/${persona.id}`)
}

function onCancelled() {
  navigateTo('/personas')
}
</script>

<template>
  <UDashboardPanel id="personas-new">
    <template #header>
      <UDashboardNavbar title="New Persona">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            variant="ghost"
            size="sm"
            aria-label="Back to personas"
            to="/personas"
          />
        </template>
        <template #trailing>
          <UBadge
            label="AI-assisted"
            icon="i-lucide-sparkles"
            color="primary"
            variant="soft"
            size="sm"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="max-w-5xl mx-auto py-2">
        <PersonaWizard
          @completed="onCompleted"
          @cancelled="onCancelled"
        />
      </div>
    </template>
  </UDashboardPanel>
</template>
