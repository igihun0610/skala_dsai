<template>
  <q-page class="flex flex-center" style="min-height: 400px;">
    <div class="text-center">
      <div style="font-size: 120px; color: #ccc;">404</div>
      <div class="text-h4 q-mb-md">페이지를 찾을 수 없습니다</div>
      <div class="text-body1 text-grey-6 q-mb-lg">
        요청하신 페이지가 존재하지 않거나 이동되었습니다.
      </div>
      <q-btn
        color="primary"
        size="lg"
        to="/"
        label="홈으로 돌아가기"
        icon="home"
      />
    </div>
  </q-page>
</template>

<script setup lang="ts">
// No logic needed for this simple 404 page
</script>