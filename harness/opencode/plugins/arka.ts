import type { Plugin } from "@opencode-ai/plugin"
import { homedir } from "node:os"
import { join } from "node:path"

const ARKA_PY = join(homedir(), ".arkaos", "bin", "arka-py")

type HookResult = Record<string, any> | null

function runHook(action: string, payload: Record<string, any>): HookResult {
  try {
    const body = JSON.stringify({ action, ...payload })
    const proc = Bun.spawnSync([ARKA_PY, "-m", "core.runtime.opencode_hooks"], {
      stdin: Buffer.from(body),
      stdout: "pipe",
      stderr: "pipe",
    })
    if (proc.exitCode !== 0) return null
    return JSON.parse(proc.stdout.toString() || "null")
  } catch {
    return null
  }
}

export const ArkaPlugin: Plugin = async ({ client, directory }) => {
  const log = async (level: "info" | "warn" | "error", message: string) => {
    try {
      await client.app.log({ body: { service: "arka", level, message } })
    } catch {}
  }

  await log("info", "ArkaOS opencode bridge loaded")

  return {
    "tui.prompt.append": async (input: any, output: any) => {
      const result = runHook("prompt", {
        prompt: String(input?.text ?? ""),
        session_id: String(input?.sessionID ?? ""),
      })
      const suggestions: string[] = result?.suggestions ?? []
      if (suggestions.length > 0) {
        output.text += "\n\n" + suggestions.join("\n")
      }
    },

    "tool.execute.before": async (input: any, output: any) => {
      const result = runHook("pre_tool", {
        tool: String(input?.tool ?? ""),
        args: output?.args ?? {},
        session_id: String(input?.sessionID ?? ""),
        cwd: directory,
      })
      if (!result) return
      if (result.allow === false) {
        throw new Error(result.message || "Blocked by ArkaOS gate")
      }
      if (result.message) {
        await log("warn", result.message)
      }
    },

    "tool.execute.after": async (input: any) => {
      runHook("post_tool", {
        tool: String(input?.tool ?? ""),
        session_id: String(input?.sessionID ?? ""),
        ok: true,
      })
    },

    "experimental.session.compacting": async (_input: any, output: any) => {
      const result = runHook("compact", {})
      const context: string[] = result?.context ?? []
      for (const line of context) {
        output.context.push(line)
      }
    },

    event: async ({ event }: any) => {
      if (event?.type === "session.created") {
        await log("info", "ArkaOS gates active (kb-first, frontend, compliance)")
        return
      }
      if (event?.type !== "session.idle") return
      try {
        const sessionID = String(event?.properties?.sessionID ?? "")
        if (!sessionID) return
        const response: any = await client.session.messages({
          path: { id: sessionID },
        })
        const messages: any[] = Array.isArray(response?.data)
          ? response.data
          : Array.isArray(response)
            ? response
            : []
        const lastAssistant = [...messages]
          .reverse()
          .find((m: any) => m?.info?.role === "assistant" || m?.role === "assistant")
        const parts: any[] = lastAssistant?.parts ?? []
        const text = parts
          .filter((p: any) => p?.type === "text")
          .map((p: any) => String(p?.text ?? ""))
          .join("\n")
        if (!text) return
        const result = runHook("idle", {
          response_text: text.slice(-20000),
          session_id: sessionID,
        })
        for (const nudge of result?.nudges ?? []) {
          await log("warn", nudge)
        }
      } catch {}
    },
  }
}
