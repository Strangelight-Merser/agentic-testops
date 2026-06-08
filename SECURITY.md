# Security Policy

Agentic TestOps executes `pytest` in the target project. Treat audited projects as executable code.

## Supported Versions

The public repository currently supports the latest `main` branch.

## Reporting Security Issues

Please do not open a public issue for a security-sensitive report. Instead, contact the repository owner privately through GitHub profile contact options.

Useful details include:

- Operating system and Python version.
- Exact command used.
- Whether the issue involves command execution, artifact disclosure, or generated patch content.
- A minimal reproduction project if possible.

## Design Boundaries

- The tool does not apply generated fixes automatically.
- Dry-run patch output is intended for review.
- Reports may contain test output from the target project, so avoid running the tool on repositories that print secrets during tests.
