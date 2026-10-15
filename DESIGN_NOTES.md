# Design notes

## Touch-first scrolling

When designing for a touchscreen, especially a small display such as an 800×480 Pi panel, make the content itself the scroll surface. Prefer a natural finger swipe or pan over a dedicated scrollbar handle; do not require a scrollbar to find, reach, or understand content beyond the visible area. Hide decorative scrollbars when the gesture and content layout make scrolling clear.

Use native browser scrolling where possible, with the correct gesture direction (`pan-y` for vertical pages and `pan-x` for horizontal strips). Keep keyboard scrolling, visible focus, accessible labels, and sufficiently large controls. Add buttons as an optional alternative when they improve discoverability or accessibility, not as a substitute for direct touch interaction. Test at the target resolution and on the actual touchscreen when available.

### Scrolling verification checklist

For each changed scroll surface, test all input methods that the surface claims to support; these are separate paths and success with one is not evidence for another:

- Finger/touch swipe on the content, including the target touchscreen when available.
- Mouse-like click-and-drag on the content, since some kiosk touch panels report gestures as mouse input.
- Mouse wheel or trackpad scroll, if the platform/browser supports it.
- Keyboard scrolling and visible focus for keyboard users.
- Horizontal swiping for horizontal lists, checking left/right behavior independently from vertical page scrolling.
- Start, middle, and end positions, including the correct axis/direction and any per-view scroll reset behavior.
- Taps/clicks on buttons, links, inputs, and selects still activate controls instead of starting a drag.
- Sticky back/close controls remain reachable; hidden scrollbars do not prevent users from discovering or using overflowing content.
- If the view has an idle/return timer, scrolling and pointer activity pause or reset the timer as designed.

Use an 800×480 viewport for the compact layout. Report browser-simulated gestures separately from tests performed on physical touch hardware, and state any unavailable input method explicitly.

Keep an essential way to leave a long scrolling screen within reach. A compact sticky header with a close or back action lets users exit without reserving a large fixed control area or scrolling back to the top.

## Dayglance settings page

The settings screen scrolls vertically by swiping over its content. It does not show a scrollbar; the settings panel remains keyboard-focusable and uses native touch scrolling plus drag-to-pan for touch panels that report gestures as mouse input. Its compact title and close control stay pinned while the options move beneath them. Test touch, mouse-like drag, wheel/trackpad where available, keyboard scrolling, click targets, and start-to-end scrolling separately.
