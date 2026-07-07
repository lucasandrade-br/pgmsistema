<script setup>
import { useRouter } from 'vue-router'
import Button from 'primevue/button'

const router = useRouter()
</script>

<template>
  <div class="min-h-screen flex flex-col items-center justify-center bg-slate-50 gap-6 text-center px-4">
    <i class="pi pi-exclamation-circle text-gray-300" style="font-size: 5rem" />

    <div>
      <h1 class="text-3xl font-bold text-gray-800">404 — Página não encontrada</h1>
      <p class="mt-2 text-gray-500 max-w-md">
        O caminho que você tentou acessar não existe ou foi movido.
      </p>
    </div>

    <Button
      label="Voltar para o Início"
      icon="pi pi-home"
      @click="router.push('/')"
    />
  </div>
</template>
