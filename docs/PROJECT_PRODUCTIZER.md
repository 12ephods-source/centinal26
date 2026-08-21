# Project Productizer

Purpose: convert exported project conversations and project documents into durable, testable product-development artifacts without consuming one scheduler slot per workflow.

## Architecture

`conversation/project export -> deterministic extraction -> project brief -> feature registry -> product roadmap -> CI artifact -> implementation backlog -> tested product -> release candidate`

The system is event-driven. GitHub Actions runs when `project_exports/**` changes or through manual dispatch. External builders can invoke the CLI on file arrival, repository webhook, app event, or queue message. Hourly scheduling is not required.

## Prompt propagation

`PROMPT_BOOTSTRAP.md` contains the consolidated Frost response/project protocol. The productizer copies it into every generated project package. It can be used as project instructions or as the system/developer bootstrap for applications that the user controls.

Important limitation: a repository program cannot retroactively modify the hidden system/developer prompt of arbitrary existing ChatGPT conversations. For ChatGPT conversations, propagation must occur through supported Project instructions/memory/product settings or by explicitly supplying the bootstrap. The program therefore creates the canonical prompt artifact rather than pretending to mutate inaccessible conversations.

## Productization gates

1. CONVERSATION
2. VERIFIED_REQUIREMENT
3. REUSABLE_CAPABILITY
4. TESTED_FEATURE
5. INTEGRATED_PRODUCT
6. RELEASE_CANDIDATE
7. COMMERCIAL_APP

Promotion requires evidence. A capability does not become a commercial feature merely because it was discussed or scripted.

## Inputs

UTF-8 Markdown, text, or JSON conversation/project exports. Direct access to ChatGPT project history is intentionally not assumed.

## Outputs

- `PROMPT_BOOTSTRAP.md`
- `PROJECT_BRIEF.md`
- `FEATURE_REGISTRY.json`
- `PRODUCT_ROADMAP.json`
- `MANIFEST.json`

## Execution

```bash
python tools/project_productizer.py project_exports -o productized_project
```

The output manifest hashes every source and generated artifact so later product work can retain provenance.

## Commercialization principle

The engine is a compiler for project knowledge, not an automatic claim that every conversation should become a product. Feature candidates must pass requirements, implementation, test, integration, security/privacy, and release gates. Product-specific repositories/apps should consume the feature registry and preserve links back to originating evidence.
