#!/usr/bin/env bats
# ============================================================================
# ARKA OS — Workflow Classifier Tests (PR58 v2.75.0)
#
# The classifier decides whether a prompt triggers the mandatory 13-phase
# flow. PR58 widened the verb pattern after telemetry showed 97% of
# prompts in a long continuous-build session were "classifier-did-not-
# match" — most of them legitimate continuations of in-flight work.
# ============================================================================

load helpers/setup

# Resolve and source the classifier helper for every test in this file.
# We don't override the shared setup() — instead we use bats' setup_file
# to compute the repo-relative path once, then source the helper at the
# top of each test. The shared setup() runs first because of `load`.
TESTS_DIR="$(cd "$(dirname "${BATS_TEST_FILENAME}")" && pwd)"
ARKAOS_REPO_DIR="$(cd "$TESTS_DIR/.." && pwd)"
source "$ARKAOS_REPO_DIR/config/hooks/_lib/workflow-classifier.sh"

# ─── Original creation verbs still classified ──────────────────────────

@test "classify: 'create' is true" {
  [ "$(arka_wf_classify 'create a user auth feature')" = "true" ]
}

@test "classify: 'implement' is true" {
  [ "$(arka_wf_classify 'implement this')" = "true" ]
}

@test "classify: portuguese 'criar' is true" {
  [ "$(arka_wf_classify 'criar uma feature de auth')" = "true" ]
}

@test "classify: portuguese 'fazer' is true" {
  [ "$(arka_wf_classify 'faz isso aqui')" = "true" ]
}

# ─── PR58 — continuation verbs ─────────────────────────────────────────

@test "PR58: 'continua' is true (portuguese continuation)" {
  [ "$(arka_wf_classify 'continua')" = "true" ]
}

@test "PR58: 'força' is true (portuguese push)" {
  [ "$(arka_wf_classify 'força')" = "true" ]
}

@test "PR58: 'continue with the work' is true" {
  [ "$(arka_wf_classify 'continue with the next PR')" = "true" ]
}

@test "PR58: 'continuing' is true" {
  [ "$(arka_wf_classify 'continuing the work')" = "true" ]
}

@test "PR58: 'continuar' is true" {
  [ "$(arka_wf_classify 'vamos continuar')" = "true" ]
}

# ─── PR58 — ship-tier verbs ────────────────────────────────────────────

@test "PR58: 'ship v2.75' is true" {
  [ "$(arka_wf_classify 'ship v2.75 to npm')" = "true" ]
}

@test "PR58: 'merge that PR' is true" {
  [ "$(arka_wf_classify 'merge that PR')" = "true" ]
}

@test "PR58: 'publish to npm' is true" {
  [ "$(arka_wf_classify 'publish to npm')" = "true" ]
}

@test "PR58: 'release v2.75' is true" {
  [ "$(arka_wf_classify 'release v2.75')" = "true" ]
}

@test "PR58: 'deploy this' is true" {
  [ "$(arka_wf_classify 'deploy this to production')" = "true" ]
}

@test "PR58: 'shipping the next batch' is true" {
  [ "$(arka_wf_classify 'shipping the next batch now')" = "true" ]
}

# ─── PR58 — improvement / placement verbs ──────────────────────────────

@test "PR58: 'melhorar o arkaos' is true" {
  [ "$(arka_wf_classify 'melhorar o arkaos em si')" = "true" ]
}

@test "PR58: 'improve the api' is true" {
  [ "$(arka_wf_classify 'improve the api responses')" = "true" ]
}

@test "PR58: 'vamos colocar tudo' is true" {
  [ "$(arka_wf_classify 'vamos colocar todas do 1 ao 3')" = "true" ]
}

@test "PR58: 'finish this task' is true" {
  [ "$(arka_wf_classify 'finish this task')" = "true" ]
}

@test "PR58: 'terminar isto' is true" {
  [ "$(arka_wf_classify 'terminar isto agora')" = "true" ]
}

# ─── Negatives — questions, slash commands, bang shells, empty ─────────

@test "negative: 'what is X?' is false" {
  [ "$(arka_wf_classify 'what is X?')" = "false" ]
}

@test "X5: question with action verb is false" {
  [ "$(arka_wf_classify 'o que e que este projeto faz?')" = "false" ]
}

@test "X5: 'como fazes o deploy?' is false" {
  [ "$(arka_wf_classify 'como fazes o deploy?')" = "false" ]
}

@test "X5: 'how do I implement auth here?' is false" {
  [ "$(arka_wf_classify 'how do I implement auth here?')" = "false" ]
}

@test "X5: polite request keeps matching" {
  [ "$(arka_wf_classify 'podes implementar a exportacao?')" = "true" ]
}

@test "X5: interrogative lead without ? stays a directive" {
  [ "$(arka_wf_classify 'como combinado, implementa a feature')" = "true" ]
}

# ─── Multi-line: the lead is the FIRST line, as in the Python twin ─────
#
# grep anchors ^ per line, so passing the whole prompt let ANY line supply
# the interrogative lead — while re.match in core/hooks/user_prompt_submit
# .py can only match at offset 0. The two classifiers disagreed on every
# multi-line prompt that happens to end in a question. These four pin the
# agreed semantics; the bats suite had single-line cases only, which is
# exactly why the divergence was invisible.

@test "multiline: directive first, question last, stays a directive" {
  run arka_wf_classify 'implementa a feature de exportacao
o que e que isto faz?'
  [ "$output" = "true" ]
}

@test "multiline: question lead on line 1 is still a question" {
  run arka_wf_classify 'o que e que este projeto faz
e como e que implementa o deploy?'
  [ "$output" = "false" ]
}

@test "multiline: leading blank lines do not hide the lead" {
  run arka_wf_classify '

o que e que este projeto faz?'
  [ "$output" = "false" ]
}

@test "multiline: directive under a blank first line stays a directive" {
  run arka_wf_classify '

implementa isto
porque e que falha?'
  [ "$output" = "true" ]
}

@test "negative: 'how does Y work?' is false" {
  [ "$(arka_wf_classify 'how does Y work?')" = "false" ]
}

@test "negative: slash command is false" {
  [ "$(arka_wf_classify '/arka help')" = "false" ]
}

@test "negative: bang shell is false" {
  [ "$(arka_wf_classify '!ls')" = "false" ]
}

@test "negative: empty prompt is false" {
  [ "$(arka_wf_classify '')" = "false" ]
}

@test "negative: 'hello' alone is false" {
  [ "$(arka_wf_classify 'hello')" = "false" ]
}

@test "negative: 'thanks' alone is false" {
  [ "$(arka_wf_classify 'thanks for the help')" = "false" ]
}
