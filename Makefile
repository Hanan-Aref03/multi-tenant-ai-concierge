# Hanan: use these targets when wiring backend workflows and integration checks.
# Mohammad: use these targets when validating security, migrations, and tenant isolation.
# Rayan: use these targets when running evals and guardrail checks.
# Ali Faddel: use these targets when iterating on widget/admin CI and release tasks.

.PHONY: help bootstrap lint test eval fmt clean

help:
	@echo "Available targets: bootstrap, lint, test, eval, fmt, clean"

bootstrap:
	@echo "TODO: install dependencies and initialize local services"

lint:
	@echo "TODO: run linters"

test:
	@echo "TODO: run automated tests"

eval:
	@echo "TODO: run model, RAG, and red-team evals"

fmt:
	@echo "TODO: format code"

clean:
	@echo "TODO: remove generated artifacts"

