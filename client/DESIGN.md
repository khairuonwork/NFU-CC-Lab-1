# Client UI direction

Reading this as: an internal lab operations interface for students demonstrating
distributed inference, in a plain and readable application style, dial
ENERGY 1 / RHYTHM 2 / MOTION 2.

- **Palette:** warm off-white, charcoal text, and restrained blue for the one
  action that starts inference. Green, amber, and red only communicate live
  worker and job state.
- **Typography:** the system font keeps a compact technical tool readable
  without adding another font dependency.
- **Layout:** image submission is the primary task. Worker state and result
  details remain visible but secondary.
- **Visualisation:** the route uses one slow packet at a time so a presenter
  can explain each handoff. Heartbeat state stays static because it represents
  real data, not a decorative animation. Long playback has a pause control.
