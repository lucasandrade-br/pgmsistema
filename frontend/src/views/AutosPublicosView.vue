<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const token = route.params.token

onMounted(() => {
  setTimeout(() => {
    // Usa a mesma variável de api.js para consistência
    const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1/'
    window.location.href = `${base}publico/link/${token}`
  }, 1500)
})
</script>

<template>
  <div class="min-h-screen bg-gray-100 flex items-center justify-center p-6">
    <div class="bg-white rounded-2xl shadow-lg p-10 flex flex-col items-center gap-6 max-w-md w-full">

      <i class="pi pi-spin pi-spinner text-5xl text-blue-500" />

      <div class="text-center">
        <h1 class="text-xl font-bold text-gray-800 mb-2">
          Autos Digitais do Processo
        </h1>
        <p class="text-gray-500 text-sm leading-relaxed">
          Iniciando o download seguro do arquivo.
          <br />
          Por favor, aguarde...
        </p>
      </div>

    </div>
  </div>
</template>
