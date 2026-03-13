<script setup>
import { ref, nextTick, watch } from 'vue'
import { useAppStore } from '@/stores/app'
import { useApi } from '@/composables/useApi'

const store = useAppStore()
const { post, loading: apiLoading } = useApi()

const messagesContainer = ref(null)

/** Scroll chat to bottom after new messages */
function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(() => store.aiChatMessages.length, scrollToBottom)

/** Send message to AI */
async function sendMessage() {
  const text = store.aiChatInput.trim()
  if (!text || store.aiChatLoading) return

  // Add user message
  store.aiChatMessages.push({ role: 'user', text })
  store.aiChatInput = ''
  store.aiChatLoading = true
  scrollToBottom()

  try {
    const response = await post('/api/ai-chat', {
      message: text,
      history: store.aiChatMessages.slice(-10),
    })

    store.aiChatMessages.push({
      role: 'bot',
      text: response?.reply || response?.message || 'Не удалось получить ответ.',
    })
  } catch (err) {
    store.aiChatMessages.push({
      role: 'bot',
      text: `Ошибка: ${err.message}. Попробуйте позже.`,
    })
  } finally {
    store.aiChatLoading = false
    scrollToBottom()
  }
}

/** Handle Enter key (send on Enter, newline on Shift+Enter) */
function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

/** Close the chat panel */
function close() {
  store.showAiChat = false
}
</script>

<template>
  <Transition name="chat-slide">
    <div
      v-if="store.showAiChat"
      class="fixed bottom-4 right-4 z-[200] w-[400px] h-[560px] max-w-[calc(100vw-2rem)] max-h-[calc(100vh-6rem)] flex flex-col rounded-2xl overflow-hidden shadow-2xl shadow-carbon-900/10 border border-carbon-200/60"
      style="background: rgba(250, 249, 247, 0.96); backdrop-filter: blur(24px) saturate(1.2); -webkit-backdrop-filter: blur(24px) saturate(1.2);"
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-5 py-3.5 border-b border-carbon-200/60">
        <div class="flex items-center gap-2.5">
          <div class="w-7 h-7 rounded-lg bg-sage/15 flex items-center justify-center">
            <svg class="w-3.5 h-3.5 text-sage" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
            </svg>
          </div>
          <div>
            <h3 class="text-sm font-semibold text-carbon-800">AI Помощник</h3>
            <p class="text-[0.625rem] text-carbon-400">KMD Assistant</p>
          </div>
        </div>
        <button
          class="w-7 h-7 rounded-lg flex items-center justify-center text-carbon-400 hover:text-carbon-600 hover:bg-carbon-100 transition-colors"
          @click="close"
          aria-label="Close chat"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Messages -->
      <div
        ref="messagesContainer"
        class="flex-1 overflow-y-auto px-5 py-4 space-y-3"
      >
        <div
          v-for="(msg, idx) in store.aiChatMessages"
          :key="idx"
          class="flex"
          :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <div
            class="max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed"
            :class="msg.role === 'user'
              ? 'bg-sage text-white rounded-br-md'
              : 'bg-carbon-100 text-carbon-700 rounded-bl-md'"
          >
            <p class="whitespace-pre-wrap break-words">{{ msg.text }}</p>
          </div>
        </div>

        <!-- Typing indicator -->
        <div v-if="store.aiChatLoading" class="flex justify-start">
          <div class="bg-carbon-100 rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 bg-carbon-400 rounded-full animate-bounce" style="animation-delay: 0ms" />
            <span class="w-1.5 h-1.5 bg-carbon-400 rounded-full animate-bounce" style="animation-delay: 150ms" />
            <span class="w-1.5 h-1.5 bg-carbon-400 rounded-full animate-bounce" style="animation-delay: 300ms" />
          </div>
        </div>
      </div>

      <!-- Input area -->
      <div class="border-t border-carbon-200/60 px-4 py-3">
        <div class="flex items-end gap-2">
          <textarea
            v-model="store.aiChatInput"
            class="flex-1 resize-none rounded-xl border border-carbon-200 bg-white px-3.5 py-2.5 text-sm text-carbon-700 placeholder:text-carbon-400 focus:outline-none focus:border-sage/50 focus:ring-2 focus:ring-sage/10 transition-all"
            :rows="1"
            placeholder="Задайте вопрос..."
            @keydown="onKeydown"
            :disabled="store.aiChatLoading"
          />
          <button
            class="flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all duration-200"
            :class="store.aiChatInput.trim() && !store.aiChatLoading
              ? 'bg-sage text-white hover:bg-sage-dark'
              : 'bg-carbon-100 text-carbon-400 cursor-not-allowed'"
            :disabled="!store.aiChatInput.trim() || store.aiChatLoading"
            @click="sendMessage"
            aria-label="Send message"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.chat-slide-enter-active {
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}
.chat-slide-leave-active {
  transition: all 0.25s ease;
}
.chat-slide-enter-from {
  opacity: 0;
  transform: translateY(24px) scale(0.96);
}
.chat-slide-leave-to {
  opacity: 0;
  transform: translateY(16px) scale(0.98);
}

textarea {
  min-height: 2.5rem;
  max-height: 6rem;
  scrollbar-width: thin;
}
</style>
