# Contributing

Thanks for helping improve Dayglance. Open an issue for a bug or feature idea, and include the browser, operating system, screen dimensions, and steps to reproduce when relevant. Please do not include private location details or credentials in reports.

Code contributions are proposed by pull request; public contributors do not need direct write access. The owner reviews and decides whether to merge proposals. See [GOVERNANCE.md](GOVERNANCE.md) for roles, current GitHub enforcement, and the recommended review process.

Follow the [coding standards](CODING_STANDARDS.md) and run the checks listed there that apply to your change. UI changes should include a screenshot update and touchscreen verification when available.

## Development

Dayglance is a static HTML/CSS/JavaScript app with a small Python standard-library server. No frontend build step is required:

```sh
python3 server.py
```

Before submitting a change, check the relevant behavior on a desktop browser and, when available, the intended touchscreen. Useful manual checks include:

- Fresh browser opens setup; city and postal-code suggestions can be selected.
- A configured location and multiple browser-saved locations load and can be edited.
- Day cards and today's weather open the correct hourly forecast; each view begins at its first hour.
- The hourly strip can be moved using touch/swipe and the large arrows. Interacting pauses the return countdown; idle time returns to the overview.
- The layout remains readable at 800×480 and at a larger desktop size.
- Weather icons render, cached UI loads after the network is disconnected, and refreshing recovers when connectivity returns.
- The operating system's screensaver can run and the page remains usable when the display wakes.

Keep the Open-Meteo attribution visible and preserve the distinction between the MIT license for this repository's code and the terms for external data/services. Do not commit user-specific location records, browser storage, credentials, or machine logs.
