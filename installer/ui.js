/**
 * ArkaOS installer UI facade (Foundation PR-3).
 *
 * Single abstraction over the terminal output of install/update/prompts.
 * Two render modes:
 *
 *   fancy  @clack/prompts + picocolors — branded intro, spinner per
 *          step, grouped notes, outro. Active ONLY when the optional
 *          dependencies load, stdout is a TTY, we are not in CI, and
 *          the user did not force plain via ARKA_UI_PLAIN=1.
 *
 *   plain  byte-identical to the historical installer output
 *          (`  [n/total] msg`, `         ✓ msg`, `         ⚠ msg`,
 *          plain box banner) so headless logs, the auto-update daemon,
 *          and existing tests remain stable.
 *
 * House rule (.claude/rules/node-installer.md): graceful fallbacks when
 * optional dependencies are unavailable — a missing @clack/prompts can
 * NEVER throw; it degrades to plain.
 */

let cachedUi = null;

async function loadFancyDeps() {
  try {
    const clack = await import("@clack/prompts");
    const pico = await import("picocolors");
    const pc = pico.default ?? pico;
    // Minimal shape check so a broken/partial install degrades to plain
    // instead of crashing mid-wizard.
    if (typeof clack.intro !== "function" || typeof clack.spinner !== "function") {
      return null;
    }
    return { clack, pc };
  } catch {
    return null;
  }
}

/**
 * Resolve the UI facade. Cached after the first call so install() and
 * runSetupPrompts() share one instance (and one spinner state).
 */
export async function getUi() {
  if (cachedUi) return cachedUi;
  const deps = await loadFancyDeps();
  const fancy =
    Boolean(deps) &&
    Boolean(process.stdout.isTTY) &&
    !process.env.CI &&
    process.env.ARKA_UI_PLAIN !== "1";
  cachedUi = fancy ? makeFancyUi(deps) : makePlainUi();
  return cachedUi;
}

/** Test hook — drop the cached facade so env changes take effect. */
export function resetUiCache() {
  cachedUi = null;
}

// ── Plain mode — the historical installer output, byte-identical ──────────

function makePlainUi() {
  const step = (n, total, msg) => {
    console.log(`  [${n}/${total}] ${msg}`);
  };
  return {
    isFancy: () => false,
    clack: null,
    colors: null,
    intro(title) {
      const inner = `  ${title}`.padEnd(54);
      console.log(`
  ╔══════════════════════════════════════════════════════╗
  ║${inner}║
  ╚══════════════════════════════════════════════════════╝
  `);
    },
    outro(msg) {
      console.log(`\n  ${msg}\n`);
    },
    note(body, title) {
      if (title) console.log(`\n  ── ${title} ──\n`);
      console.log(
        String(body)
          .split("\n")
          .map((l) => `    ${l}`)
          .join("\n"),
      );
    },
    step,
    section: step,
    ok(msg) {
      console.log(`         ✓ ${msg}`);
    },
    warn(msg) {
      console.log(`         ⚠ ${msg}`);
    },
    detail(msg) {
      console.log(msg);
    },
    spinner() {
      return {
        start(msg) {
          if (msg) console.log(msg);
        },
        stop(msg) {
          if (msg) console.log(msg);
        },
        message() {},
      };
    },
    stopSpinner() {},
    warnings: () => [],
  };
}

// ── Fancy mode — clack spinners, grouped sections, branded intro ──────────

function makeFancyUi({ clack, pc }) {
  let active = null; // { s, title, okCount }
  const warnings = [];

  const finishActive = () => {
    if (!active) return;
    const suffix =
      active.okCount > 0 ? pc.dim(` (${active.okCount} ok)`) : "";
    active.s.stop(`${active.title}${suffix}`);
    active = null;
  };

  const step = (n, total, msg) => {
    finishActive();
    const s = clack.spinner();
    const title = `${pc.dim(`[${n}/${total}]`)} ${msg}`;
    s.start(title);
    active = { s, title, okCount: 0 };
  };

  return {
    isFancy: () => true,
    clack,
    colors: pc,
    intro(title) {
      clack.intro(pc.inverse(pc.bold(` ${title} `)));
    },
    outro(msg) {
      finishActive();
      clack.outro(msg);
    },
    note(body, title) {
      finishActive();
      clack.note(body, title);
    },
    step,
    section: step,
    ok(msg) {
      if (active) {
        active.okCount += 1;
        active.s.message(`${active.title} ${pc.dim("·")} ${pc.green(msg)}`);
      } else {
        clack.log.success(msg);
      }
    },
    warn(msg) {
      warnings.push(msg);
      if (active) {
        active.s.message(`${active.title} ${pc.yellow(`⚠ ${msg}`)}`);
      } else {
        clack.log.warn(msg);
      }
    },
    detail(msg) {
      const t = String(msg).trim();
      if (!t) return;
      if (active) {
        active.s.message(`${active.title} ${pc.dim(t)}`);
      } else {
        clack.log.message(pc.dim(t));
      }
    },
    spinner() {
      return clack.spinner();
    },
    stopSpinner() {
      finishActive();
    },
    warnings: () => [...warnings],
  };
}
