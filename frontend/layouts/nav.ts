import {
  MessageSquare, PencilLine, Bot, Puzzle, Wrench, FileText, Brain,
  History, Settings, Layers, Activity,
} from 'lucide-vue-next'

export interface NavItem {
  path: string
  label: string
  en: string
  icon: any
  hint?: string
}

export interface NavGroup {
  key: string
  title: string
  en: string
  items: NavItem[]
}

/**
 * 单一导航来源：侧栏 / 移动端面板 / 面包屑 / 命令面板都从这里读。
 * 分组原则：工作区（日常对话与写作）/ 智能体（运行时、能力、提示词）/ 知识（记忆与历史）。
 * 角色人设已并入「智能体」页的 tab；全局搜索走顶栏 ⌘K，不再占导航位。
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    key: 'work', title: '工作区', en: 'WORKSPACE',
    items: [
      { path: '/chat', label: '对话', en: 'Chat', icon: MessageSquare, hint: '⌘1' },
      { path: '/workspace', label: '工作台', en: 'Studio', icon: PencilLine, hint: '⌘2' },
    ],
  },
  {
    key: 'agents', title: '智能体', en: 'AGENTS',
    items: [
      { path: '/agent', label: '智能体', en: 'Agent', icon: Bot },
      { path: '/plugins', label: '技能', en: 'Skills', icon: Puzzle },
      { path: '/tools', label: '工具', en: 'Tools', icon: Wrench },
      { path: '/prompt', label: '提示词', en: 'Prompts', icon: FileText },
    ],
  },
  {
    key: 'knowledge', title: '知识', en: 'KNOWLEDGE',
    items: [
      { path: '/memory', label: '记忆', en: 'Memory', icon: Brain },
      { path: '/history', label: '历史', en: 'History', icon: History },
      { path: '/runs', label: '执行记录', en: 'Runs', icon: Activity },
    ],
  },
]

export const NAV_FOOTER: NavItem[] = [
  { path: '/settings', label: '设置', en: 'Settings', icon: Settings },
]

export const MOBILE_TABS = [
  { path: '/chat', label: '对话', icon: MessageSquare },
  { path: '/workspace', label: '工作台', icon: PencilLine },
  { path: '/agent', label: '智能体', icon: Bot },
  { path: '/tools', label: '工具', icon: Wrench },
  { path: '__more', label: '更多', icon: Layers },
]

export function allNavItems(): NavItem[] {
  return NAV_GROUPS.flatMap(g => g.items).concat(NAV_FOOTER)
}
