# Contributing to model-compose

Thanks for your interest in **model-compose**. This guide walks through how to set up the project locally, propose changes, and get them merged.

For the legal terms that apply to code and documentation contributions, see the [Contributor Assignment Agreement](#contributor-assignment-agreement) section at the bottom of this document. Bug reports, feature requests, and discussion comments are **not** covered by that agreement and are always welcome.

---

## Ways to Contribute

- Reporting bugs and unexpected behavior
- Suggesting features or improvements
- Improving documentation, examples, or error messages
- Fixing bugs or implementing features through pull requests

If you are unsure whether a change is in scope, open an issue first to discuss the idea before investing significant time.

---

## Development Setup

### Prerequisites

- Python **3.10 or newer**
- `git`
- (Optional) Docker, if you plan to work on the Docker runtime

### Clone and Install

```bash
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .
```

This installs `model-compose` in editable mode so local changes take effect immediately.

### Verify

```bash
model-compose --version
```

---

## Running Tests

The test suite uses `pytest`:

```bash
pip install pytest
python -m pytest tests/
```

Please run the tests locally before opening a pull request, and add or update tests when you change behavior.

---

## Coding Style

- Follow the conventions already used in the file you are editing.
- Keep changes focused: one logical change per pull request.
- Prefer small, readable functions over large ones.
- Match existing naming patterns for components, actions, and services.

---

## Submitting a Pull Request

1. **Fork** the repository and create a branch off `main`, for example `feature/my-improvement` or `fix/some-bug`.
2. **Make your changes** in focused commits with clear messages.
3. **Add or update tests** under `tests/` for any behavioral change.
4. **Run the test suite** locally.
5. **Open a pull request** against `main` with:
   - A clear title summarizing the change.
   - A description that explains *what* changed and *why*.
   - Links to any related issues.

### Pull Request Checklist

- [ ] Tests pass locally (`python -m pytest tests/`).
- [ ] New behavior is covered by tests where practical.
- [ ] Documentation and examples are updated if user-facing behavior changes.
- [ ] The pull request has a single, well-defined purpose.
- [ ] You have read and agreed to the [Contributor Assignment Agreement](#contributor-assignment-agreement) below.

---

## Reporting Issues

When reporting a bug, please include:

- A clear, descriptive title.
- Steps to reproduce the issue.
- Expected vs. actual behavior.
- Your environment: OS, Python version, model-compose version.
- Relevant logs, configuration snippets, or error messages.

For feature requests, describe the use case and why existing functionality is not sufficient.

---

## Contributor Assignment Agreement

model-compose accepts code and documentation contributions under a **Contributor Assignment Agreement (CAA)**. By opening a pull request — or otherwise submitting code, documentation, or other copyrightable material intended for inclusion in the project — you agree to the terms of the agreement.

> **By submitting a pull request or other copyrightable material intended for inclusion in model-compose, you agree to the model-compose Contributor Assignment Agreement, Version 1.0, effective 2026-05-26:**
>
> https://gist.github.com/hanyeol/373a0d9300f84d0af65770dbd61caa16

In short:

- The agreement applies **only to copyrightable material you intentionally submit for inclusion** (pull requests, patches, documentation changes).
- It does **not** apply to bug reports, feature requests, questions, or discussion comments.
- You assign copyright in your contribution to the project owner, who may relicense the project in the future.
- If you contribute on behalf of an employer or organization, please contact the maintainer in advance to arrange a separate written agreement.

Please read the full agreement before your first pull request. If you have questions, contact **Hanyeol Cho** at hanyeol.cho@gmail.com.

---

*Thank you for helping make model-compose better.*
