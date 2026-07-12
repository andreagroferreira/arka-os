---
name: estimate-forecast
description: >
  Estimation and delivery forecasting: story points, throughput analysis,
  and Monte Carlo simulation producing confidence intervals (50th/85th/95th
  percentile) for "when will it be done". TRIGGER: "quando fica pronto",
  "estima este backlog", "when will this ship", "forecast the release
  date", "Monte Carlo forecast", "/pm estimate". SKIP: sizing items during
  refinement -> pm/backlog-groom (estimation inside grooming, not
  probabilistic forecasting); committing capacity for a single sprint ->
  pm/sprint-plan; quantifying code-quality drag on delivery ->
  dev/tech-debt (debt economics, not schedule forecasting).
---

# Estimate Forecast

> **Agent:** Jorge (Scrum Master) | **Framework:** Monte Carlo Forecasting (Vacanti)

## What It Does

Estimation and forecasting: story points, throughput, Monte Carlo probability.

## Output

Forecast with confidence intervals (50th, 85th, 95th percentile)
