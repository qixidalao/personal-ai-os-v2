/**
 * 🎨 自绘 UI 组件库 — Personal AI OS
 * 无第三方 UI 依赖，全部手写
 */

// ====== 基础组件 ======
export { default as AiButton } from './Button/Button.vue'
export { default as AiInput } from './Input/Input.vue'
export { default as AiCard } from './Card/Card.vue'
export { default as AiBadge } from './Badge/Badge.vue'
export { default as AiAvatar } from './Avatar/Avatar.vue'
export { default as AiModal } from './Modal/Modal.vue'
export { default as AiDrawer } from './Drawer/Drawer.vue'
export { default as AiDropdown } from './Dropdown/Dropdown.vue'
export { default as AiToggle } from './Toggle/Toggle.vue'
export { default as AiTooltip } from './Tooltip/Tooltip.vue'
export { default as AiToastContainer } from './Toast/ToastContainer.vue'
export { useToast } from './Toast/useToast'

// ====== 布局组件 ======
export { default as AiSkeleton } from './Skeleton/Skeleton.vue'
export { default as AiProgress } from './Progress/Progress.vue'
export { default as AiSpinner } from './Spinner/Spinner.vue'
export { default as AiDivider } from './Divider/Divider.vue'
export { default as AiEmpty } from './Empty/Empty.vue'

// ====== 安装函数 ======
import type { App } from 'vue'
import Button from './Button/Button.vue'
import Input from './Input/Input.vue'
import Card from './Card/Card.vue'
import Badge from './Badge/Badge.vue'

export function installUI(app: App) {
  app.component('AiButton', Button)
  app.component('AiInput', Input)
  app.component('AiCard', Card)
  app.component('AiBadge', Badge)
}
