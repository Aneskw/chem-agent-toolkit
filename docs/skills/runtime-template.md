# Author-owned runtime section

Use this section once in SKILL.md, before the representative business example. Keep the common
wording and structure; adapt only the actual execution command, example filename, and necessary
source-supported device/resource options. {{task_command}} is an author input: replace it with
real argv such as python task.py, Rscript task.R, or the applicable tool command. Only {{image}}
remains for host finalization. The filename represents caller code, not a required saved script.
Do not create a script just to satisfy this template. Business code remains ordinary tool code.

````markdown
## Runtime environment

Use the preconfigured Docker image:

```bash
docker pull {{image}}
```

Execution example (Bash; replace the example filename or arguments for the task):

```bash
docker run --rm \
  --mount "type=bind,source=$(pwd),target=/work" \
  --workdir /work \
  {{image}} \
  {{task_command}}
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).
````

Do not repeat installation steps, alternate Docker wrappers or generic Docker explanations later.
Add exceptional prerequisites only when necessary for this tool, using the environment contract.
Do not write a command that requires unimplemented GPU/credential support. Report wrong host-owned
runtime fields as environment findings instead of changing runtime.json or contradicting it in prose.
