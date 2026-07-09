<template><div class="ai-spinner"><div class="ai-spinner__dot"/><div class="ai-spinner__dot"/><div class="ai-spinner__dot"/></div></template>
<style scoped>
.ai-spinner{display:flex;gap:4px;align-items:center}
.ai-spinner__dot{width:6px;height:6px;border-radius:50%;background:var(--primary);animation:spinnerBounce 1.4s infinite ease both}
.ai-spinner__dot:nth-child(1){animation-delay:-.32s}
.ai-spinner__dot:nth-child(2){animation-delay:-.16s}
@keyframes spinnerBounce{0%,80%,100%{transform:scale(0)}40%{transform:scale(1)}}
</style>
