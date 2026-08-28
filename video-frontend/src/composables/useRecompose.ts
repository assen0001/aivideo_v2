/** 重新合成视频 composable（V2.7）：复用现有分镜素材只重跑 compose，替换成片。
 *
 * 用法：
 *   const { recomposing, recomposedTs, trigger } = useRecompose(() => projectId)
 *   <button :disabled="recomposing" @click="trigger(refreshAfterRecompose)">
 *     {{ recomposing ? '合成中…' : '🔄 重新合成视频' }}
 *   </button>
 *
 * - recomposing：合成中 loading 态（按钮禁用 + 文案切换）
 * - recomposedTs：完成时的时间戳，用于给视频 URL 拼接 ?ts= 破除浏览器缓存（成片路径不变）
 * - trigger(onSuccess)：调接口 → 3s 轮询状态；完成回调 onSuccess；失败保留旧成片并 toast
 */
import { onBeforeUnmount, ref } from 'vue'
import * as projectApi from '@/api/projects'
import { useToastStore } from '@/stores/toast'

export function useRecompose(getProjectId: () => string) {
  const toast = useToastStore()
  const recomposing = ref(false)
  const recomposedTs = ref(0)
  let pollTimer: ReturnType<typeof setInterval> | null = null

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  /** 触发重新合成：调接口 → 3s 轮询状态 → 完成时 onSuccess() */
  async function trigger(onSuccess: () => void) {
    if (recomposing.value) return
    const projectId = getProjectId()
    if (!projectId) return

    recomposing.value = true
    try {
      await projectApi.recomposeProject(projectId)
      toast.show('success', '已开始重新合成，请稍候…')
    } catch {
      recomposing.value = false
      return // 错误已由 http 拦截器 toast
    }

    stopPolling()
    pollTimer = setInterval(async () => {
      try {
        const st = await projectApi.getProjectStatus(projectId)
        if (st.status === '完成') {
          stopPolling()
          recomposing.value = false
          recomposedTs.value = Date.now()
          toast.show('success', '重新合成完成')
          onSuccess()
        } else if (st.status === '失败') {
          stopPolling()
          recomposing.value = false
          toast.show('error', st.error_msg || '重新合成失败，已保留原成片')
        }
        // 进行中：继续轮询
      } catch {
        // 轮询出错：继续等下一轮
      }
    }, 3000)
  }

  onBeforeUnmount(stopPolling)

  return { recomposing, recomposedTs, trigger }
}
