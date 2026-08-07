#!/usr/bin/env node
/**
 * Static SCOPE analysis for fenced JS/TS code in skill markdown (issue #457).
 *
 * WHY NOT `node --check`
 * ---------------------
 * The issue originally proposed `node --check`. It is the wrong tool and the
 * repo proves it: the block that motivated the gate --
 *
 *     ctx.clearRect(0, 0, w, h);          // w and h are never declared
 *
 * -- parses perfectly. An unresolvable identifier is a runtime ReferenceError,
 * never a parse error, so `node --check` exits 0 on the exact defect the gate
 * exists to catch. tests/python/test_fenced_code_scope.py pins that fact so the
 * gate can never silently regress back to a syntax check.
 *
 * The correct tool is static SCOPE analysis: ESLint's `no-undef` run over an
 * AST whose scope chain we control.
 *
 * THE SCOPE MODEL, AND WHY IT IS SHAPED THIS WAY
 * ---------------------------------------------
 * Doc snippets are fragments, not programs. Linting each fence in isolation
 * drowns the signal -- Francisca measured three false positives against two
 * true findings on canvas-generative/references/algorithms.md alone. Two
 * measured rules fix that:
 *
 * 1. CUMULATIVE PER FILE, IN DOCUMENT ORDER. Block N is analyzed with the
 *    top-level bindings of blocks 1..N-1 of the same file injected as globals.
 *    A doc that declares `class ParticleSystem` in one fence and uses it three
 *    fences later is correct prose, and the gate must agree.
 *
 *    NOTE ON IMPLEMENTATION: this is deliberately NOT literal text
 *    concatenation. Measured on this repo, gluing the fences of a file into one
 *    source produces a FATAL PARSE ERROR in 8 of 33 files -- two sibling JSX
 *    fragments become "JSX expressions must have one parent element", a
 *    trailing object-literal fragment splices into the next block, and so on. A
 *    fatal parse error suppresses every no-undef finding in that file, which is
 *    a silent fail-open of exactly the class issue #452 describes. Propagating
 *    the harvested BINDINGS instead delivers the same semantics -- block N sees
 *    the declarations of blocks 1..N-1 -- while keeping each fence
 *    independently parseable and each finding mapped to a real markdown line.
 *
 * 2. IMPORTS ARE SKILL-DIRECTORY-WIDE. A skill is one document set: SKILL.md
 *    plus its references/. When any fence in that set writes
 *    `import { ScrollTrigger } from "gsap/ScrollTrigger"`, the whole set has
 *    established that name, and a later fence that uses it without repeating
 *    the import boilerplate is documentation, not a bug. Measured: this rule
 *    alone removes 111 findings (359 -> 248) and needs no hand-maintained list
 *    of library names, because the skill's own code declares its surface.
 *    Value declarations do NOT get this treatment -- they stay strictly
 *    cumulative in document order, per rule 1.
 *
 * Whatever survives both rules is either genuinely undeclared or context the
 * prose establishes outside any fence; that residue is what the allowlist in
 * scripts/fenced-code-allowlist.json covers, entry by entry.
 *
 * TYPESCRIPT
 * ----------
 * @typescript-eslint/parser is used for every block, with no `project` option.
 * That is scope analysis only -- no type checking, no tsconfig, no `tsc`. The
 * parser handles plain JS as a superset, so one parser covers all six fence
 * languages.
 *
 * USAGE
 *   node scripts/lint_fenced_code.mjs                 # gate: exit 1 on findings
 *   node scripts/lint_fenced_code.mjs --json          # machine-readable report
 *   node scripts/lint_fenced_code.mjs --summary FILE  # append a markdown summary
 *   node scripts/lint_fenced_code.mjs --no-allowlist  # raw findings, ignore baseline
 *   node scripts/lint_fenced_code.mjs --update-allowlist
 */

import { readFileSync, writeFileSync, appendFileSync, readdirSync, existsSync } from 'node:fs';
import { join, dirname, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Linter } from 'eslint';
import * as tsParser from '@typescript-eslint/parser';

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_ROOT = dirname(HERE);
const ALLOWLIST_PATH = join(HERE, 'fenced-code-allowlist.json');

/**
 * Fence languages carrying executable JS/TS. `typescript` is included as the
 * long-form alias of `ts` -- the repo uses it 19 times and dropping it would
 * leave those blocks unchecked.
 */
export const ANALYZED_LANGS = Object.freeze(
  new Set(['js', 'javascript', 'jsx', 'ts', 'tsx', 'typescript']),
);

/**
 * Directory names never descended into.
 *   vendor       -- vendorized upstream trees carry their own pins and licences;
 *                   a finding there is not ours to fix and an edit breaks the lock.
 *   node_modules -- installed dependencies, not authored content.
 * `plugins/` is excluded structurally: it is a generated mirror of departments/
 * and is never reached because discovery is rooted at departments/.
 */
const SKIPPED_DIRS = Object.freeze(new Set(['vendor', 'node_modules']));

// ─── Discovery ──────────────────────────────────────────────────────────────

function walkMarkdown(dir, out = []) {
  let entries;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!SKIPPED_DIRS.has(entry.name)) walkMarkdown(full, out);
    } else if (entry.isFile() && entry.name.endsWith('.md')) {
      out.push(full);
    }
  }
  return out;
}

/**
 * The scoped corpus: `departments/**\/SKILL.md` and
 * `departments/**\/references/**\/*.md`, minus the skipped directories.
 * Sorted, so two runs enumerate identically.
 */
export function discoverFiles(root = DEFAULT_ROOT) {
  const base = join(root, 'departments');
  if (!existsSync(base)) return [];
  const isReference = (p) => p.split(sep).includes('references');
  return walkMarkdown(base)
    .filter((p) => p.endsWith(`${sep}SKILL.md`) || isReference(p))
    .sort();
}

/** Nearest ancestor directory holding a SKILL.md -- the document-set unit. */
function skillDirOf(file, root) {
  let dir = dirname(file);
  const stop = root;
  while (dir.startsWith(stop) && dir !== stop) {
    if (existsSync(join(dir, 'SKILL.md'))) return dir;
    dir = dirname(dir);
  }
  return dirname(file);
}

// ─── Extraction ─────────────────────────────────────────────────────────────

/**
 * Extract fenced code blocks in document order.
 *
 * CommonMark rules that matter here and are implemented deliberately:
 *  - a fence is 3+ backticks, indented at most 3 spaces;
 *  - the closing fence must be at least as long as the opening one, which is
 *    what keeps a ```js sample nested inside a ````markdown wrapper from being
 *    extracted as its own block;
 *  - the opening indent is stripped from body lines, so an indented fence
 *    inside a list item still yields valid source.
 *
 * `startLine` is the 1-based line of the block's FIRST CODE LINE in the
 * markdown file, so a finding at block-relative line L maps to startLine+L-1.
 */
export function extractFencedBlocks(text) {
  const lines = text.split('\n');
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const open = /^( {0,3})(`{3,})\s*(.*)$/.exec(lines[i]);
    if (!open) {
      i += 1;
      continue;
    }
    const [, indent, ticks, info] = open;
    const lang = (info.trim().split(/\s+/)[0] || '').toLowerCase();
    const startLine = i + 2;
    const body = [];
    i += 1;
    while (i < lines.length) {
      const close = /^ {0,3}(`{3,})\s*$/.exec(lines[i]);
      if (close && close[1].length >= ticks.length) break;
      body.push(lines[i].startsWith(indent) ? lines[i].slice(indent.length) : lines[i]);
      i += 1;
    }
    if (ANALYZED_LANGS.has(lang)) blocks.push({ lang, code: body.join('\n'), startLine });
    i += 1; // step over the closing fence
  }
  return blocks;
}

// ─── Analysis ───────────────────────────────────────────────────────────────

const HARVEST_RULE = '__arkaos_harvest_scope';

/**
 * `<T>expr` is a type assertion in .ts and a JSX element in .tsx, so the two
 * cannot share a parser setting. Every language except explicit TypeScript
 * gets JSX: plain JS fences do embed JSX in these docs, and JS has no generics
 * for the syntax to collide with.
 */
const jsxFor = (lang) => lang !== 'ts' && lang !== 'typescript';

function buildLinter() {
  const linter = new Linter();
  linter.defineParser('arkaos-ts', tsParser);
  const harvest = { all: [], imports: [] };
  linter.defineRule(HARVEST_RULE, {
    create(context) {
      return {
        'Program:exit'(node) {
          const sourceCode = context.sourceCode ?? context.getSourceCode();
          const global = sourceCode.getScope
            ? sourceCode.getScope(node)
            : context.getScope();
          // getScope() at Program yields the GLOBAL scope, which under this
          // parser is prepopulated with the TypeScript lib declarations. The
          // block's own top-level bindings -- including its imports -- live in
          // the nested module scope.
          const moduleScope = global.childScopes.find((s) => s.type === 'module') ?? global;
          harvest.all = moduleScope.variables.map((v) => v.name);
          harvest.imports = moduleScope.variables
            .filter((v) => v.defs.some((d) => d.type === 'ImportBinding'))
            .map((v) => v.name);
        },
      };
    },
  });
  return { linter, harvest };
}

function configFor(lang, globals) {
  return {
    parser: 'arkaos-ts',
    parserOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      ecmaFeatures: { jsx: jsxFor(lang) },
      // No `project`/`programs`: scope analysis only. This is not tsc.
    },
    // Browser globals are the right baseline -- this corpus is animation,
    // canvas, DOM and analytics documentation. es2022 covers the standard
    // library surface the snippets use.
    env: { browser: true, es2022: true },
    globals,
    rules: { 'no-undef': 'error', [HARVEST_RULE]: 'error' },
  };
}

const identifierOf = (message) => /'([^']+)'/.exec(message)?.[1] ?? message;

/**
 * Analyze the corpus.
 *
 * Returns { undefined: [...], parseErrors: [...], stats: {...} } with every
 * list sorted, so two runs over an unchanged tree are byte-identical.
 */
/**
 * @param {object}  [options]
 * @param {string}  [options.root]        Repository root to analyze.
 * @param {?string[]} [options.files]     Explicit file list (defaults to discovery).
 * @param {boolean} [options.cumulative]  When false, every block is analyzed in
 *   isolation -- neither the per-file document-order propagation nor the
 *   skill-directory import surface is applied. This exists so the design
 *   decision is FALSIFIABLE: flipping it must resurrect the false positives
 *   Francisca measured (canvas, ctx, ParticleSystem on algorithms.md), which is
 *   what tests/python/test_fenced_code_scope.py asserts. It is not a supported
 *   mode for the gate.
 */
export function analyze({ root = DEFAULT_ROOT, files = null, cumulative = true } = {}) {
  const targets = files ?? discoverFiles(root);
  const { linter, harvest } = buildLinter();

  // Group by skill directory: SKILL.md and its references/ are one document set.
  const groups = new Map();
  for (const file of targets) {
    let blocks;
    try {
      blocks = extractFencedBlocks(readFileSync(file, 'utf8'));
    } catch {
      continue;
    }
    if (!blocks.length) continue;
    const key = skillDirOf(file, root);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({ file, blocks });
  }

  const undefinedFindings = [];
  const parseErrors = [];
  let blockCount = 0;
  let fileCount = 0;

  for (const key of [...groups.keys()].sort()) {
    const entries = groups.get(key).sort((a, b) => a.file.localeCompare(b.file));

    // Pass 1 -- skill-directory-wide import surface (rule 2 in the header).
    const dirImports = Object.create(null);
    if (cumulative) {
      for (const { blocks } of entries) {
        for (const block of blocks) {
          harvest.imports = [];
          linter.verify(block.code, configFor(block.lang, {}));
          for (const name of harvest.imports) dirImports[name] = 'readonly';
        }
      }
    }

    // Pass 2 -- cumulative, in document order, per file (rule 1 in the header).
    for (const { file, blocks } of entries) {
      fileCount += 1;
      const inherited = { ...dirImports };
      const rel = relative(root, file).split(sep).join('/');
      for (let index = 0; index < blocks.length; index += 1) {
        const block = blocks[index];
        blockCount += 1;
        harvest.all = [];
        const messages = linter.verify(block.code, configFor(block.lang, inherited));

        const fatal = messages.find((m) => m.fatal);
        if (fatal) {
          // A block that will not parse is a block that was NOT scope-analyzed.
          // Reporting it as its own class keeps that visible; swallowing it
          // would be a silent fail-open.
          parseErrors.push({
            file: rel,
            blockIndex: index,
            lang: block.lang,
            line: block.startLine + fatal.line - 1,
            message: fatal.message,
          });
        }
        for (const m of messages) {
          if (m.ruleId !== 'no-undef') continue;
          undefinedFindings.push({
            file: rel,
            identifier: identifierOf(m.message),
            line: block.startLine + m.line - 1,
            lang: block.lang,
          });
        }
        // Propagate this block's top-level bindings to the blocks after it.
        if (cumulative) for (const name of harvest.all) inherited[name] = 'writable';
      }
    }
  }

  const byFileThenLine = (a, b) =>
    a.file.localeCompare(b.file) || a.line - b.line || String(a.identifier ?? '').localeCompare(String(b.identifier ?? ''));
  undefinedFindings.sort(byFileThenLine);
  parseErrors.sort((a, b) => a.file.localeCompare(b.file) || a.blockIndex - b.blockIndex);

  return {
    undefined: undefinedFindings,
    parseErrors,
    stats: { files: fileCount, blocks: blockCount },
  };
}

// ─── Allowlist ──────────────────────────────────────────────────────────────

export function loadAllowlist(path = ALLOWLIST_PATH) {
  if (!existsSync(path)) return { assumedContext: {}, trackedFindings: {}, unparseableBlocks: {} };
  const raw = JSON.parse(readFileSync(path, 'utf8'));
  return {
    assumedContext: raw.assumedContext ?? {},
    trackedFindings: raw.trackedFindings ?? {},
    unparseableBlocks: raw.unparseableBlocks ?? {},
  };
}

/**
 * Split findings into suppressed and reportable, and surface allowlist entries
 * that no longer match anything. Baselines are keyed by identifier name and by
 * block index -- both survive ordinary line drift, and both change exactly when
 * a re-triage is actually warranted.
 */
export function applyAllowlist(report, allowlist) {
  const assumed = new Set(Object.keys(allowlist.assumedContext));
  const tracked = new Map(
    Object.entries(allowlist.trackedFindings).map(([file, entry]) => [
      file,
      new Set(entry.identifiers ?? []),
    ]),
  );
  const unparseable = new Map(
    Object.entries(allowlist.unparseableBlocks).map(([file, entry]) => [
      file,
      new Set(entry.blocks ?? []),
    ]),
  );

  const usedAssumed = new Set();
  const usedTracked = new Map();
  const usedUnparseable = new Map();

  const reportable = [];
  for (const finding of report.undefined) {
    if (assumed.has(finding.identifier)) {
      usedAssumed.add(finding.identifier);
      continue;
    }
    const set = tracked.get(finding.file);
    if (set?.has(finding.identifier)) {
      if (!usedTracked.has(finding.file)) usedTracked.set(finding.file, new Set());
      usedTracked.get(finding.file).add(finding.identifier);
      continue;
    }
    reportable.push(finding);
  }

  const reportableParse = [];
  for (const error of report.parseErrors) {
    const set = unparseable.get(error.file);
    if (set?.has(error.blockIndex)) {
      if (!usedUnparseable.has(error.file)) usedUnparseable.set(error.file, new Set());
      usedUnparseable.get(error.file).add(error.blockIndex);
      continue;
    }
    reportableParse.push(error);
  }

  const stale = [];
  for (const name of assumed) if (!usedAssumed.has(name)) stale.push(`assumedContext: ${name}`);
  for (const [file, set] of tracked) {
    for (const name of set) {
      if (!usedTracked.get(file)?.has(name)) stale.push(`trackedFindings: ${file} -> ${name}`);
    }
  }
  for (const [file, set] of unparseable) {
    for (const index of set) {
      if (!usedUnparseable.get(file)?.has(index)) {
        stale.push(`unparseableBlocks: ${file} -> block ${index}`);
      }
    }
  }

  return { reportable, reportableParse, stale: stale.sort() };
}

/** Regenerate the baseline sections from a raw report, preserving justifications. */
function rebuildAllowlist(report, existing) {
  const assumed = new Set(Object.keys(existing.assumedContext));
  const trackedFindings = {};
  for (const finding of report.undefined) {
    if (assumed.has(finding.identifier)) continue;
    const entry = (trackedFindings[finding.file] ??= {
      note: existing.trackedFindings[finding.file]?.note ?? 'real findings, tracked',
      identifiers: [],
    });
    if (!entry.identifiers.includes(finding.identifier)) entry.identifiers.push(finding.identifier);
  }
  for (const entry of Object.values(trackedFindings)) entry.identifiers.sort();

  const unparseableBlocks = {};
  for (const error of report.parseErrors) {
    const entry = (unparseableBlocks[error.file] ??= {
      note: existing.unparseableBlocks[error.file]?.note ?? 'real findings, tracked',
      blocks: [],
    });
    if (!entry.blocks.includes(error.blockIndex)) entry.blocks.push(error.blockIndex);
  }
  for (const entry of Object.values(unparseableBlocks)) entry.blocks.sort((a, b) => a - b);

  const sortKeys = (obj) =>
    Object.fromEntries(Object.entries(obj).sort(([a], [b]) => a.localeCompare(b)));

  return {
    _comment: existing._comment,
    assumedContext: existing.assumedContext,
    trackedFindings: sortKeys(trackedFindings),
    unparseableBlocks: sortKeys(unparseableBlocks),
  };
}

// ─── CLI ────────────────────────────────────────────────────────────────────

function main(argv) {
  const args = new Set(argv);
  // Read a flag's value, rejecting a trailing flag with no value rather than
  // letting `undefined` reach path.join() as an opaque TypeError.
  const valueOf = (flag, fallback) => {
    if (!args.has(flag)) return fallback;
    const value = argv[argv.indexOf(flag) + 1];
    if (!value || value.startsWith('--')) {
      throw new Error(`${flag} requires a value`);
    }
    return value;
  };
  const summaryPath = valueOf('--summary', null);
  const root = valueOf('--root', DEFAULT_ROOT);

  const started = Date.now();
  const report = analyze({ root, cumulative: !args.has('--no-cumulative') });
  const elapsedMs = Date.now() - started;

  if (args.has('--update-allowlist')) {
    const existing = JSON.parse(
      existsSync(ALLOWLIST_PATH) ? readFileSync(ALLOWLIST_PATH, 'utf8') : '{}',
    );
    const rebuilt = rebuildAllowlist(report, {
      assumedContext: existing.assumedContext ?? {},
      trackedFindings: existing.trackedFindings ?? {},
      unparseableBlocks: existing.unparseableBlocks ?? {},
      _comment: existing._comment,
    });
    writeFileSync(ALLOWLIST_PATH, `${JSON.stringify(rebuilt, null, 2)}\n`);
    process.stdout.write(`Allowlist rewritten: ${ALLOWLIST_PATH}\n`);
    return 0;
  }

  const useAllowlist = !args.has('--no-allowlist');
  const allowlist = useAllowlist
    ? loadAllowlist()
    : { assumedContext: {}, trackedFindings: {}, unparseableBlocks: {} };
  const { reportable, reportableParse, stale } = applyAllowlist(report, allowlist);

  const failed = reportable.length + reportableParse.length + stale.length;

  if (args.has('--json')) {
    process.stdout.write(
      `${JSON.stringify(
        {
          stats: { ...report.stats, elapsedMs },
          undefinedTotal: report.undefined.length,
          parseErrorTotal: report.parseErrors.length,
          reportable,
          reportableParse,
          stale,
        },
        null,
        2,
      )}\n`,
    );
  } else {
    const lines = [];
    lines.push(
      `fenced-code scope analysis: ${report.stats.blocks} JS/TS blocks in ` +
        `${report.stats.files} markdown files (${elapsedMs} ms)`,
    );
    lines.push(
      `  no-undef: ${report.undefined.length} raw, ${reportable.length} unallowlisted`,
    );
    lines.push(
      `  unparseable blocks: ${report.parseErrors.length} raw, ${reportableParse.length} unallowlisted`,
    );
    for (const f of reportable) {
      lines.push(`  ${f.file}:${f.line}  '${f.identifier}' is not defined  [${f.lang}]`);
    }
    for (const e of reportableParse) {
      lines.push(`  ${e.file}:${e.line}  unparseable block ${e.blockIndex} [${e.lang}]: ${e.message}`);
    }
    for (const s of stale) {
      lines.push(`  STALE allowlist entry (rerun with --update-allowlist): ${s}`);
    }
    process.stdout.write(`${lines.join('\n')}\n`);
  }

  if (summaryPath) {
    const verdict = failed === 0 ? 'PASS' : `FAIL (${failed} unallowlisted)`;
    appendFileSync(
      summaryPath,
      [
        '### Fenced JS/TS scope analysis (issue #457)',
        '',
        `- Corpus: **${report.stats.blocks}** JS/TS blocks in **${report.stats.files}** markdown files`,
        `- \`no-undef\`: ${report.undefined.length} raw / ${reportable.length} unallowlisted`,
        `- Unparseable blocks: ${report.parseErrors.length} raw / ${reportableParse.length} unallowlisted`,
        `- Stale allowlist entries: ${stale.length}`,
        `- Elapsed: ${elapsedMs} ms`,
        '',
        `**${verdict}**`,
        '',
      ].join('\n'),
    );
  }

  return failed === 0 ? 0 : 1;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  // process.exitCode, never process.exit(): stdout is asynchronous on a pipe,
  // and exiting outright truncates the report at the 64KB pipe buffer. Measured
  // -- the --json payload is larger than that, and process.exit() cut it mid
  // object. Setting the code lets Node drain stdout and then exit naturally.
  try {
    process.exitCode = main(process.argv.slice(2));
  } catch (error) {
    // A usage error is not a finding; report it as such instead of a stack
    // trace, and use a distinct exit code so CI can tell them apart.
    process.stderr.write(`lint_fenced_code: ${error.message}\n`);
    process.exitCode = 2;
  }
}
