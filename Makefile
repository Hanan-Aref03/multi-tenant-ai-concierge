# Hanan: use these targets when wiring backend workflows and integration checks.
# Mohammad: use these targets when validating security, migrations, and tenant isolation.
# Rayan: use these targets when running evals and guardrail checks.
# Ali Faddel: use these targets when iterating on widget/admin CI and release tasks.

.PHONY: help bootstrap lint test eval fmt clean verify-isolation team-checks

help:
	@echo "Available targets: bootstrap, lint, test, eval, fmt, clean, verify-isolation, team-checks"

bootstrap:
	docker compose up -d postgres redis minio vault

lint:
	python -m compileall apps services tests

test:
	python -m unittest discover -s tests -t . -p "test_*.py"

eval:
	powershell -ExecutionPolicy Bypass -File scripts/verify_isolation.ps1

fmt:
	@echo "Formatters are deferred until the Python packaging layer lands."

verify-isolation:
	powershell -ExecutionPolicy Bypass -File scripts/verify_isolation.ps1

team-checks:
	powershell -ExecutionPolicy Bypass -File scripts/run_team_checks.ps1

clean:
	@echo "Remove local build artifacts manually when needed."
