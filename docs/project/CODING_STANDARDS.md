# Coding standards

Dayglance is a small, dependency-light application intended to run on Raspberry Pi hardware. Keep changes easy to inspect, reliable on the supported touchscreen, and simple to install.

## Style and dependencies

- Follow the whitespace rules in [`.editorconfig`](../../.editorconfig): UTF-8, LF endings, spaces, two-space indentation for web/config/documentation/shell files, and four-space indentation for standalone Python files.
- In JavaScript, use `const` by default, `let` when reassignment is needed, descriptive names, and the existing semicolon style. Avoid adding a frontend framework, build system, or runtime dependency without a clear benefit for the Pi 3 B+ target.
- Keep the server compatible with the Python standard library where practical. Use four-space indentation and type hints for new standalone Python code.
- Keep shell scripts POSIX `sh` compatible, fail fast with `set -eu`, and quote paths and expansions.
- Keep `config.json` valid JSON (no comments or trailing commas). Document accepted values and examples in its `_documentation` section and `CONFIGURATION.md`.

## Runtime and accessibility

- Preserve the app's compact landscape layout, including the 800×480 touchscreen target, and check that touch targets remain usable.
- For touch-first layouts, prefer direct content swipes over scrollbar handles, particularly on small displays. Keep keyboard and native scrolling available, and do not make a visible scrollbar necessary to discover or use overflowing content. See [DESIGN_NOTES.md](DESIGN_NOTES.md).
- For scroll behavior changes, separately check each applicable input path (touch swipe, mouse-like drag, wheel/trackpad, keyboard, and horizontal swipe), the correct direction and range, controls within the scroll surface, and any sticky navigation or interaction timer. Use the verification checklist in [DESIGN_NOTES.md](DESIGN_NOTES.md); report simulated and physical-device checks distinctly.
- Use semantic HTML, visible focus states, accessible names for icon-only controls, and text alternatives for weather icons and state.
- Do not prevent the operating system's screensaver or display sleep. On resume, refresh stale data without losing the user's current place in the app.
- Treat location names, API responses, and configuration values as input. Render text with safe DOM APIs; validate config types and ranges before using them.
- Never put API keys, passwords, or other secrets in `config.json`, which the local web server serves to browsers. Keep any future provider credentials in a separate device-local server-side store with restricted permissions.
- Preserve attribution and the license/terms required by each data source.

## Verification expected for changes

Run the checks relevant to the change and include the result in the pull request:

```sh
node --check app.js
node --check radar.js
node --test tests/test-radar.js
python3 -m unittest discover -s tests -v
sh -n launch-dayglance.sh install-autostart.sh tests/test-launcher-config.sh
python3 -m json.tool config.json >/dev/null
sh tests/test-launcher-config.sh
```

For UI work, also inspect the changed flow in a browser and, when available, on the target touchscreen. Check the 800×480 layout, keyboard-free use, touch/swipe behavior, and screensaver resume when affected. Update screenshots and user documentation when visible behavior or setup instructions change.

## Enforcement status

The `CI` GitHub Actions workflow runs the syntax, radar, configuration, and launcher checks above for pushes to `main` and pull requests targeting `main`. Its job check is named `CI / Verify`. The workflow is deliberately dependency-light and does not install a formatter or linter; keep the documented style reviewable and consistent, and add a formatter only with a clear benefit and an agreed repository-wide configuration.

The workflow file is present in this working tree. It becomes an active GitHub check after it is published to the repository. Once a successful run has established the check, configure `main` to require pull requests and the `CI / Verify` check. Keep the required approval count at zero while there is no second independent reviewer; the owner cannot approve their own pull request. See [GOVERNANCE.md](GOVERNANCE.md) for the current remote enforcement status and review-limit recommendation.
