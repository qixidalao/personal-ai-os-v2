<template>
  <div class="ui-page settings-page">
    <div class="ui-page-inner">
      <header class="ui-hero set-hero">
        <div class="ui-hero-main">
          <div class="ui-eyebrow">CONSOLE</div>
          <h1 class="ui-title">{{ isAdmin ? '管理员设置' : '设置' }}</h1>
          <p class="ui-sub">{{ isAdmin ? '模型、工具、数据与安全的全局配置。仅管理员可见。' : '外观、账号与执行服务器的个人设置，修改后自动保存。' }}</p>
        </div>
        <div class="ui-head-actions">
          <router-link v-if="isAdmin" to="/settings" class="ui-btn ui-btn--ghost ui-btn--sm">← 返回用户设置</router-link>
          <router-link v-else-if="isOwner" to="/admin" class="ui-btn ui-btn--ghost ui-btn--sm">管理员控制台 →</router-link>
          <span :class="['ui-badge', loadingSettings ? '' : 'ui-badge--ok']">
            {{ loadingSettings ? '正在同步配置…' : '自动保存已开启' }}
          </span>
        </div>
      </header>

      <div class="set-shell" :class="{ mobile: isMobile }">
        <nav class="ui-seg set-nav">
          <button
            v-for="t in tabs"
            :key="t.id"
            :class="['ui-seg-item', { active: activeTab === t.id }]"
            @click="activeTab = t.id"
          >
            <span class="set-nav-icon">{{ t.icon }}</span>
            <span class="set-nav-label">{{ t.label }}</span>
          </button>
        </nav>

        <div class="set-panes">
          <!-- ==================== 模型与服务 ==================== -->
          <div v-if="activeTab === 'global'" class="set-pane">
            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">模型提供商</h2>
                  <p class="ui-section-sub">接入 OpenAI 兼容服务。填写 API Key 后可自动发现模型列表。</p>
                </div>
                <div class="ui-section-actions">
                  <button class="ui-btn ui-btn--primary ui-btn--sm" @click="addProvider">＋ 添加</button>
                </div>
              </div>
              <div class="set-well set-well--flush">
                <div class="set-list">
                  <div v-if="providers.length === 0" class="set-empty">还没有 Provider，添加 API Key 后会自动发现模型。</div>
                  <div v-for="(p, i) in providers" :key="providerKey(p, i)" class="set-list-item">
                    <span class="set-list-icon">🏪</span>
                    <div class="set-list-item-main">
                      <div class="set-list-item-name">{{ p.name || '新 Provider' }}</div>
                      <div class="set-list-item-meta">{{ p.baseUrl || '未配置 Base URL' }} · {{ p.models?.length || 0 }} 模型</div>
                      <div v-if="p.models?.length" class="set-list-item-tags">
                        <span v-for="m in p.models.slice(0, 4)" :key="m" class="set-model-tag">{{ m }}</span>
                        <span v-if="p.models.length > 4" class="set-model-tag more">+{{ p.models.length - 4 }}</span>
                      </div>
                    </div>
                    <button class="ui-btn ui-btn--sm" @click="editProvider(i)">编辑</button>
                    <button class="ui-btn ui-btn--sm ui-btn--danger ui-btn--icon" title="删除" @click="removeProvider(i)">✕</button>
                  </div>
                </div>
              </div>
            </section>

            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">全局 LLM 生成参数</h2>
                  <p class="ui-section-sub">新建对话默认使用的采样参数。</p>
                </div>
              </div>
              <div class="set-well">
                <div class="set-row">
                  <div class="set-row-main">
                    <div class="set-row-title">流式输出</div>
                    <div class="set-row-desc">逐字返回响应，关闭后一次性返回完整内容。</div>
                  </div>
                  <button :class="['ui-switch', streaming ? 'on' : '']" @click="streaming = !streaming"></button>
                </div>
                <div class="set-slider-row">
                  <div class="set-slider-head">
                    <label class="ui-label">Temperature</label>
                    <span class="set-slider-val">{{ params.temperature }}</span>
                  </div>
                  <input type="range" min="0" max="2" step="0.1" v-model.number="params.temperature" />
                </div>
                <div class="set-slider-row">
                  <div class="set-slider-head">
                    <label class="ui-label">Top P</label>
                    <span class="set-slider-val">{{ params.topP }}</span>
                  </div>
                  <input type="range" min="0" max="1" step="0.05" v-model.number="params.topP" />
                </div>
                <div class="set-slider-row">
                  <div class="set-slider-head">
                    <label class="ui-label">Max Tokens</label>
                    <span class="set-slider-val">{{ params.maxTokens }}</span>
                  </div>
                  <input type="range" min="256" max="32768" step="256" v-model.number="params.maxTokens" />
                </div>
                <div class="set-slider-row">
                  <div class="set-slider-head">
                    <label class="ui-label">Presence Penalty</label>
                    <span class="set-slider-val">{{ params.presencePenalty }}</span>
                  </div>
                  <input type="range" min="-2" max="2" step="0.1" v-model.number="params.presencePenalty" />
                </div>
              </div>
            </section>

            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">相关页面</h2>
                  <p class="ui-section-sub">提示词、工具与智能体已有独立页面，设置页不再重复维护，前往对应页面管理。</p>
                </div>
              </div>
              <div class="set-jump-grid">
                <a class="set-jump" href="#/prompt">
                  <span class="set-jump-icon">📝</span>
                  <span class="set-jump-main">
                    <span class="set-jump-name">提示词库</span>
                    <span class="set-jump-path">/prompt</span>
                  </span>
                  <span class="set-jump-arrow">↗</span>
                </a>
                <a class="set-jump" href="#/tools">
                  <span class="set-jump-icon">🧰</span>
                  <span class="set-jump-main">
                    <span class="set-jump-name">工具中心</span>
                    <span class="set-jump-path">/tools</span>
                  </span>
                  <span class="set-jump-arrow">↗</span>
                </a>
                <a class="set-jump" href="#/agent">
                  <span class="set-jump-icon">🤖</span>
                  <span class="set-jump-main">
                    <span class="set-jump-name">智能体</span>
                    <span class="set-jump-path">/agent</span>
                  </span>
                  <span class="set-jump-arrow">↗</span>
                </a>
              </div>
            </section>
          </div>

          <!-- ==================== 对话体验 ==================== -->
          <div v-if="activeTab === 'agent'" class="set-pane">
            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">对话界面</h2>
                  <p class="ui-section-sub">历史消息的默认载入条数。</p>
                </div>
              </div>
              <div class="set-well">
                <div class="ui-field">
                  <label class="ui-label">默认显示消息条数（0 为无限制）</label>
                  <div class="set-inline-row">
                    <Dropdown :items="displayLimitOptions" :label="displayLimitLabel" @select="onSelectLimitItem" class="set-dropdown-wrp" />
                    <Input v-if="displayLimitSelect === '__custom__'" :model-value="String(displayLimitCustom)" type="number" placeholder="输入条数" @update:model-value="onInputCustom" class="set-input-wrp" />
                  </div>
                </div>
              </div>
            </section>

            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">主题</h2>
                  <p class="ui-section-sub">切换全局明暗配色。</p>
                </div>
              </div>
              <div class="set-well">
                <div class="set-radio-row"><label><input type="radio" v-model="theme" value="dark" /> 🌙 暗色</label></div>
                <div class="set-radio-row"><label><input type="radio" v-model="theme" value="light" /> ☀️ 亮色</label></div>
              </div>
            </section>

            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">排版</h2>
                  <p class="ui-section-sub">代码字体与界面质感。</p>
                </div>
              </div>
              <div class="set-well">
                <div class="ui-field">
                  <label class="ui-label">代码字体</label>
                  <input v-model="codeFont" class="ui-input" placeholder="JetBrains Mono" />
                </div>
                <div class="set-row">
                  <div class="set-row-main">
                    <div class="set-row-title">代码连字 Ligatures</div>
                    <div class="set-row-desc">启用字体连字，如 =&gt; 与 !=</div>
                  </div>
                  <button :class="['ui-switch', ligatures ? 'on' : '']" @click="ligatures = !ligatures"></button>
                </div>
                <div class="set-row">
                  <div class="set-row-main">
                    <div class="set-row-title">毛玻璃效果</div>
                    <div class="set-row-desc">面板与弹层使用半透明模糊背景。</div>
                  </div>
                  <button :class="['ui-switch', glass ? 'on' : '']" @click="glass = !glass"></button>
                </div>
              </div>
            </section>
          </div>

            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">语音朗读</h2>
                  <p class="ui-section-sub">系统语音按句暂停；第三方 TTS 用音频播放，暂停更可靠。<span class="tts-req">*</span> 为必填。</p>
                </div>
              </div>

              <div class="acct-field">
                <div class="acct-label-row"><span class="acct-label">语音来源</span></div>
                <Dropdown :items="ttsSourceOptions" :label="ttsSourceLabel" @select="onSelectTtsSource" class="acct-dropdown" />
              </div>

              <template v-if="ttsSource === 'system'">
                <div class="acct-field">
                  <div class="acct-label-row"><span class="acct-label">系统语音包</span></div>
                  <Dropdown :items="ttsVoiceOptions" :label="ttsVoiceLabel" @select="onSelectTtsVoice" class="acct-dropdown" />
                </div>
                <div class="acct-cols">
                  <div class="acct-field">
                    <div class="acct-label-row"><span class="acct-label">语速 {{ ttsRate.toFixed(1) }}x</span></div>
                    <input v-model.number="ttsRate" class="tts-range" type="range" min="0.5" max="2" step="0.1" />
                  </div>
                  <div class="acct-field">
                    <div class="acct-label-row"><span class="acct-label">音调 {{ ttsPitch.toFixed(1) }}</span></div>
                    <input v-model.number="ttsPitch" class="tts-range" type="range" min="0.5" max="2" step="0.1" />
                  </div>
                </div>
              </template>

              <template v-else>
                <div class="acct-field">
                  <div class="acct-label-row"><span class="acct-label">接口类型 <span class="tts-req">*</span></span></div>
                  <Dropdown :items="ttsApiTypeOptions" :label="ttsApiTypeLabel" @select="onSelectTtsApiType" class="acct-dropdown" />
                </div>

                <template v-if="ttsApiType === 'openai'">
                  <div class="acct-field">
                    <div class="acct-label-row"><span class="acct-label">Base URL <span class="tts-req">*</span></span></div>
                    <input v-model="ttsEndpoint" class="acct-input" placeholder="https://api.openai.com/v1" @blur="maybeLoadTtsVoices" />
                    <div class="acct-tip">只需要填到 <code>/v1</code>；AIOS 会自动请求 <code>/audio/speech</code>。兼容 OpenAI 的第三方服务也填它的 Base URL。</div>
                  </div>
                  <div class="acct-field">
                    <div class="acct-label-row"><span class="acct-label">API Key <span class="tts-req">*</span></span></div>
                    <input v-model="ttsKey" class="acct-input" type="password" placeholder="sk-..." />
                  </div>
                  <div class="acct-field">
                    <div class="acct-label-row"><span class="acct-label">模型 <span class="tts-req">*</span></span></div>
                    <input v-model="ttsModel" class="acct-input" placeholder="gpt-4o-mini-tts / tts-1" @blur="maybeLoadTtsVoices" />
                  </div>
                  <div class="acct-field">
                    <div class="acct-label-row">
                      <span class="acct-label">语音包 ID（选填）</span>
                      <button class="acct-help acct-help--text" type="button" :disabled="ttsApiLoading" @click="loadTtsApiVoices">{{ ttsApiLoading ? '加载中…' : '重新加载列表' }}</button>
                    </div>
                    <input v-model="ttsVoiceId" class="acct-input" placeholder="留空 = 接口默认；如 all / zh-CN-XiaoxiaoNeural" />
                    <div v-if="ttsApiVoiceOptions.length" class="tts-chips">
                      <button v-for="opt in ttsApiVoiceOptions" :key="opt.value" type="button" class="tts-chip" @click="ttsVoiceId = opt.value">{{ opt.label }}</button>
                    </div>
                    <div class="acct-tip">接口没有语音列表时留空即可；有列表会自动显示为下方按钮。</div>
                  </div>
                  <div class="set-row">
                    <div class="set-row-main">
                      <div class="set-row-title">使用参考音频（声音克隆）</div>
                      <div class="set-row-desc">只有支持零样本克隆的 TTS 接口才需要；普通 TTS 保持关闭。</div>
                    </div>
                    <button :class="['ui-switch', ttsUseRef ? 'on' : '']" @click="ttsUseRef = !ttsUseRef"></button>
                  </div>
                  <div v-if="ttsUseRef" class="acct-field">
                    <div class="acct-actions">
                      <input ref="ttsRefInput" type="file" accept="audio/*" style="display:none" @change="uploadTtsRef" />
                      <button class="acct-btn acct-btn--ghost" :disabled="ttsBusy" @click="ttsRefInput?.click()">选择参考音频</button>
                      <span class="acct-hint">{{ ttsRefName || '未选择' }}</span>
                    </div>
                    <div class="acct-tip">上传后会作为 <code>reference_audio</code> / <code>reference_audio_base64</code> 发送。</div>
                  </div>
                </template>

                <template v-else-if="ttsApiType === 'mimo'">
                  <div class="acct-field">
                    <div class="acct-label-row"><span class="acct-label">Base URL <span class="tts-req">*</span></span></div>
                    <input v-model="ttsEndpoint" class="acct-input" placeholder="https://api.xiaomimimo.com/v1" />
                    <div class="acct-tip">AIOS 会请求 <code>{Base URL}/chat/completions</code>，使用 <code>api-key</code> 请求头。</div>
                  </div>
                  <div class="acct-field">
                    <div class="acct-label-row"><span class="acct-label">API Key <span class="tts-req">*</span></span></div>
                    <input v-model="ttsKey" class="acct-input" type="password" placeholder="MiMo API Key" />
                  </div>
                  <div class="acct-field">
                    <div class="acct-label-row"><span class="acct-label">模型 <span class="tts-req">*</span></span></div>
                    <input v-model="ttsModel" class="acct-input" placeholder="mimo-v2.5-tts / mimo-v2.5-tts-voiceclone" />
                    <div class="tts-chips">
                      <button v-for="m in MIMO_MODELS" :key="m" type="button" class="tts-chip" @click="ttsModel = m">{{ m }}</button>
                    </div>
                  </div>
                  <div v-if="ttsModel === 'mimo-v2.5-tts'" class="acct-field">
                    <div class="acct-label-row"><span class="acct-label">音色（选填，默认 mimo_default）</span></div>
                    <input v-model="ttsVoiceId" class="acct-input" placeholder="mimo_default / 冰糖 / 茉莉 / 苏打 / 白桦 / Mia…" />
                    <div class="tts-chips">
                      <button v-for="v in MIMO_VOICES" :key="v" type="button" class="tts-chip" @click="ttsVoiceId = v">{{ v }}</button>
                    </div>
                  </div>
                  <div v-if="ttsModel === 'mimo-v2.5-tts-voicedesign'" class="acct-field">
                    <div class="acct-label-row"><span class="acct-label">音色描述 <span class="tts-req">*</span></span></div>
                    <input v-model="ttsInstruction" class="acct-input" placeholder="例如：温柔、低沉、略带磁性的女声" />
                  </div>
                  <div v-if="ttsModel === 'mimo-v2.5-tts-voiceclone'" class="set-row">
                    <div class="set-row-main">
                      <div class="set-row-title">使用参考音频（声音克隆）</div>
                      <div class="set-row-desc">voiceclone 模型必须上传 10 秒左右的 mp3/wav 人声。</div>
                    </div>
                    <button :class="['ui-switch', ttsUseRef ? 'on' : '']" @click="ttsUseRef = !ttsUseRef"></button>
                  </div>
                  <div v-if="ttsModel === 'mimo-v2.5-tts-voiceclone' && ttsUseRef" class="acct-field">
                    <div class="acct-actions">
                      <input ref="ttsRefInput" type="file" accept="audio/*" style="display:none" @change="uploadTtsRef" />
                      <button class="acct-btn acct-btn--ghost" :disabled="ttsBusy" @click="ttsRefInput?.click()">选择参考音频</button>
                      <span class="acct-hint">{{ ttsRefName || '未选择' }}</span>
                    </div>
                  </div>
                </template>

                <template v-else>
                  <div class="acct-field">
                    <div class="acct-label-row"><span class="acct-label">URL 模板 <span class="tts-req">*</span></span></div>
                    <input v-model="ttsEndpoint" class="acct-input" placeholder="https://tts.example.com/speak?text={text}" />
                    <div class="acct-tip">必须包含 <code>{text}</code>，AIOS 会把文本替换进去后发起 GET。</div>
                  </div>
                  <div class="acct-field">
                    <div class="acct-label-row"><span class="acct-label">API Key（选填）</span></div>
                    <input v-model="ttsKey" class="acct-input" type="password" placeholder="需要鉴权时填写" />
                  </div>
                  <div class="acct-field">
                    <div class="acct-label-row"><span class="acct-label">语音参数（选填）</span></div>
                    <input v-model="ttsVoiceId" class="acct-input" placeholder="接口需要的 voice / speaker 参数" />
                  </div>
                </template>
              </template>

              <div class="acct-actions">
                <button class="acct-btn" :disabled="ttsBusy" @click="testTts">{{ ttsBusy ? '合成中…' : '试听' }}</button>
              </div>
              <p v-if="!ttsSupported && ttsSource === 'system'" class="acct-hint">当前浏览器不支持系统语音；可改用第三方 TTS。</p>
              <p v-if="ttsMsg" class="acct-msg">{{ ttsMsg }}</p>
            </section>
          </div>

          <!-- ==================== 数据与安全 ==================== -->

          <!-- ==================== 关于 ==================== -->
          <!-- ==================== 邮件与安全（管理员） ==================== -->
          <div v-if="activeTab === 'mailsec' && isAdmin" class="set-pane">
            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">邮件与注册</h2>
                  <p class="ui-section-sub">注册验证码、找回密码用的发信配置；仅管理员可见。</p>
                </div>
              </div>
              <div class="acct-field">
                <div class="acct-label-row"><span class="acct-label">邮箱服务商</span></div>
                <Dropdown :items="mailProviderOptions" :label="mailProviderLabel" @select="onSelectMailProvider" class="acct-dropdown" />
              </div>
              <div class="acct-cols">
                <div class="acct-field">
                  <div class="acct-label-row"><span class="acct-label">SMTP 服务器</span></div>
                  <input v-model="mailHost" class="acct-input" placeholder="smtp.qq.com" />
                </div>
                <div class="acct-field">
                  <div class="acct-label-row"><span class="acct-label">端口</span></div>
                  <input v-model="mailPort" class="acct-input" type="number" placeholder="465" />
                </div>
              </div>
              <div class="acct-field">
                <div class="acct-label-row"><span class="acct-label">发件邮箱 / SMTP 用户名</span></div>
                <input v-model="mailUser" class="acct-input" placeholder="you@foxmail.com" />
              </div>
              <div class="acct-field">
                <div class="acct-label-row"><span class="acct-label">SMTP 授权码</span></div>
                <input v-model="mailPass" class="acct-input" type="password" :placeholder="mailConfigured ? '已保存；留空表示不修改' : '授权码（不是登录密码）'" />
              </div>
              <div class="acct-field">
                <div class="acct-label-row"><span class="acct-label">发件人地址（From）</span></div>
                <input v-model="mailFrom" class="acct-input" placeholder="you@foxmail.com" />
              </div>
              <div class="set-row">
                <div class="set-row-main">
                  <div class="set-row-title">使用 SSL（465 端口）</div>
                  <div class="set-row-desc">QQ/163 开；Gmail/Outlook 的 587 端口关。</div>
                </div>
                <button :class="['ui-switch', mailSsl ? 'on' : '']" @click="mailSsl = !mailSsl"></button>
              </div>
              <div class="acct-field">
                <div class="acct-label-row"><span class="acct-label">允许注册的邮箱（每行一个）</span></div>
                <textarea v-model="mailAllowedText" class="acct-input acct-textarea" placeholder="someone@gmail.com&#10;another@outlook.com"></textarea>
              </div>
              <div class="set-row">
                <div class="set-row-main">
                  <div class="set-row-title">允许自助注册</div>
                  <div class="set-row-desc">关闭时只有白名单邮箱可以注册。</div>
                </div>
                <button :class="['ui-switch', mailAllow ? 'on' : '']" @click="mailAllow = !mailAllow"></button>
              </div>
              <div class="acct-actions">
                <button class="acct-btn" :disabled="mailBusy" @click="saveMailConfig">保存邮件配置</button>
                <input v-model="testTo" class="acct-input acct-inline" placeholder="测试收件邮箱" />
                <button class="acct-btn acct-btn--ghost" :disabled="mailBusy" @click="testMail">发送测试邮件</button>
              </div>
              <p v-if="mailMsg" class="acct-msg">{{ mailMsg }}</p>
            </section>

            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">登录安全</h2>
                  <p class="ui-section-sub">登录失败锁定与限流；仅管理员可调。</p>
                </div>
              </div>
              <div class="set-row">
                <div class="set-row-main">
                  <div class="set-row-title">登录失败锁定</div>
                  <div class="set-row-desc">连续 5 次错误锁 15 分钟。</div>
                </div>
                <button :class="['ui-switch', securityLockout ? 'on' : '']" @click="securityLockout = !securityLockout"></button>
              </div>
              <div class="set-row">
                <div class="set-row-main">
                  <div class="set-row-title">登录 / 注册限流</div>
                  <div class="set-row-desc">同一 IP 10 分钟内的尝试次数限制。</div>
                </div>
                <button :class="['ui-switch', securityRateLimit ? 'on' : '']" @click="securityRateLimit = !securityRateLimit"></button>
              </div>
              <div class="acct-actions">
                <button class="acct-btn" :disabled="securityBusy" @click="saveSecurityConfig">保存安全开关</button>
              </div>
              <p v-if="securityMsg" class="acct-msg">{{ securityMsg }}</p>
            </section>
          </div>

          <!-- ==================== 管理员运维 ==================== -->
          <div v-if="activeTab === 'data' && isAdmin" class="set-pane">
            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">存储与高级</h2>
                  <p class="ui-section-sub">仅管理员可见的运维信息与开关。</p>
                </div>
              </div>
            </section>

<section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">存储统计</h2>
                </div>
              </div>
              <div class="set-well">
                <div class="set-stat-row"><span>本地数据</span><span>{{ storageUsed }}MB / {{ storageTotal }}MB</span></div>
                <div class="set-stat-row"><span>会话数量</span><span>{{ sessionCount }}</span></div>
                <div class="set-stat-row"><span>缓存大小</span><span>{{ cacheSize }}MB</span></div>
              </div>
            </section>

<section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">开发者模式</h2>
                  <p class="ui-section-sub">开启后可在主界面查看实时 HTTP 请求日志。</p>
                </div>
              </div>
              <div class="set-well">
                <div class="set-row">
                  <div class="set-row-main">
                    <div class="set-row-title">Dev Console</div>
                    <div class="set-row-desc">展示每一条请求的状态、耗时与响应。</div>
                  </div>
                  <button :class="['ui-switch', devMode ? 'on' : '']" @click="devMode = !devMode"></button>
                </div>
              </div>
            </section>


          </div>

          <div v-if="activeTab === 'data' && !isAdmin" class="set-pane">
            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">数据与授权</h2>
                  <p class="ui-section-sub">这里只影响你自己的设置与本会话的工具授权。</p>
                </div>
              </div>
            </section>

<section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">执行授权</h2>
                  <p class="ui-section-sub">工具中心手动执行时勾选「本会话记住」产生的授权；撤销后该会话下次调用需要重新审批。</p>
                </div>
                <div class="ui-section-actions">
                  <button class="ui-btn ui-btn--sm" :disabled="grantsLoading" @click="loadGrants">
                    {{ grantsLoading ? '加载中…' : '刷新' }}
                  </button>
                </div>
              </div>

              <div class="set-well set-well--flush">
                <div v-if="grantsLoading" class="grant-skel">
                  <div v-for="i in 3" :key="i" class="ui-skeleton grant-skel-row"></div>
                </div>

                <div v-else-if="grantsError" class="grant-error">
                  <span>{{ grantsError }}</span>
                  <button class="ui-btn ui-btn--sm" @click="loadGrants">重试</button>
                </div>

                <div v-else-if="!grants.length" class="ui-empty grant-empty">
                  <div class="ui-empty-icon">🔐</div>
                  <div class="ui-empty-title">暂无会话级授权</div>
                  <div class="ui-empty-desc">在工具中心手动执行并勾选「本会话记住该工具」后，授权记录会出现在这里，可随时撤销。</div>
                </div>

                <div v-else class="set-list">
                  <div v-for="g in grants" :key="grantKey(g)" class="set-list-item">
                    <span class="set-list-icon">🔐</span>
                    <div class="set-list-item-main">
                      <div class="set-list-item-name">
                        <code class="grant-tool">{{ g.tool }}</code>
                      </div>
                      <div class="set-list-item-meta">
                        会话 {{ shortGrantId(g.session_id) }}<template v-if="g.run_id"> · run {{ shortGrantId(g.run_id, 10) }}</template>
                      </div>
                    </div>
                    <span class="grant-time" :title="grantFmtAbs(g.granted_at)">{{ grantFmtRel(g.granted_at) }}</span>
                    <button
                      class="ui-btn ui-btn--sm ui-btn--danger"
                      :disabled="revokingGrantKey === grantKey(g)"
                      @click="revokeGrant(g)"
                    >{{ revokingGrantKey === grantKey(g) ? '撤销中…' : '撤销' }}</button>
                  </div>
                </div>
              </div>

              <div v-if="grantsActionError" class="grant-action-error">{{ grantsActionError }}</div>
              <div v-if="grantsNotice" class="set-hint grant-notice">{{ grantsNotice }}</div>
            </section>

<section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">数据管理</h2>
                  <p class="ui-section-sub">高危操作，执行前请确认。</p>
                </div>
                <div class="ui-section-actions">
                  <span class="ui-badge ui-badge--bad">危险操作</span>
                </div>
              </div>
              <div class="set-well set-danger-well">
                <p class="set-danger-text">此操作将重置设置数据，不会删除会话文件。</p>
                <button class="ui-btn ui-btn--danger" @click="showNuke = true">💣 重置所有设置</button>
              </div>
            </section>
          </div>

          <div v-if="activeTab === 'account'" class="set-pane">
            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">聊天性能</h2>
                  <p class="ui-section-sub">影响首字延迟的两项开关，修改后自动保存。</p>
                </div>
              </div>
              <div class="set-row">
                <div class="set-row-main">
                  <div class="set-row-title">深度思考</div>
                  <div class="set-row-desc">关闭后模型跳过 reasoning，首字明显更快；需要复杂推理时再打开。</div>
                </div>
                <button :class="['ui-switch', thinking ? 'on' : '']" @click="thinking = !thinking"></button>
              </div>
              <div class="set-row">
                <div class="set-row-main">
                  <div class="set-row-title">自动工具选择</div>
                  <div class="set-row-desc">仅在检测到工具意图时携带工具 schema，普通闲聊不再上传 12 个工具定义。</div>
                </div>
                <button :class="['ui-switch', autoTools ? 'on' : '']" @click="autoTools = !autoTools"></button>
              </div>
            </section>

            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">账号安全</h2>
                  <p class="ui-section-sub">当前登录账号：{{ accountEmail || '本机访问' }}</p>
                </div>
              </div>
              <div class="acct-grid">
                <input v-model="oldPassword" class="acct-input" type="password" placeholder="当前密码" />
                <input v-model="newPassword" class="acct-input" type="password" placeholder="新密码（≥8 位，含字母和数字）" />
                <button class="acct-btn" :disabled="accountBusy" @click="changePassword">修改密码</button>
              </div>
              <div class="acct-grid">
                <input v-model="emailPassword" class="acct-input" type="password" placeholder="当前密码" />
                <input v-model="newEmail" class="acct-input" type="email" placeholder="新邮箱" />
                <button class="acct-btn" :disabled="accountBusy" @click="changeEmail">修改邮箱</button>
              </div>
              <div class="acct-actions">
                <button class="acct-btn acct-btn--ghost" @click="logoutNow">退出登录</button>
              </div>
              <p v-if="accountMsg" class="acct-msg">{{ accountMsg }}</p>
            </section>

            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">{{ isAdmin ? '远程执行器（BYO）' : '执行服务器' }}</h2>
                  <p class="ui-section-sub">
                    选择公网 SSH 服务器，或在自己的电脑运行 AIOS Agent 主动连接。普通账号不会在 AIOS 主机执行代码。
                  </p>
                </div>
                <div class="ui-section-actions">
                  <button class="acct-doc-toggle" @click="openExecutorDocs">
                    📖 配置指南
                  </button>
                </div>
              </div>

              <div class="acct-field">
                <div class="acct-label-row">
                  <span class="acct-label">执行模式</span>
                  <button class="acct-help" type="button" :aria-expanded="!!helpOpen.mode" @click="toggleHelp('mode')">?</button>
                </div>
                <Dropdown :items="executorModeOptions" :label="executorModeLabel" @select="onSelectExecutorMode" class="acct-dropdown" />
                <div v-if="helpOpen.mode" class="acct-tip">
                  选择「使用我的服务器」后填写下面的信息；不启用时只能聊天，不能执行工具。
                </div>
              </div>

              <div v-if="!isOwner" class="acct-field">
                <div class="acct-label-row"><span class="acct-label">我的持久数据存放位置</span></div>
                <Dropdown :items="storageModeOptions" :label="storageModeLabel" @select="onSelectStorageMode" class="acct-dropdown" />
                <div class="acct-tip">默认保存在 AIOS 实例的账号目录；选择远程后，聊天记录与媒体写到你自己的服务器。配置 SSH 后可选择迁移已有数据。</div>
              </div>
              <div v-if="showStorageMigration" class="acct-tip acct-tip--choice">
                发现已有聊天记录/媒体。是否现在复制到你的远程服务器？本地源数据会保留，远程复制成功后才切换存储。
                <div class="acct-actions">
                  <button class="acct-btn" :disabled="storageBusy" @click="migrateStorage">{{ storageBusy ? '迁移中…' : '迁移并切换' }}</button>
                  <button class="acct-btn acct-btn--ghost" :disabled="storageBusy" @click="keepLocalStorage">继续保存在本机</button>
                </div>
                <span v-if="storageMsg">{{ storageMsg }}</span>
              </div>
              <div class="acct-field">
                <div class="acct-label-row">
                  <span class="acct-label">服务器地址</span>
                  <button class="acct-help" type="button" :aria-expanded="!!helpOpen.host" @click="toggleHelp('host')">?</button>
                </div>
                <input v-model="executorHost" class="acct-input" placeholder="公网 IP，例如 1.2.3.4" />
                <div v-if="helpOpen.host" class="acct-tip">
                  填写服务器的公网 IP 或域名；请不要填 127.0.0.1 或内网地址。
                </div>
              </div>

              <div class="acct-cols">
                <div class="acct-field">
                  <div class="acct-label-row">
                    <span class="acct-label">端口</span>
                    <button class="acct-help" type="button" :aria-expanded="!!helpOpen.port" @click="toggleHelp('port')">?</button>
                  </div>
                  <input v-model="executorPort" class="acct-input" type="number" placeholder="22" />
                  <div v-if="helpOpen.port" class="acct-tip">默认 22；云厂商改成自定义端口时填实际端口。</div>
                </div>
                <div class="acct-field">
                  <div class="acct-label-row">
                    <span class="acct-label">登录用户</span>
                    <button class="acct-help" type="button" :aria-expanded="!!helpOpen.user" @click="toggleHelp('user')">?</button>
                  </div>
                  <input v-model="executorUser" class="acct-input" placeholder="aios" />
                  <div v-if="helpOpen.user" class="acct-tip">服务器上的登录用户名，一般填 aios。</div>
                </div>
              </div>

              <div class="acct-field">
                <div class="acct-label-row">
                  <span class="acct-label">运行环境</span>
                  <button class="acct-help" type="button" :aria-expanded="!!helpOpen.image" @click="toggleHelp('image')">?</button>
                </div>
                <input v-model="executorImage" class="acct-input" placeholder="aios-runner:latest" />
                <div v-if="helpOpen.image" class="acct-tip">服务器上准备好的运行环境名称，保持默认即可。</div>
              </div>

              <div class="acct-field">
                <div class="acct-label-row">
                  <span class="acct-label">服务器指纹</span>
                  <button class="acct-help" type="button" :aria-expanded="!!helpOpen.hostkey" @click="toggleHelp('hostkey')">?</button>
                </div>
                <textarea v-model="executorHostKey" class="acct-input acct-textarea" placeholder="把服务器管理员给你的那一整行粘贴到这里"></textarea>
                <div v-if="helpOpen.hostkey" class="acct-tip">
                  用来确认连接的是你的服务器；把服务器管理员给你的那一整行粘进来。
                </div>
              </div>

              <div class="acct-actions">
                <button class="acct-btn" :disabled="executorBusy" @click="saveExecutor">保存配置</button>
                <button class="acct-btn" :disabled="executorBusy" @click="testExecutor">测试连接</button>
                <button class="acct-btn acct-btn--ghost" :disabled="executorBusy" @click="loadSshKey">获取接入密钥</button>
              </div>
              <p v-if="executorMsg" class="acct-msg">{{ executorMsg }}</p>
              <pre v-if="executorPublicKey" class="acct-key">{{ executorPublicKey }}</pre>

              <template v-if="executorMode === 'device'">
                <div class="acct-field device-pair">
                  <div class="acct-label-row"><span class="acct-label">配对本机设备</span></div>
                  <p class="acct-hint">支持 Windows/macOS/Linux：在目标设备安装 Python Agent，输入一次性配对码后保持 Agent 运行。每个任务默认需要本机确认；设备关机或 Agent 退出时不可执行。Android 目前需前台运行；iOS/鸿蒙暂不支持。</p>
                  <div class="acct-actions">
                    <button class="acct-btn" :disabled="deviceBusy" @click="createDevicePairing">生成配对码</button>
                    <code v-if="pairingCode" class="device-pair-code">{{ pairingCode }}</code>
                  </div>
                  <p v-if="pairingError" class="acct-msg">{{ pairingError }}</p>
                </div>
                <div v-if="pairedDevices.length" class="device-list">
                  <div v-for="d in pairedDevices" :key="d.device_id" class="device-row">
                    <span>{{ d.name }} · {{ d.platform }} · {{ d.online ? '在线' : '离线' }}</span>
                    <button class="acct-btn acct-btn--ghost" :disabled="deviceBusy" @click="revokeDevice(d.device_id)">撤销</button>
                  </div>
                </div>
              </template>
            </section>
          </div>

          <div v-if="activeTab === 'about'" class="set-pane">
            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">项目信息</h2>
                  <p class="ui-section-sub">Personal AI OS — 本地优先的个人智能中枢。</p>
                </div>
              </div>
              <div class="set-well">
                <div class="about-info-grid">
                  <div class="about-info-item">
                    <span class="about-info-label">版本</span>
                    <span class="about-info-value">{{ appVersion }}</span>
                  </div>
                  <div class="about-info-item">
                    <span class="about-info-label">构建</span>
                    <span class="about-info-value">{{ buildDate }}</span>
                  </div>
                  <div class="about-info-item">
                    <span class="about-info-label">协议</span>
                    <a class="about-info-value about-link" href="https://www.gnu.org/licenses/gpl-3.0.html" target="_blank" rel="noopener">GPL-3.0 ↗</a>
                  </div>
                  <div class="about-info-item">
                    <span class="about-info-label">作者</span>
                    <span class="about-info-value">qixidalao</span>
                  </div>
                </div>
                <div class="about-desc">{{ aboutDesc }}</div>
                <div class="about-motto">{{ aboutMotto }}</div>
              </div>
            </section>

            <template v-if="!isAdmin">
              <section class="ui-section">
                <div class="ui-section-head">
                  <div>
                    <h2 class="ui-section-title">你可以做什么</h2>
                  </div>
                </div>
                <div class="set-well">
                  <ul class="about-list">
                    <li>和 AI 对话，保存自己的历史会话；</li>
                    <li>上传图片或文件，让 AI 帮你处理；</li>
                    <li>需要执行代码时，在「我的账号 → 执行服务器」里配置自己的服务器；</li>
                    <li>在「我的账号」里修改密码、邮箱，或退出登录。</li>
                  </ul>
                </div>
              </section>
            </template>

            <template v-if="isAdmin">
            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">当前能力</h2>
                  <p class="ui-section-sub">这一版实际具备、且经过测试的能力。</p>
                </div>
              </div>
              <div class="set-well">
                <div class="about-thanks-list">
                  <span v-for="(cap, i) in capabilities" :key="i" class="about-thanks-tag">{{ cap }}</span>
                </div>
              </div>
            </section>

            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">技术栈</h2>
                </div>
              </div>
              <div class="set-well">
                <div class="about-tech-grid">
                  <div v-for="(v, k) in techStack" :key="k" class="about-tech-item">
                    <span class="about-tech-key">{{ k }}</span>
                    <span class="about-tech-val">{{ v }}</span>
                  </div>
                </div>
              </div>
            </section>

            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">安全与边界</h2>
                  <p class="ui-section-sub">当前部署的安全模型。</p>
                </div>
              </div>
              <div class="set-well">
                <ul class="about-list">
                  <li v-for="(note, i) in securityNotes" :key="i">{{ note }}</li>
                </ul>
              </div>
            </section>

            </template>

            <section v-if="isAdmin && specialThanks.length" class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">特别感谢</h2>
                </div>
              </div>
              <div class="set-well">
                <div class="about-thanks-list">
                  <span v-for="(name, i) in specialThanks" :key="i" class="about-thanks-tag">{{ name }}</span>
                </div>
              </div>
            </section>

            <section class="ui-section">
              <div class="ui-section-head">
                <div>
                  <h2 class="ui-section-title">API 入口</h2>
                  <p class="ui-section-sub">需要登录 Cookie 或 Bearer Token，健康检查除外。</p>
                </div>
                <div class="ui-section-actions">
                  <span class="about-api-badge">/api/v1</span>
                </div>
              </div>
              <div class="set-well">
                <div v-for="group in apiGroups" :key="group.title" class="about-api-group">
                  <div class="about-api-group-title">{{ group.title }}</div>
                  <div v-for="item in group.items" :key="item.path" class="about-api-item">
                    <code class="about-api-path">{{ item.path }}</code>
                    <span class="about-api-desc">{{ item.desc }}</span>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>

    <!-- ==================== 执行器文档弹层 ==================== -->
    <div v-if="showExecutorDocModal" class="set-modal-overlay" @click.self="showExecutorDocModal = false">
      <div class="set-modal exec-doc-modal">
        <div class="set-modal-head">
          <div>
            <div class="ui-eyebrow">EXECUTOR GUIDE</div>
            <div class="set-modal-title">执行服务器配置指南</div>
          </div>
          <button class="ui-btn ui-btn--ghost ui-btn--sm ui-btn--icon" title="关闭" @click="showExecutorDocModal = false">✕</button>
        </div>
        <div class="exec-doc-body">
          <div v-if="executorDocLoading" class="exec-doc-loading">正在加载文档…</div>
          <div v-else-if="executorDocError" class="exec-doc-loading">{{ executorDocError }}</div>
          <div v-else v-html="executorDocHtml"></div>
        </div>
      </div>
    </div>

    <!-- ==================== Provider 编辑弹层 ==================== -->
    <div v-if="editingProvider !== null" class="set-modal-overlay" @click.self="closeProviderEditor">
      <div class="set-modal">
        <div class="set-modal-head">
          <div>
            <div class="ui-eyebrow">PROVIDER</div>
            <div class="set-modal-title">编辑 Provider</div>
          </div>
          <button class="ui-btn ui-btn--ghost ui-btn--sm ui-btn--icon" title="关闭" @click="closeProviderEditor">✕</button>
        </div>
        <div class="ui-field">
          <label class="ui-label">名称</label>
          <input v-model="editingProvider.name" class="ui-input" placeholder="OpenAI / DeepSeek / OpenRouter" />
        </div>
        <div class="ui-field">
          <label class="ui-label">API Key</label>
          <input v-model="editingProvider.key" type="password" class="ui-input" placeholder="sk-..." />
        </div>
        <div class="ui-field">
          <label class="ui-label">Base URL</label>
          <input v-model="editingProvider.baseUrl" class="ui-input" placeholder="https://api.openai.com" />
        </div>
        <div class="ui-field">
          <label class="ui-label">模型列表</label>
          <div class="set-inline-row">
            <input v-model="editingProvider.modelsStr" class="ui-input" placeholder="自动加载或逗号分隔" />
            <button class="ui-btn ui-btn--sm set-refresh-btn" :disabled="modelLoading" @click="loadEditingProviderModels">{{ modelLoading ? '加载中' : '刷新' }}</button>
          </div>
          <div v-if="modelLoadHint" :class="['set-hint', modelLoadOk ? 'ok' : '']">{{ modelLoadHint }}</div>
        </div>
        <div class="ui-field">
          <label class="ui-label">余额查询路径</label>
          <input v-model="editingProvider.billingPath" class="ui-input" placeholder="/v1/dashboard/billing" />
        </div>
        <div class="ui-field">
          <label class="ui-label">JSONPath 解析</label>
          <input v-model="editingProvider.jsonPath" class="ui-input" placeholder="$.data.total_available" />
        </div>
        <div class="set-modal-actions">
          <button class="ui-btn ui-btn--ghost" @click="closeProviderEditor">取消</button>
          <button class="ui-btn ui-btn--primary" :disabled="modelLoading" @click="saveProvider">保存</button>
        </div>
      </div>
    </div>

    <!-- ==================== 重置确认弹层 ==================== -->
    <div v-if="showNuke" class="set-modal-overlay" @click.self="showNuke = false">
      <div class="set-modal">
        <div class="set-modal-head">
          <div>
            <div class="ui-eyebrow">DANGER ZONE</div>
            <div class="set-modal-title">确认重置</div>
          </div>
          <span class="ui-badge ui-badge--bad">不可撤销</span>
        </div>
        <p class="set-modal-text">确定要重置所有设置吗？Provider、Prompt、外观等配置会恢复默认。</p>
        <div class="set-modal-actions">
          <button class="ui-btn ui-btn--ghost" @click="showNuke = false">取消</button>
          <button class="ui-btn ui-btn--danger" @click="nukeAll">确认重置</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import Input from '../components/ui/Input/Input.vue'
import Dropdown from '../components/ui/Dropdown/Dropdown.vue'
import { marked } from 'marked'

type Provider = {
  name: string
  key: string
  baseUrl: string
  models: string[]
  modelsStr?: string
  billingPath?: string
  jsonPath?: string
}

const API = window.location.origin
const route = useRoute()
const isAdmin = computed(() => route.path.startsWith('/admin'))
const isMobile = ref(window.innerWidth < 768)
const adminTabs = [
  { id: 'global', label: '模型与服务', icon: '🧠' },
  { id: 'mailsec', label: '邮件与安全', icon: '✉️' },
  { id: 'data', label: '数据与运维', icon: '🛠️' },
  { id: 'about', label: '关于', icon: 'ℹ️' },
]
const userTabs = [
  { id: 'global', label: '模型与服务', icon: '🧠' },
  { id: 'agent', label: '外观与对话', icon: '💬' },
  { id: 'account', label: '我的账号', icon: '👤' },
  { id: 'data', label: '数据与授权', icon: '📊' },
]
const tabs = computed(() => (isAdmin.value ? adminTabs : userTabs))
const activeTab = ref(isAdmin.value ? 'mailsec' : 'global')
watch(isAdmin, (admin) => { activeTab.value = admin ? 'mailsec' : 'global' })

async function apiGet(path: string) {
  const r = await fetch(`${API}${path}`)
  if (!r.ok) throw new Error(`GET ${path} ${r.status}`)
  return r.json()
}

async function apiPut(path: string, body: any) {
  const r = await fetch(`${API}${path}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(await responseError(r, `PUT ${path} ${r.status}`))
  return r.json()
}
const storageUsed = ref(256)
const storageTotal = ref(1024)
const sessionCount = ref(0)
const cacheSize = ref(128)
const devMode = ref(false)
const thinking = ref(false)
const autoTools = ref(true)
const isOwner = ref(false)
const accountEmail = ref('')
const accountMsg = ref('')
const accountBusy = ref(false)
const oldPassword = ref('')
const newPassword = ref('')
const emailPassword = ref('')
const newEmail = ref('')
const mailProvider = ref('custom')
const mailHost = ref('')
const mailPort = ref(465)
const mailUser = ref('')
const mailFrom = ref('')
const mailPass = ref('')
const mailSsl = ref(true)
const mailConfigured = ref(false)
const mailAllow = ref(false)
const mailAllowedText = ref('')
const mailMsg = ref('')
const mailBusy = ref(false)
const testTo = ref('')
const mailProviderOptions = [
  { label: 'QQ / Foxmail', value: 'qq', desc: 'smtp.qq.com · 465 SSL' },
  { label: 'Gmail', value: 'gmail', desc: 'smtp.gmail.com · 587 STARTTLS' },
  { label: '网易 163', value: '163', desc: 'smtp.163.com · 465 SSL' },
  { label: 'Outlook / Microsoft', value: 'outlook', desc: 'smtp.office365.com · 587 STARTTLS' },
  { label: '自定义', value: 'custom', desc: '手动填写服务器与端口' },
]
const mailProviderLabel = computed(() => mailProviderOptions.find(o => o.value === mailProvider.value)?.label || '自定义')
const ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window
const ttsSource = ref('system')
const ttsApiType = ref('openai')
const ttsApiTypeOptions = [
  { label: 'OpenAI 兼容接口', value: 'openai', desc: 'Base URL + Key + 模型 + 语音 ID' },
  { label: '小米 MiMo（Chat 音频）', value: 'mimo', desc: 'POST /chat/completions，返回 base64 音频' },
  { label: '自定义 URL 模板', value: 'template', desc: 'GET 一个包含 {text} 的地址' },
]
const ttsApiTypeLabel = computed(() => ttsApiTypeOptions.find(o => o.value === ttsApiType.value)?.label || 'OpenAI 兼容接口')
const ttsApiVoiceOptions = ref<{ label: string; value: string }[]>([])
const ttsApiVoiceLabel = computed(() => ttsApiVoiceOptions.value.find(o => o.value === ttsVoiceId.value)?.label || (ttsVoiceId.value || '请选择语音包'))
const ttsApiLoading = ref(false)
const ttsUseRef = ref(false)
const ttsInstruction = ref('')
const MIMO_MODELS = ['mimo-v2.5-tts', 'mimo-v2.5-tts-voicedesign', 'mimo-v2.5-tts-voiceclone']
const MIMO_VOICES = ['mimo_default', '冰糖', '茉莉', '苏打', '白桦', 'Mia', 'Chloe', 'Milo', 'Dean']
const ttsSourceOptions = [
  { label: '系统语音', value: 'system', desc: '浏览器自带，按句暂停' },
  { label: '第三方 TTS 接口', value: 'thirdparty', desc: 'URL 调用，音频播放可靠暂停' },
]
const ttsSourceLabel = computed(() => ttsSourceOptions.find(o => o.value === ttsSource.value)?.label || '系统语音')
const ttsEndpoint = ref('')
const ttsKey = ref('')
const ttsModel = ref('')
const ttsVoiceId = ref('')
const ttsRefName = ref('')
const ttsRefUrl = ref('')
const ttsMsg = ref('')
const ttsBusy = ref(false)
const ttsRefInput = ref<HTMLInputElement | null>(null)
const ttsVoiceOptions = ref<{ label: string; value: string }[]>([])
const ttsVoice = ref('')
const ttsRate = ref(1)
const ttsPitch = ref(1)
const ttsVoiceLabel = computed(() => ttsVoiceOptions.value.find(o => o.value === ttsVoice.value)?.label || '系统默认')
const securityLockout = ref(true)
const securityRateLimit = ref(true)
const securityMsg = ref('')
const securityBusy = ref(false)
const executorMode = ref('disabled')
const storageMode = ref('local')
const storageModeOptions = [
  { label: '保存在 AIOS 账号空间（默认）', value: 'local', desc: '由部署者的 AIOS 实例保管' },
  { label: '保存在我的远程服务器', value: 'remote', desc: '聊天记录与媒体复制到你自己的服务器' },
]
const storageModeLabel = computed(() => storageModeOptions.find(o => o.value === storageMode.value)?.label || storageModeOptions[0].label)
const showStorageMigration = ref(false)
const storageBusy = ref(false)
const storageMsg = ref('')
const previousStorageMode = ref('local')
const executorModeOptions = computed(() => [
  { label: '不启用（普通权限）', value: 'disabled', desc: '只聊天 / 自己的会话，不执行工具' },
  { label: '我的公网服务器（SSH）', value: 'ssh', desc: 'AIOS 通过 SSH 连接服务器' },
  { label: '我的本机设备（Agent）', value: 'device', desc: '设备主动连接 AIOS，不需要公网 IP' },
  ...(isAdmin.value ? [{ label: '使用本机（管理员）', value: 'local', desc: '在本机执行' }] : []),
])
const executorModeLabel = computed(() => executorModeOptions.value.find(o => o.value === executorMode.value)?.label || '不启用（普通权限）')
const showExecutorDocModal = ref(false)
const executorDocHtml = ref('')
const executorDocLoading = ref(false)
const executorDocError = ref('')
const helpOpen = reactive<Record<string, boolean>>({})
function toggleHelp(key: string) { helpOpen[key] = !helpOpen[key] }

function renderExecutorDoc(md: string): string {
  // 文档里的图片放到 frontend/public/executor-docs/，构建后路径为 /executor-docs/...
  // 弹层已有标题，去掉文档里的重复 H1
  const fixed = md.replace(/^# .*\n+/, '').replace(/assets\/executor\//g, '/executor-docs/')
  return marked.parse(fixed, { async: false }) as string
}

async function openExecutorDocs() {
  showExecutorDocModal.value = true
  if (executorDocHtml.value) return
  executorDocLoading.value = true
  executorDocError.value = ''
  try {
    const data = await apiGet('/api/v1/executor/docs')
    executorDocHtml.value = renderExecutorDoc(data.markdown || '')
  } catch (e: any) {
    executorDocError.value = `文档加载失败：${e?.message || e}`
  } finally {
    executorDocLoading.value = false
  }
}
function onSelectExecutorMode(item: any) { executorMode.value = item.value }
const executorHost = ref('')
const executorPort = ref(22)
const executorUser = ref('aios')
const executorImage = ref('aios-runner:latest')
const executorHostKey = ref('')
const pairedDevices = ref<any[]>([])
const pairingCode = ref('')
const pairingError = ref('')
const deviceBusy = ref(false)
const executorPublicKey = ref('')
const executorMsg = ref('')
const executorBusy = ref(false)
const showNuke = ref(false)
const loadingSettings = ref(true)

// 关于面板数据
const appVersion = 'v2.1.0'
const buildDate = '2026-11-11'
const aboutDesc = computed(() => isAdmin.value ? '个人 AI 工作台与本地智能中枢：聊天、Agent、工具、记忆、多用户与远程执行一体化。' : '个人 AI 工作台：聊天、记录、工具与记忆。')
const aboutMotto = '万物皆配置 · 万物皆事件 · 万物皆插件 · 万物皆流'
const capabilities = [
  '邮箱注册 / 登录', '30 天滑动会话', '多用户归属隔离（Phase 1）',
  'BYO SSH 执行器', 'bwrap 本地沙箱', '工具审批 / 审计',
  'Cloudflare Tunnel', 'SSE 逐字流式', '自动工具选择',
  '深度思考开关', 'SMTP 验证码', '本机免登录',
]
const securityNotes = [
  '所有 /api/* 与 WebSocket 由后端 ASGI 中间件鉴权，不是前端页面拦截。',
  '本机免登录仅限 loopback + Host 本机 + 无代理头；外部 forwarder 无法伪装。',
  '审批、手动工具执行、设置写入：仅 owner（或本机 / Bearer Token）。',
  'member 只能访问自己的会话与 runs；未配置远程执行器时禁止本地工具。',
  'member 的远程执行器只允许公网 SSH 服务器；填 127.0.0.1 会被拒绝。',
  '登录失败 5 次锁定 15 分钟；登录 / 注册有 IP 限流。',
]
const techStack = {
  '前端': 'Vue 3 + TypeScript + Vite',
  '后端': 'Python 3.14 / FastAPI',
  '存储': 'SQLite + JSON 会话文件',
  '执行': 'bwrap 沙箱 / BYO SSH runner',
  '网络': 'Cloudflare Tunnel / SSE',
  '鉴权': '邮箱账号 + scrypt + HttpOnly 会话',
}
const apiGroups = [
  { title: '🔐 认证', items: [
    { path: 'POST /api/v1/auth/login', desc: '邮箱登录' },
    { path: 'GET /api/v1/auth/me', desc: '当前账号' },
    { path: 'POST /api/v1/auth/logout', desc: '退出登录' },
  ]},
  { title: '💬 聊天', items: [
    { path: 'POST /api/v1/chat/stream', desc: '流式对话 SSE' },
    { path: 'GET /api/v1/sessions', desc: '会话列表（按归属过滤）' },
  ]},
  { title: '🖥 执行器', items: [
    { path: 'GET/PUT /api/v1/executor/config', desc: '远程执行器配置' },
    { path: 'POST /api/v1/executor/test', desc: '测试 SSH 连接' },
    { path: 'POST /api/v1/executor/run', desc: '远程执行任务' },
  ]},
  { title: '⚙️ 设置', items: [
    { path: 'GET /api/v1/settings', desc: '读取设置（member 脱敏）' },
    { path: 'PUT /api/v1/settings', desc: '保存设置（owner）' },
  ]},
  { title: '📎 其他', items: [
    { path: 'GET /api/v1/health', desc: '健康检查（公开）' },
    { path: 'GET /api/v1/runs', desc: 'Run 审计（按归属过滤）' },
  ]},
]
const specialThanks = ['Termux 社区', 'FastAPI', 'Vue.js', 'OpenAI', 'DeepSeek']

async function apiPost(path: string, body: any = {}) {
  const r = await fetch(`${API}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(await responseError(r, `POST ${path} ${r.status}`))
  return r.json()
}

async function responseError(r: Response, fallback: string) {
  try { const data = await r.json(); return data?.detail || data?.message || fallback }
  catch { return (await r.text().catch(() => '')) || fallback }
}
const agentParams = reactive({ temperature: 0.3, maxTokens: 4096, maxToolRounds: 6, agentPrompt: '' })
const params = reactive({ temperature: 0.7, topP: 0.9, maxTokens: 8192, presencePenalty: 0 })
const streaming = ref(true)
const providers = ref<Provider[]>([])
const prompts = ref<any[]>([])
const editingProvider = ref<Provider | null>(null)
const editingProviderIndex = ref<number | null>(null)
const modelLoading = ref(false)
const modelLoadHint = ref('')
const modelLoadOk = ref(false)
const agentTools = ref<any[]>([])
const theme = ref('dark')
const codeFont = ref('JetBrains Mono')
const ligatures = ref(true)
const glass = ref(false)
const displayLimit = ref(30)
const displayLimitSelect = ref<string | number>(30)
const displayLimitCustom = ref(30)
const displayLimitOptions = [
  { label: '0（无限制）', value: 0 },
  { label: '10 条', value: 10 },
  { label: '20 条', value: 20 },
  { label: '30 条', value: 30 },
  { label: '40 条', value: 40 },
  { label: '50 条', value: 50 },
  { label: '✏️ 自定义', value: '__custom__' },
]
const displayLimitLabel = computed(() => {
  const opt = displayLimitOptions.find(o => o.value === displayLimitSelect.value)
  return opt ? opt.label : `自定义（${displayLimit.value} 条）`
})
function onSelectLimitItem(item: any) {
  displayLimitSelect.value = item.value
  if (item.value === '__custom__') {
    displayLimit.value = displayLimitCustom.value || 30
  } else {
    displayLimit.value = item.value
  }
  autoSave()
}
function onInputCustom(val: string) {
  const num = parseInt(val, 10)
  if (!isNaN(num) && num >= 0) { displayLimitCustom.value = num; displayLimit.value = num; autoSave() }
}

const editingToolIdx = ref<number | null>(null)
const editingToolDesc = ref('')
const editingToolSchema = ref('')
const editingTool = computed(() => editingToolIdx.value !== null ? agentTools.value[editingToolIdx.value] : null)

function openToolSchema(i: number) {
  editingToolIdx.value = i
  const t = agentTools.value[i]
  editingToolDesc.value = t.description || ''
  editingToolSchema.value = typeof t.schema === 'string' ? t.schema : JSON.stringify(t.schema, null, 2)
}
function cancelToolSchema() { editingToolIdx.value = null; editingToolDesc.value = ''; editingToolSchema.value = '' }
function saveToolSchema() {
  if (editingToolIdx.value !== null) agentTools.value[editingToolIdx.value].description = editingToolDesc.value
  cancelToolSchema(); autoSave()
}

function providerKey(p: Provider, i: number) { return `${p.name || 'provider'}-${p.baseUrl || ''}-${i}` }

function normalizeModels(input: unknown): string[] {
  if (Array.isArray(input)) return Array.from(new Set(input.map(String).map(s => s.trim()).filter(Boolean)))
  if (typeof input === 'string') return Array.from(new Set(input.split(',').map(s => s.trim()).filter(Boolean)))
  return []
}

function addProvider() {
  modelLoadHint.value = ''; modelLoadOk.value = false
  editingProviderIndex.value = null
  editingProvider.value = { name: '', key: '', baseUrl: '', models: [], modelsStr: '', billingPath: '', jsonPath: '' }
}
function editProvider(i: number) {
  modelLoadHint.value = ''; modelLoadOk.value = false
  editingProviderIndex.value = i
  const p = providers.value[i]
  editingProvider.value = { ...p, models: normalizeModels(p.models), modelsStr: normalizeModels(p.models).join(',') }
}
function closeProviderEditor() { editingProvider.value = null; editingProviderIndex.value = null; modelLoadHint.value = ''; modelLoadOk.value = false }
function removeProvider(i: number) { providers.value.splice(i, 1); autoSave(); window.dispatchEvent(new CustomEvent('settings:providers-updated')) }

async function loadEditingProviderModels() {
  const p = editingProvider.value
  if (!p) return []
  if (!p.baseUrl?.trim()) { modelLoadOk.value = false; modelLoadHint.value = '请先填写 Base URL'; return [] }
  modelLoading.value = true; modelLoadOk.value = false; modelLoadHint.value = '正在请求 /v1/models ...'
  try {
    const data = await apiPost('/api/v1/settings/providers/models', { baseUrl: p.baseUrl.trim(), key: p.key || '' })
    const loaded = normalizeModels(data.models)
    const manual = normalizeModels(p.modelsStr)
    const merged = Array.from(new Set([...loaded, ...manual]))
    p.models = merged; p.modelsStr = merged.join(',')
    modelLoadOk.value = true; modelLoadHint.value = `已自动加载 ${loaded.length} 个模型${manual.length ? '，并合并手填模型' : ''}`
    return merged
  } catch (e: any) {
    const manual = normalizeModels(p.modelsStr)
    p.models = manual; modelLoadOk.value = false
    modelLoadHint.value = `自动加载失败：${e?.message || e}。已保留手填模型。`
    return manual
  } finally { modelLoading.value = false }
}

async function saveProvider() {
  if (!editingProvider.value) return
  const p = editingProvider.value
  await loadEditingProviderModels()
  const clean: Provider = {
    name: p.name?.trim() || '未命名 Provider', key: p.key || '', baseUrl: p.baseUrl?.trim() || '',
    models: normalizeModels(p.modelsStr || p.models), billingPath: p.billingPath || '', jsonPath: p.jsonPath || '',
  }
  if (editingProviderIndex.value !== null && editingProviderIndex.value >= 0) providers.value.splice(editingProviderIndex.value, 1, clean)
  else providers.value.push(clean)
  closeProviderEditor(); autoSave(); window.dispatchEvent(new CustomEvent('settings:providers-updated'))
}

function addPrompt() { prompts.value.push({ name: '新 Prompt', content: '', isDefault: false }); autoSave() }
function setDefaultPrompt(i: number) { prompts.value.forEach((p, idx) => { p.isDefault = idx === i }); autoSave() }

const editingPromptIndex = ref<number | null>(null)
const editingPrompt = reactive({ name: '', content: '' })
function editPrompt(i: number) { editingPromptIndex.value = i; const p = prompts.value[i]; editingPrompt.name = p.name || ''; editingPrompt.content = p.content || '' }
function cancelEditPrompt() { editingPromptIndex.value = null; editingPrompt.name = ''; editingPrompt.content = '' }
function savePrompt() {
  const i = editingPromptIndex.value
  if (i === null) return
  prompts.value[i].name = editingPrompt.name; prompts.value[i].content = editingPrompt.content
  cancelEditPrompt(); autoSave()
}
function removePrompt(i: number) { prompts.value.splice(i, 1); if (editingPromptIndex.value === i) cancelEditPrompt(); autoSave() }

function applySettings(data: any) {
  if (!data || typeof data !== 'object') return
  if (data.params) Object.assign(params, data.params)
  streaming.value = data.streaming !== false
  providers.value = Array.isArray(data.providers) ? data.providers.map((p: any) => ({ ...p, models: normalizeModels(p.models) })) : []
  prompts.value = Array.isArray(data.prompts) ? data.prompts : []
  agentTools.value = Array.isArray(data.agentTools) ? data.agentTools : []
  if (data.agentParams) Object.assign(agentParams, data.agentParams)
  theme.value = data.theme || 'dark'
  codeFont.value = data.codeFont || 'JetBrains Mono'
  ligatures.value = data.ligatures !== undefined ? !!data.ligatures : true
  glass.value = !!data.glass
  devMode.value = !!data.devMode
  thinking.value = data.thinking === true
  autoTools.value = data.autoTools !== false
  const dl = data.displayLimit
  if (typeof dl === 'number' && dl >= 0) {
    displayLimit.value = dl
    if ([0, 10, 20, 30, 40, 50].includes(dl)) displayLimitSelect.value = dl
    else { displayLimitSelect.value = '__custom__'; displayLimitCustom.value = dl }
  }
}

async function nukeAll() {
  showNuke.value = false; storageUsed.value = 0
  try { const data = await apiPost('/api/v1/settings/reset'); applySettings(data.settings || data); alert('所有设置已重置为默认') }
  catch (e) { console.warn('设置重置失败', e); alert('设置重置失败，请查看控制台') }
}

async function loadSettings() {
  loadingSettings.value = true
  try { applySettings(await apiGet('/api/v1/settings')) }
  catch (e) { console.warn('设置加载失败，使用默认值', e) }
  finally { loadingSettings.value = false }
}

async function loadSessionCount() {
  try { const data = await apiGet('/api/v1/sessions'); sessionCount.value = Array.isArray(data.sessions) ? data.sessions.length : 0 }
  catch { sessionCount.value = 0 }
}

/* ---------------- 执行授权（数据与安全 tab） ---------------- */
interface GrantRecord {
  session_id: string
  tool: string
  run_id?: string | null
  granted_at?: string | null
}

const grants = ref<GrantRecord[]>([])
const grantsLoading = ref(false)
const grantsError = ref('')
const grantsActionError = ref('')
const grantsNotice = ref('')
const revokingGrantKey = ref('')

function grantKey(g: GrantRecord) {
  return `${g.session_id}::${g.tool}`
}
function grantToMs(value?: string | null) {
  if (!value) return null
  const t = new Date(value).getTime()
  return Number.isNaN(t) ? null : t
}
function grantPad2(n: number) {
  return String(n).padStart(2, '0')
}
function grantFmtAbs(value?: string | null) {
  const ms = grantToMs(value)
  if (ms === null) return '—'
  const d = new Date(ms)
  return `${d.getFullYear()}-${grantPad2(d.getMonth() + 1)}-${grantPad2(d.getDate())} ${grantPad2(d.getHours())}:${grantPad2(d.getMinutes())}:${grantPad2(d.getSeconds())}`
}
function grantFmtRel(value?: string | null) {
  const ms = grantToMs(value)
  if (ms === null) return '—'
  const diff = Math.max(0, Date.now() - ms)
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day} 天前`
  return grantFmtAbs(value)
}
function shortGrantId(value?: string | null, max = 12) {
  if (!value) return '—'
  return value.length > max ? `${value.slice(0, max)}…` : value
}
async function loadGrants() {
  grantsLoading.value = true
  grantsError.value = ''
  grantsActionError.value = ''
  try {
    const r = await fetch(`${API}/api/v1/approvals/grants`)
    if (!r.ok) throw new Error(await responseError(r, `GET 执行授权 ${r.status}`))
    const data = await r.json()
    grants.value = Array.isArray(data?.grants) ? data.grants : []
  } catch (e: any) {
    grants.value = []
    grantsError.value = `加载执行授权失败：${e?.message || e}`
  } finally {
    grantsLoading.value = false
  }
}
async function revokeGrant(g: GrantRecord) {
  const key = grantKey(g)
  if (revokingGrantKey.value === key) return
  revokingGrantKey.value = key
  grantsError.value = ''
  grantsActionError.value = ''
  grantsNotice.value = ''
  try {
    const r = await fetch(
      `${API}/api/v1/approvals/grants/${encodeURIComponent(g.session_id)}/${encodeURIComponent(g.tool)}`,
      { method: 'DELETE' },
    )
    if (!r.ok) throw new Error(await responseError(r, `撤销授权 ${r.status}`))
    grants.value = grants.value.filter((item) => grantKey(item) !== key)
    grantsNotice.value = `已撤销「${g.tool}」的会话授权`
  } catch (e: any) {
    grantsActionError.value = `撤销授权失败：${e?.message || e}`
  } finally {
    revokingGrantKey.value = ''
  }
}

let saveTimer: ReturnType<typeof setTimeout> | null = null
function autoSave() {
  if (loadingSettings.value) return
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    try {
      await apiPut('/api/v1/settings', {
        params: { ...params }, streaming: streaming.value,
        providers: providers.value.map(p => ({ ...p, models: normalizeModels(p.models) })),
        prompts: prompts.value, agentTools: agentTools.value, agentParams: { ...agentParams },
        theme: theme.value, codeFont: codeFont.value, ligatures: ligatures.value,
        glass: glass.value, devMode: devMode.value, displayLimit: displayLimit.value,
        thinking: thinking.value, autoTools: autoTools.value,
      })
      window.dispatchEvent(new CustomEvent('settings:providers-updated'))
    } catch (e) { console.warn('设置保存失败', e) }
  }, 500)
}

watch(params, autoSave, { deep: true })
watch(streaming, autoSave)
watch(providers, autoSave, { deep: true })
watch(prompts, autoSave, { deep: true })
watch(agentTools, autoSave, { deep: true })
watch(agentParams, autoSave, { deep: true })
watch(theme, (val) => {
  autoSave()
  window.dispatchEvent(new CustomEvent('settings:theme-updated', { detail: val }))
})
watch(codeFont, autoSave)
watch(ligatures, autoSave)
watch(glass, autoSave)
watch(devMode, autoSave)
watch(thinking, autoSave)
watch(autoTools, autoSave)
watch(displayLimit, autoSave)
watch(activeTab, (tab) => {
  if (tab === 'data') loadGrants()
  if (tab === 'account') { loadAccountInfo(); loadExecutor() }
  if (tab === 'mailsec') { loadMailConfig(); loadSecurityConfig() }
})

function loadTtsVoices() {
  if (!ttsSupported) return
  const voices = window.speechSynthesis.getVoices()
  ttsVoiceOptions.value = [
    { label: '系统默认', value: '' },
    ...voices.map(v => ({ label: `${v.name} · ${v.lang}`, value: v.voiceURI || v.name })),
  ]
  try {
    ttsVoice.value = localStorage.getItem('aios-tts-voice') || ''
    ttsSource.value = localStorage.getItem('aios-tts-source') || 'system'
    ttsApiType.value = localStorage.getItem('aios-tts-api-type') || 'openai'
    ttsEndpoint.value = localStorage.getItem('aios-tts-endpoint') || ''
    ttsKey.value = localStorage.getItem('aios-tts-key') || ''
    ttsModel.value = localStorage.getItem('aios-tts-model') || ''
    ttsVoiceId.value = localStorage.getItem('aios-tts-voice-id') || ''
    ttsRefUrl.value = localStorage.getItem('aios-tts-ref') || ''
    ttsRefName.value = localStorage.getItem('aios-tts-ref-name') || ''
    ttsInstruction.value = localStorage.getItem('aios-tts-instruction') || ''
    ttsUseRef.value = localStorage.getItem('aios-tts-use-ref') === '1'
    ttsRate.value = Number(localStorage.getItem('aios-tts-rate') || '1') || 1
    ttsPitch.value = Number(localStorage.getItem('aios-tts-pitch') || '1') || 1
    if (ttsApiType.value === 'mimo' && ttsSource.value === 'thirdparty') {
      if (!MIMO_MODELS.includes(ttsModel.value)) ttsModel.value = 'mimo-v2.5-tts'
      if (!ttsVoiceId.value) ttsVoiceId.value = 'mimo_default'
    }
    if (ttsSource.value === 'thirdparty' && ttsApiType.value === 'openai' && ttsEndpoint.value && ttsModel.value) {
      setTimeout(() => { void loadTtsApiVoices() }, 300)
    }
  } catch { /* ignore */ }
  if (!ttsVoice.value) {
    const zh = voices.find(v => v.lang && (v.lang.toLowerCase().startsWith('zh') || v.lang.toLowerCase().includes('cn')))
    if (zh) ttsVoice.value = zh.voiceURI || zh.name
  }
}

function onSelectTtsApiType(item: any) {
  ttsApiType.value = item.value
  try { localStorage.setItem('aios-tts-api-type', item.value) } catch { /* ignore */ }
  if (item.value === 'openai') maybeLoadTtsVoices()
  if (item.value === 'mimo') {
    if (!MIMO_MODELS.includes(ttsModel.value)) ttsModel.value = 'mimo-v2.5-tts'
    if (!ttsVoiceId.value) ttsVoiceId.value = 'mimo_default'
  }
}

function onSelectTtsApiVoice(item: any) {
  ttsVoiceId.value = item.value
  try { localStorage.setItem('aios-tts-voice-id', item.value) } catch { /* ignore */ }
}

let ttsVoiceTimer: ReturnType<typeof setTimeout> | null = null
function maybeLoadTtsVoices() {
  if (ttsSource.value !== 'thirdparty' || ttsApiType.value !== 'openai') return
  if (!ttsEndpoint.value.trim() || !ttsModel.value.trim()) return
  if (ttsVoiceTimer) clearTimeout(ttsVoiceTimer)
  ttsVoiceTimer = setTimeout(() => { void loadTtsApiVoices() }, 700)
}

async function loadTtsApiVoices() {
  if (!ttsEndpoint.value.trim() || !ttsModel.value.trim()) {
    ttsMsg.value = '先填 Base URL 和模型，再加载语音包'
    return
  }
  ttsApiLoading.value = true; ttsMsg.value = ''
  try {
    const qs = new URLSearchParams({ endpoint: ttsEndpoint.value, api_key: ttsKey.value, model: ttsModel.value })
    const r = await fetch(`${API}/api/v1/tts/voices?${qs.toString()}`)
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
    const list = Array.isArray(d.voices) ? d.voices : []
    ttsApiVoiceOptions.value = list.map((v: any) => ({ label: `${v.name || v.id} · ${v.id}`, value: String(v.id) }))
    ttsMsg.value = d.source === 'remote'
      ? `已从接口加载 ${list.length} 个语音包`
      : '该接口没有返回语音列表：语音包 ID 可以留空，或手动填写接口要求的值'
  } catch (err: any) {
    ttsMsg.value = `加载语音包失败：${err?.message || err}`
  } finally {
    ttsApiLoading.value = false
  }
}

function onSelectTtsVoice(item: any) {
  ttsVoice.value = item.value
  try { localStorage.setItem('aios-tts-voice', item.value) } catch { /* ignore */ }
}

function onSelectTtsSource(item: any) {
  ttsSource.value = item.value
  try { localStorage.setItem('aios-tts-source', item.value) } catch { /* ignore */ }
  if (item.value === 'thirdparty' && ttsApiType.value === 'openai') maybeLoadTtsVoices()
}

async function uploadTtsRef(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  ttsBusy.value = true; ttsMsg.value = ''
  try {
    const form = new FormData(); form.append('file', file)
    const r = await fetch(`${API}/api/v1/tts/voice`, { method: 'POST', body: form })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
    ttsRefUrl.value = d.url || ''
    ttsRefName.value = d.name || file.name
    try { localStorage.setItem('aios-tts-ref', ttsRefUrl.value); localStorage.setItem('aios-tts-ref-name', ttsRefName.value) } catch { /* ignore */ }
    ttsMsg.value = '参考音频已上传'
  } catch (err: any) { ttsMsg.value = `上传失败：${err?.message || err}` }
  finally { ttsBusy.value = false }
}

async function testTts() {
  if (ttsSource.value === 'thirdparty') {
    if (!ttsEndpoint.value.trim()) { ttsMsg.value = '请先填写 TTS 地址'; return }
    if (ttsApiType.value === 'openai' || ttsApiType.value === 'mimo') {
      if (!ttsKey.value.trim()) { ttsMsg.value = '请先填写 API Key'; return }
      if (!ttsModel.value.trim()) { ttsMsg.value = '请先填写模型'; return }
      if (ttsApiType.value === 'mimo') {
        if (ttsModel.value === 'mimo-v2.5-tts-voicedesign' && !ttsInstruction.value.trim()) { ttsMsg.value = 'voicedesign 需要填写音色描述'; return }
        if (ttsModel.value === 'mimo-v2.5-tts-voiceclone' && (!ttsUseRef.value || !ttsRefUrl.value)) { ttsMsg.value = 'voiceclone 需要打开参考音频并上传文件'; return }
      }
    } else if (!ttsEndpoint.value.includes('{text}')) {
      ttsMsg.value = '自定义 URL 必须包含 {text}'; return
    }
    ttsBusy.value = true; ttsMsg.value = ''
    try {
      const r = await fetch(`${API}/api/v1/tts/synthesize`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: '你好，这是第三方语音试听。', endpoint: ttsEndpoint.value, api_key: ttsKey.value,
          model: ttsModel.value, voice: ttsVoiceId.value, format: 'mp3', reference_audio: ttsUseRef.value ? ttsRefUrl.value : '',
          api_type: ttsApiType.value, instruction: ttsInstruction.value,
        }),
      })
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || `HTTP ${r.status}`) }
      const blob = await r.blob()
      const audio = new Audio(URL.createObjectURL(blob))
      audio.play().catch(() => {})
      ttsMsg.value = '已播放试听'
    } catch (err: any) { ttsMsg.value = `试听失败：${err?.message || err}` }
    finally { ttsBusy.value = false }
    return
  }
  if (!ttsSupported) return
  window.speechSynthesis.cancel()
  const utter = new SpeechSynthesisUtterance('你好，这是语音朗读试听。')
  utter.lang = 'zh-CN'
  utter.rate = ttsRate.value
  utter.pitch = ttsPitch.value
  const voices = window.speechSynthesis.getVoices()
  const v = voices.find(x => (x.voiceURI || x.name) === ttsVoice.value)
  if (v) { utter.voice = v; utter.lang = v.lang || 'zh-CN' }
  window.speechSynthesis.speak(utter)
}

watch([ttsRate, ttsPitch, ttsSource, ttsApiType, ttsEndpoint, ttsKey, ttsModel, ttsVoiceId, ttsUseRef, ttsInstruction], () => {
  try {
    localStorage.setItem('aios-tts-rate', String(ttsRate.value))
    localStorage.setItem('aios-tts-pitch', String(ttsPitch.value))
    localStorage.setItem('aios-tts-source', ttsSource.value)
    localStorage.setItem('aios-tts-api-type', ttsApiType.value)
    localStorage.setItem('aios-tts-endpoint', ttsEndpoint.value)
    localStorage.setItem('aios-tts-key', ttsKey.value)
    localStorage.setItem('aios-tts-model', ttsModel.value)
    localStorage.setItem('aios-tts-voice-id', ttsVoiceId.value)
    localStorage.setItem('aios-tts-use-ref', ttsUseRef.value ? '1' : '0')
    localStorage.setItem('aios-tts-instruction', ttsInstruction.value)
  } catch { /* ignore */ }
})

function onSelectMailProvider(item: any) {
  mailProvider.value = item.value
  const preset: Record<string, any> = {
    qq: { host: 'smtp.qq.com', port: 465, ssl: true },
    gmail: { host: 'smtp.gmail.com', port: 587, ssl: false },
    '163': { host: 'smtp.163.com', port: 465, ssl: true },
    outlook: { host: 'smtp.office365.com', port: 587, ssl: false },
  }
  const p = preset[item.value]
  if (p) { mailHost.value = p.host; mailPort.value = p.port; mailSsl.value = p.ssl }
}

async function loadMailConfig() {
  try {
    const d = await apiGet('/api/v1/auth/mail/config')
    mailConfigured.value = !!d.configured
    mailHost.value = d.host || ''
    mailPort.value = d.port || 465
    mailUser.value = d.username || ''
    mailFrom.value = d.from || ''
    mailSsl.value = d.ssl !== false
    const byHost = { 'smtp.qq.com': 'qq', 'smtp.gmail.com': 'gmail', 'smtp.163.com': '163', 'smtp.office365.com': 'outlook' }
    mailProvider.value = (byHost as any)[d.host] || 'custom'
    mailAllow.value = !!d.registration?.allow
    mailAllowedText.value = (d.registration?.allowedEmails || []).join('\n')
    if (!testTo.value) testTo.value = d.username || ''
  } catch (e: any) { mailMsg.value = `读取邮件配置失败：${e?.message || e}` }
}

async function saveMailConfig() {
  mailBusy.value = true; mailMsg.value = ''
  try {
    const allowedEmails = mailAllowedText.value.split('\n').map(x => x.trim()).filter(Boolean)
    const r = await fetch(`${API}/api/v1/auth/mail/config`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        host: mailHost.value, port: Number(mailPort.value) || 465,
        username: mailUser.value, from: mailFrom.value || mailUser.value,
        password: mailPass.value || undefined, ssl: mailSsl.value,
        registration: { allow: mailAllow.value, allowedEmails },
      }),
    })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
    mailConfigured.value = !!d.configured
    mailMsg.value = d.configured ? '邮件配置已保存并可用' : '已保存，但 SMTP 还不完整'
    mailPass.value = ''
  } catch (e: any) { mailMsg.value = `保存失败：${e?.message || e}` }
  finally { mailBusy.value = false }
}

async function testMail() {
  mailBusy.value = true; mailMsg.value = ''
  try {
    const r = await fetch(`${API}/api/v1/auth/mail/test`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to: testTo.value }),
    })
    const d = await r.json().catch(() => ({}))
    mailMsg.value = d.ok ? '测试邮件已发送，请查收（含垃圾箱）' : `发送失败：${d.error || d.detail || '未知错误'}`
  } catch (e: any) { mailMsg.value = `发送失败：${e?.message || e}` }
  finally { mailBusy.value = false }
}

async function loadSecurityConfig() {
  try {
    const d = await apiGet('/api/v1/auth/security')
    securityLockout.value = d.loginLockout !== false
    securityRateLimit.value = d.rateLimit !== false
  } catch (e: any) { securityMsg.value = `读取安全开关失败：${e?.message || e}` }
}

async function saveSecurityConfig() {
  securityBusy.value = true; securityMsg.value = ''
  try {
    const r = await fetch(`${API}/api/v1/auth/security`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ loginLockout: securityLockout.value, rateLimit: securityRateLimit.value }),
    })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
    securityMsg.value = '安全开关已保存'
  } catch (e: any) { securityMsg.value = `保存失败：${e?.message || e}` }
  finally { securityBusy.value = false }
}

async function loadAccountInfo() {
  try {
    const me = await apiGet('/api/v1/auth/me')
    accountEmail.value = me.email || ''
    isOwner.value = me.role === 'owner' || !!me.local
  } catch { /* 本机/未登录时忽略 */ }
}

async function loadExecutor() {
  try {
    const data = await apiGet('/api/v1/executor/config')
    const cfg = data.config || {}
    executorMode.value = cfg.mode || 'disabled'
    executorHost.value = cfg.ssh?.host || ''
    executorPort.value = cfg.ssh?.port || 22
    executorUser.value = cfg.ssh?.user || 'aios'
    executorImage.value = cfg.ssh?.image || 'aios-runner:latest'
    storageMode.value = cfg.storage?.mode || 'local'
    previousStorageMode.value = storageMode.value
    isOwner.value = data.role === 'owner'
    if (executorMode.value === 'device') await loadPairedDevices()
  } catch (e: any) { executorMsg.value = `读取执行器配置失败：${e?.message || e}` }
}

async function saveExecutor() {
  executorBusy.value = true; executorMsg.value = ''
  try {
    const r = await fetch(`${API}/api/v1/executor/config`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: executorMode.value,
        ssh: { host: executorHost.value, port: Number(executorPort.value) || 22, user: executorUser.value,
               image: executorImage.value, host_key: executorHostKey.value },
        storage: { mode: storageMode.value, path: '~/aios-data' },
      }),
    })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
    const wasRemote = previousStorageMode.value === 'remote'
    previousStorageMode.value = storageMode.value
    executorMsg.value = '已保存'
    if (!isOwner.value && storageMode.value === 'remote' && !wasRemote) showStorageMigration.value = true
  } catch (e: any) { executorMsg.value = `保存失败：${e?.message || e}` }
  finally { executorBusy.value = false }
}

function onSelectStorageMode(item: any) {
  const old = storageMode.value
  storageMode.value = item.value
  if (item.value === 'remote' && old !== 'remote') showStorageMigration.value = true
}

async function migrateStorage() {
  storageBusy.value = true; storageMsg.value = ''
  try {
    const r = await fetch(`${API}/api/v1/executor/storage/migrate`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'migrate' }),
    })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
    storageMsg.value = '远程存储已启用；本机原数据保留作为备份。'
    storageMode.value = d.mode || 'remote'
    previousStorageMode.value = storageMode.value
    showStorageMigration.value = false
  } catch (e: any) {
    storageMsg.value = `未切换存储，本地数据未改动：${e?.message || e}`
    storageMode.value = 'local'
    previousStorageMode.value = 'local'
  } finally { storageBusy.value = false }
}

async function keepLocalStorage() {
  storageBusy.value = true
  try {
    const r = await fetch(`${API}/api/v1/executor/storage/migrate`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'keep_local' }),
    })
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || `HTTP ${r.status}`) }
    storageMode.value = 'local'; previousStorageMode.value = 'local'; showStorageMigration.value = false
    storageMsg.value = '继续使用 AIOS 账号空间，本机数据没有迁移。'
  } catch (e: any) { storageMsg.value = e?.message || String(e) }
  finally { storageBusy.value = false }
}

async function loadPairedDevices() {
  try { const d = await apiGet('/api/v1/devices'); pairedDevices.value = d.devices || [] }
  catch (e: any) { pairingError.value = e?.message || String(e) }
}

async function createDevicePairing() {
  deviceBusy.value = true; pairingError.value = ''; pairingCode.value = ''
  try {
    const r = await fetch(`${API}/api/v1/devices/pairing-code`, { method: 'POST' })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
    pairingCode.value = d.pairing_code
    await loadPairedDevices()
  } catch (e: any) { pairingError.value = `生成失败：${e?.message || e}` }
  finally { deviceBusy.value = false }
}

async function revokeDevice(id: string) {
  deviceBusy.value = true; pairingError.value = ''
  try {
    const r = await fetch(`${API}/api/v1/devices/${encodeURIComponent(id)}`, { method: 'DELETE' })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
    await loadPairedDevices()
  } catch (e: any) { pairingError.value = `撤销失败：${e?.message || e}` }
  finally { deviceBusy.value = false }
}

async function testExecutor() {
  executorBusy.value = true; executorMsg.value = '正在测试连接…'
  try {
    const r = await fetch(`${API}/api/v1/executor/test`, { method: 'POST' })
    const d = await r.json().catch(() => ({}))
    executorMsg.value = d.ok ? `连接成功：${(d.stdout || '').slice(0, 200)}` : `连接失败：${d.error || d.stderr || '未知错误'}`
  } catch (e: any) { executorMsg.value = `测试失败：${e?.message || e}` }
  finally { executorBusy.value = false }
}

async function loadSshKey() {
  executorBusy.value = true
  try {
    const d = await apiGet('/api/v1/executor/ssh-key')
    executorPublicKey.value = d.public_key || ''
    executorMsg.value = '公钥已生成，添加到服务器 ~/.ssh/authorized_keys'
  } catch (e: any) { executorMsg.value = `获取公钥失败：${e?.message || e}` }
  finally { executorBusy.value = false }
}

async function changePassword() {
  accountBusy.value = true; accountMsg.value = ''
  try {
    const r = await fetch(`${API}/api/v1/auth/change-password`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_password: oldPassword.value, new_password: newPassword.value }),
    })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
    accountMsg.value = '密码已修改'; oldPassword.value = ''; newPassword.value = ''
  } catch (e: any) { accountMsg.value = `修改密码失败：${e?.message || e}` }
  finally { accountBusy.value = false }
}

async function changeEmail() {
  accountBusy.value = true; accountMsg.value = ''
  try {
    const r = await fetch(`${API}/api/v1/auth/change-email`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: emailPassword.value, new_email: newEmail.value }),
    })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
    accountEmail.value = newEmail.value; accountMsg.value = '邮箱已修改'; emailPassword.value = ''; newEmail.value = ''
  } catch (e: any) { accountMsg.value = `修改邮箱失败：${e?.message || e}` }
  finally { accountBusy.value = false }
}

async function logoutNow() {
  try { await fetch(`${API}/api/v1/auth/logout`, { method: 'POST' }) } catch { /* ignore */ }
  location.href = '/login'
}

function onResize() { isMobile.value = window.innerWidth < 768 }

onMounted(() => {
  window.addEventListener('resize', onResize)
  loadSettings(); loadSessionCount(); loadAccountInfo(); loadExecutor()
  if (isAdmin.value) { loadMailConfig(); loadSecurityConfig() }
  if (ttsSupported) {
    loadTtsVoices()
    window.speechSynthesis.addEventListener('voiceschanged', loadTtsVoices)
  }
})
onMounted(() => { loadGrants() })
onUnmounted(() => { window.removeEventListener('resize', onResize); if (saveTimer) clearTimeout(saveTimer) })
</script>

<style scoped>
/* ============================================================
   设置页 — 控制台布局
   ============================================================ */
.set-hero { margin-bottom: 20px; }

.set-nav {
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  width: min(100%, 720px);
  max-width: 100%;
  overflow-x: auto;
  scrollbar-width: thin;
  margin-bottom: 20px;
}
.set-nav-icon { font-size: 13px; line-height: 1; }
.set-nav-label { font-size: 12.5px; font-weight: 560; }
.set-nav .ui-seg-item {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 33px;
  padding: 0 14px;
}

.settings-page .ui-page-inner { max-width: 1000px; }

.set-panes { display: block; }
.set-pane { max-width: 860px; display: flex; flex-direction: column; }

/* ---------- 分区内的控制台面板（比卡片更收敛，避免分区套卡片） ---------- */
.set-well {
  padding: 14px 16px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background: color-mix(in srgb, var(--bg) 42%, transparent);
}
.set-well--flush { padding: 0; overflow: hidden; }
.set-well > .ui-field:last-child { margin-bottom: 0; }

/* ---------- 列表行 ---------- */
.set-list { display: flex; flex-direction: column; }
.set-list-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-light);
  transition: background var(--t-fast);
}
.set-list-item:last-child { border-bottom: none; }
.set-list-item:hover { background: var(--surface-alt); }
.set-list-item.default { background: var(--primary-soft); }
.set-list-item > .ui-btn { flex-shrink: 0; align-self: center; }
.set-list-icon { font-size: 15px; line-height: 26px; flex-shrink: 0; }
.set-list-item-main { flex: 1; min-width: 0; }
.set-list-item-name {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 13px;
  font-weight: 620;
  color: var(--text);
}
.set-list-item-meta {
  margin-top: 2px;
  font-size: 11px;
  color: var(--text2);
  font-family: var(--font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.set-list-item-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.set-model-tag {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: var(--r-full);
  background: var(--primary-soft);
  color: var(--primary);
  white-space: nowrap;
}
.set-model-tag.more { background: var(--surface-3); color: var(--text3); }

.set-empty {
  padding: 24px 16px;
  text-align: center;
  font-size: 12px;
  color: var(--text3);
  line-height: 1.6;
}

/* ---------- 开关行 ---------- */
.set-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 10px 0;
}
.set-row + .set-row { border-top: 1px solid var(--border-light); }
.set-well > .set-row:first-child { padding-top: 0; }
.set-well > .set-row:last-child { padding-bottom: 0; }
.set-row-main { min-width: 0; }
.set-row-title { font-size: 13px; font-weight: 560; color: var(--text); }
.set-row-desc { margin-top: 2px; font-size: 11px; color: var(--text3); line-height: 1.5; }

/* ---------- 滑杆行 ---------- */
.set-slider-row { padding: 10px 0; }
.set-slider-row + .set-slider-row { border-top: 1px solid var(--border-light); }
.set-well > .set-slider-row:last-child { padding-bottom: 0; }
.set-slider-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}
.set-slider-head .ui-label { margin-bottom: 0; }
.set-slider-val {
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 18px;
  padding: 0 8px;
  border-radius: var(--r-full);
  background: var(--primary-soft);
  color: var(--primary);
  font-variant-numeric: tabular-nums;
}
.set-slider-row input[type="range"] {
  width: 100%;
  height: 20px;
  accent-color: var(--primary);
}
.set-slider-hint {
  display: block;
  margin-top: 6px;
  font-size: 11px;
  color: var(--text3);
  line-height: 1.5;
}

/* ---------- 表单 ---------- */
.set-inline-row { display: flex; align-items: center; gap: 8px; }
.set-inline-row .ui-input { flex: 1 1 auto; width: auto; min-width: 0; }
.set-dropdown-wrp { flex: 1; min-width: 0; }
.set-input-wrp { width: 140px; flex-shrink: 0; }
.set-refresh-btn { flex-shrink: 0; height: 38px; color: var(--text2); }

.set-hint { margin-top: 6px; font-size: 11px; line-height: 1.5; color: var(--text3); }
.set-hint.ok { color: var(--success); }

/* ---------- 工具链 ---------- */
.set-tool-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-light);
  transition: background var(--t-fast);
}
.set-tool-item:last-child { border-bottom: none; }
.set-tool-item:hover { background: var(--surface-alt); }
.set-tool-item-main { flex: 1; min-width: 0; }
.set-tool-item-desc {
  margin-top: 4px;
  padding-left: 23px;
  font-size: 11px;
  color: var(--text3);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.set-tool-item > .ui-btn { flex-shrink: 0; align-self: center; }
.set-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 560;
  cursor: pointer;
}
.set-checkbox input { width: 15px; height: 15px; accent-color: var(--primary); }

/* ---------- 单选 ---------- */
.set-radio-row + .set-radio-row { border-top: 1px solid var(--border-light); }
.set-radio-row label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 0;
  font-size: 13px;
  cursor: pointer;
  color: var(--text);
}
.set-radio-row input { width: 15px; height: 15px; accent-color: var(--primary); }

/* ---------- 存储统计 ---------- */
.set-stat-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 0;
  font-size: 12.5px;
  color: var(--text2);
  border-bottom: 1px solid var(--border-light);
}
.set-stat-row:last-child { border-bottom: none; }
.set-stat-row > span:last-child {
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 12px;
}

/* ---------- 危险操作 ---------- */
.set-danger-well { border-color: color-mix(in srgb, var(--error) 38%, var(--border-light)); }
.set-danger-text { margin-bottom: 12px; font-size: 12px; color: var(--text2); line-height: 1.6; }

/* ---------- 执行授权 ---------- */
.grant-tool {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 640;
  color: var(--text);
  background: var(--surface-alt);
  padding: 1px 7px;
  border-radius: var(--r-xs);
}
.grant-time {
  flex-shrink: 0;
  align-self: center;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text3);
  white-space: nowrap;
}
.grant-skel { display: flex; flex-direction: column; gap: 8px; padding: 12px 14px; }
.grant-skel-row { height: 32px; border-radius: var(--r-sm); }
.grant-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  padding: 12px 14px;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--error);
}
.grant-error span { flex: 1; min-width: 0; word-break: break-word; }
.grant-error .ui-btn { flex-shrink: 0; }
.grant-empty { padding: 34px 14px; }
.grant-action-error {
  margin-top: 8px;
  padding: 8px 12px;
  border: 1px solid color-mix(in srgb, var(--error) 30%, transparent);
  border-radius: var(--r-sm);
  background: color-mix(in srgb, var(--error) 8%, transparent);
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--error);
  word-break: break-word;
}
.grant-notice { color: var(--success); }

/* ---------- 关于 ---------- */
.about-info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.about-info-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 10px 12px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  background: var(--surface-2);
}
.about-info-label { font-size: 10.5px; letter-spacing: 0.06em; color: var(--text3); }
.about-info-value { font-size: 12.5px; font-weight: 600; color: var(--text); }
.about-link { color: var(--primary); }
.about-link:hover { text-decoration: underline; }
.about-desc { margin-top: 14px; font-size: 12px; color: var(--text2); line-height: 1.7; }
.about-motto {
  margin-top: 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text3);
  letter-spacing: 0.02em;
}

.about-tech-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 8px; }
.about-tech-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 11px;
  border-radius: var(--r-sm);
  background: var(--surface-alt);
}
.about-tech-key { font-size: 11px; color: var(--text3); }
.about-tech-val { font-size: 12px; font-weight: 560; color: var(--text); }

.about-thanks-list { display: flex; flex-wrap: wrap; gap: 6px; }
.about-thanks-tag {
  padding: 4px 11px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-full);
  background: var(--surface-alt);
  font-size: 11.5px;
  color: var(--text2);
}

.about-api-group + .about-api-group { margin-top: 16px; }
.about-api-group-title {
  font-size: 10.5px;
  font-weight: 750;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text3);
  margin-bottom: 6px;
}
.about-api-item {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 5px 0;
  border-bottom: 1px solid var(--border-light);
}
.about-api-item:last-child { border-bottom: none; }
.about-api-path {
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 2px 7px;
  border-radius: var(--r-xs);
  background: var(--surface-alt);
  color: var(--primary);
  white-space: nowrap;
}
.about-api-desc { font-size: 11.5px; color: var(--text3); }
.about-api-badge {
  font-family: var(--font-mono);
  font-size: 10px;
  padding: 1px 7px;
  border-radius: var(--r-xs);
  background: var(--surface-alt);
  color: var(--text3);
}

/* ---------- 相关页面（跨页入口） ---------- */
.set-jump-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}
.set-jump {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 13px 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background: var(--surface-alt);
  color: var(--text);
  text-decoration: none;
  transition: border-color var(--t-fast), background var(--t-fast), transform var(--t-fast);
}
.set-jump:hover {
  border-color: color-mix(in srgb, var(--primary) 42%, var(--border-light));
  background: var(--primary-soft);
  transform: translateY(-1px);
}
.set-jump-icon { flex-shrink: 0; font-size: 16px; line-height: 1; }
.set-jump-main { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.set-jump-name { font-size: 12.5px; font-weight: 620; color: var(--text); }
.set-jump-path { font-family: var(--font-mono); font-size: 10.5px; color: var(--text3); }
.set-jump-arrow { margin-left: auto; color: var(--text3); font-size: 13px; transition: color var(--t-fast); }
.set-jump:hover .set-jump-arrow { color: var(--primary); }

/* ---------- 弹层 ---------- */
.set-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: var(--overlay);
  -webkit-backdrop-filter: blur(6px);
  backdrop-filter: blur(6px);
  animation: set-fade 160ms var(--ease);
}
@keyframes set-fade { from { opacity: 0; } to { opacity: 1; } }

.set-modal {
  width: 100%;
  max-width: 460px;
  max-height: 84vh;
  overflow-y: auto;
  padding: 20px;
  border: 1px solid var(--border-strong);
  border-radius: var(--r-lg);
  background: var(--surface);
  box-shadow: var(--shadow-lg);
  animation: set-modal-in 200ms var(--ease);
}
@keyframes set-modal-in {
  from { opacity: 0; transform: translateY(8px) scale(0.99); }
  to { opacity: 1; transform: none; }
}
.set-modal--wide { max-width: 580px; }
.set-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 16px;
}
.set-modal-title { font-size: 16px; font-weight: 680; letter-spacing: -0.01em; }
.set-modal-text { font-size: 12.5px; color: var(--text2); line-height: 1.7; }
.set-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
}
.set-modal .ui-field:last-of-type { margin-bottom: 0; }

.set-prompt-content,
.set-code {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.7;
  background: var(--bg);
}
.set-prompt-content { min-height: 180px; }

/* ---------- navigation responsive behavior ---------- */
.set-nav {
  width: min(100%, 720px);
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  overflow-x: auto;
  scrollbar-width: thin;
  margin-bottom: 20px;
}
.set-nav .ui-seg-item {
  flex: 0 0 auto;
  min-width: 132px;
  justify-content: center;
}
.set-shell.mobile .set-nav { width: 100%; }
.set-shell.mobile .set-pane { max-width: none; }
.set-pane { max-width: 860px; }

@media (max-width: 767px) {
  .set-hero { margin-bottom: 16px; }
  .set-nav { width: 100%; margin-bottom: 18px; padding-bottom: 2px; }
  .set-nav .ui-seg-item { min-width: 118px; height: 38px; }
  .set-pane { max-width: none; }
  .set-well { padding: 12px 14px; }
  .set-well--flush { padding: 0; }
  .set-list-item { flex-wrap: wrap; align-items: center; }
  .set-list-item-main { flex: 1 1 100%; }
  .set-list-item > .ui-btn { min-height: 32px; }
  .set-tool-item { flex-wrap: wrap; align-items: center; }
  .set-tool-item-main { flex: 1 1 100%; }
  .set-tool-item > .ui-btn { margin-left: auto; }
  .set-inline-row { flex-direction: column; align-items: stretch; }
  .set-input-wrp { width: 100%; }
  .set-refresh-btn { width: 100%; height: 34px; }
  .about-info-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .about-tech-grid { grid-template-columns: minmax(0, 1fr); }
  .set-jump-grid { grid-template-columns: minmax(0, 1fr); }
  .about-api-item { gap: 4px 8px; }
  .about-api-path { white-space: normal; }
  .set-modal-overlay { padding: 12px; }
  .set-modal { max-width: 100%; max-height: 88vh; padding: 16px; }
  .set-modal-actions { flex-wrap: wrap; }
  .set-modal-actions .ui-btn { flex: 1 1 auto; }
}

.acct-grid { display: flex; gap: 8px; margin: 8px 0; flex-wrap: wrap; }
.acct-input { flex: 1; min-width: 180px; height: 38px; padding: 0 12px; border-radius: 9px;
  border: 1px solid var(--border, #2a3247); background: rgba(0,0,0,.15); color: inherit; font-size: 13px; }
.acct-textarea { width: 100%; min-height: 70px; height: auto; padding: 10px 12px; flex: none; }
.acct-btn { height: 38px; padding: 0 16px; border-radius: 9px; border: 1px solid #5b7cfa55;
  background: rgba(91,124,250,.18); color: inherit; cursor: pointer; font-size: 13px; }
.acct-btn:disabled { opacity: .5; cursor: default; }
.acct-btn--ghost { background: transparent; border-color: #2a3247; }
.acct-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.acct-msg { margin: 8px 0 0; font-size: 12px; color: #8ea2ff; }
.acct-hint { font-size: 12px; color: #8b93a7; line-height: 1.7; }
.acct-field { margin: 10px 0; }
.acct-label-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.acct-label { font-size: 12px; color: var(--text2, #9aa3b8); }
.acct-help { width: 18px; height: 18px; border-radius: 50%; border: 1px solid #3a4560;
  background: transparent; color: #8b93a7; font-size: 11px; line-height: 1; cursor: pointer; padding: 0; }
.acct-help:hover { color: #c7d2fe; border-color: #5b7cfa; }
.acct-tip { margin-top: 6px; padding: 8px 10px; border-radius: 8px; background: rgba(91,124,250,.10);
  border: 1px solid rgba(91,124,250,.25); color: #9aa3b8; font-size: 12px; line-height: 1.7; }
.acct-cols { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.acct-dropdown { width: 100%; }
.acct-dropdown :deep(.ai-dropdown__trigger--label) { width: 100%; min-width: 0; }
.acct-tip--choice { margin: 10px 0; padding: 12px; }
.acct-doc { margin: 8px 0 14px; padding: 12px 14px; border-radius: 10px; background: rgba(0,0,0,.18);
  border: 1px solid #2a3247; font-size: 12.5px; color: #b9c1d4; line-height: 1.8; }
.acct-doc-title { font-weight: 600; color: #e7eaf3; margin-bottom: 6px; }
.acct-doc ol { margin: 0; padding-left: 20px; }
.acct-doc code { background: rgba(0,0,0,.3); padding: 1px 5px; border-radius: 4px; font-size: 11px; }
.acct-doc-note { margin-top: 8px; color: #8b93a7; font-size: 11.5px; }
.acct-doc-toggle { height: 32px; padding: 0 12px; border-radius: 8px; border: 1px solid #2a3247;
  background: transparent; color: #c7d2fe; font-size: 12px; cursor: pointer; }
@media (max-width: 767px) { .acct-cols { grid-template-columns: 1fr; } }
.acct-inline { flex: 1; min-width: 150px; height: 38px; }
.device-pair-code{padding:7px 12px;border:1px dashed var(--primary);border-radius:8px;font:600 18px ui-monospace,monospace;letter-spacing:2px;color:var(--primary)}
.device-list{margin-top:10px;border-top:1px solid var(--border-light)}
.device-row{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px 0;border-bottom:1px solid var(--border-light);font-size:12px;color:var(--text2)}

.tts-range { width: 100%; accent-color: var(--primary); }
.tts-req { color: #f87171; font-weight: 700; margin-left: 2px; }
.acct-help--text { width: auto; padding: 0 8px; border-radius: 6px; font-size: 11px; height: 22px; }
.tts-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; }
.tts-chip { padding: 3px 9px; border-radius: 999px; border: 1px solid var(--border-light); background: var(--surface); color: var(--text2); font-size: 11px; cursor: pointer; }
.tts-chip:hover { border-color: var(--primary); color: var(--text); }
.tts-advanced summary { cursor: pointer; color: var(--text2); font-size: 12px; margin-bottom: 8px; }
.exec-doc-modal { width: min(780px, 94vw) !important; max-height: 86vh; display: flex; flex-direction: column; }
.exec-doc-body { overflow-y: auto; padding: 6px 22px 24px; line-height: 1.8; font-size: 13.5px; color: var(--text); }
.exec-doc-body :deep(h1) { font-size: 21px; margin: 10px 0 14px; }
.exec-doc-body :deep(h2) { font-size: 17px; margin: 22px 0 10px; padding-bottom: 6px; border-bottom: 1px solid var(--border-light); }
.exec-doc-body :deep(h3) { font-size: 14.5px; margin: 16px 0 8px; }
.exec-doc-body :deep(p) { margin: 8px 0; color: var(--text2); }
.exec-doc-body :deep(ul), .exec-doc-body :deep(ol) { padding-left: 22px; margin: 8px 0; color: var(--text2); }
.exec-doc-body :deep(li) { margin: 4px 0; }
.exec-doc-body :deep(code) { background: rgba(0,0,0,.25); padding: 1px 6px; border-radius: 5px; font-size: 12px; }
.exec-doc-body :deep(pre) { background: rgba(0,0,0,.28); padding: 12px; border-radius: 8px; overflow-x: auto; }
.exec-doc-body :deep(pre code) { padding: 0; background: none; }
.exec-doc-body :deep(table) { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 12.5px; }
.exec-doc-body :deep(th), .exec-doc-body :deep(td) { border: 1px solid var(--border-light); padding: 7px 9px; text-align: left; }
.exec-doc-body :deep(th) { background: rgba(255,255,255,.04); }
.exec-doc-body :deep(img) { max-width: 100%; border-radius: 10px; margin: 8px 0; border: 1px solid var(--border-light); }
.exec-doc-body :deep(blockquote) { margin: 10px 0; padding: 8px 14px; border-left: 3px solid var(--primary); background: rgba(91,124,250,.08); color: var(--text2); }
.exec-doc-loading { padding: 30px; text-align: center; color: var(--text2); }
@media (max-width: 767px) { .exec-doc-modal { width: 96vw !important; max-height: 90vh; } .exec-doc-body { padding: 4px 14px 20px; } }
.acct-key { white-space: pre-wrap; word-break: break-all; font-size: 11px; padding: 10px;
  border-radius: 8px; background: rgba(0,0,0,.25); color: #9aa3b8; }

.about-list { margin: 0; padding-left: 18px; font-size: 12.5px; color: var(--text-dim, #8b93a7); line-height: 1.9; }
.about-list li { margin: 2px 0; }
</style>
