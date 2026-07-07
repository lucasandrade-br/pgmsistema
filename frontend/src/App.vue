<script setup>
import Toast from 'primevue/toast'
</script>

<template>
  <!-- Toast global — disponível em qualquer view via useToast() -->
  <Toast position="top-right" />
  <!-- O router renderiza AppLayout (rotas protegidas) ou as views de auth -->
  <RouterView />
</template>

