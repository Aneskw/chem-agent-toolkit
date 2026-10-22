# Agent effectiveness evaluation

Agent effectiveness is evaluated separately from skill construction. This directory is reserved for independent evaluation work; the build pipeline does not create benchmark questions, run Agent A/B experiments or score effectiveness.

A study should freeze independent tasks and expected outcomes, keep tool and environment access comparable, and compare quality, recovery, cost and runtime across multiple runs. Distinguish the effect of instructions from the effect of newly supplied scripts or tools.

Retain original experimental traces, scores and negative results independently of ordinary build cleanup. Passing build checks alone does not establish Agent benefit.
